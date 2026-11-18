"""Plain-language incident explanations.

Two writers share one input, the incident's own evidence:
  * a template that always works (no network, no key), and
  * Gemini, used only when GEMINI_API_KEY is set. It is told to use nothing but the supplied facts, and its answer is
    rejected (the template is shown instead) if it contains a number that is not in those facts.
The page always says which writer produced the text. The call runs in the background so the interface never waits for it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODELS = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-3.5-flash-lite"]  # tried in order; override with GEMINI_MODEL
RETRY_AFTER_S = 45  # after a failed attempt for an incident, use the template this long before asking again
MAX_CHARS = 900

CAUSE = {
    "attack": "looks like a cyberattack",
    "fault": "looks like a physical fault, not an attack",
    "unknown": "has no confirmed cause yet",
}
STATUS_NEXT = {
    "open": "Nothing has been done yet. An operator can approve the simulated containment.",
    "responding": "Containment is in progress.",
    "recovering": "Containment is done and the system is being checked against its normal limits before it is called recovered.",
    "recovered": "The system is back inside its normal limits and the incident is closed.",
    "unresolved": "The system did not return to its normal limits, so an operator needs to look at it.",
}
DETECTORS = {
    "network": "the network rules", "controller": "the controller checks", "process": "the process limits",
    "twin": "the digital twin", "invariants": "the physics checks", "ml": "the machine-learning model",
    "twin_residual": "the digital twin",
}

SYSTEM = (
    "You explain power-grid incidents to an operator who is not a security expert. Use ONLY the facts in the JSON the user "
    "sends. Never invent numbers, device names, causes, times or actions. Do not use any number that is not in the facts. "
    "Write every number and address exactly as it appears in the facts, as digits (for example 775,000 and 10.0.0.66); never spell numbers or addresses out in words. Write 3 or 4 short sentences of plain English, no markdown, no bullet points. Say what happened, why the system thinks "
    "so, and what the next step is, using the given status. If the cause is unknown, say that clearly. Do not call "
    "something an attack unless the classification says attack."
)


def facts(inc: dict) -> dict:
    """The only information either writer sees."""
    fired = [DETECTORS.get(k, k) for k, v in sorted(inc.get("scores", {}).items(), key=lambda kv: -kv[1]) if v >= 0.8]
    return {
        "incident": inc["id"],
        "severity": inc["severity"],
        "classification": inc["classification"],
        "status": inc["status"],
        "affected_devices": inc.get("affected_devices", []),
        "detectors_raised_alert": fired,
        "evidence": [e["text"] for e in inc.get("evidence", [])][:8],
        "district": inc.get("district"),
        "next_step_given_status": STATUS_NEXT.get(inc["status"], ""),
    }


def template_text(inc: dict) -> str:
    f = facts(inc)
    parts = [f"A {f['severity']}-severity incident {CAUSE.get(f['classification'], CAUSE['unknown'])}."]
    if f["affected_devices"]:
        parts.append("It affects " + ", ".join(f["affected_devices"]) + ".")
    if f["detectors_raised_alert"]:
        parts.append("It was flagged by " + _join(f["detectors_raised_alert"]) + ".")
    if f["evidence"]:
        parts.append("Main evidence: " + _sentence(f["evidence"][0]) + (" " + _sentence(f["evidence"][1]) if len(f["evidence"]) > 1 else ""))
    parts.append(f["next_step_given_status"])
    return " ".join(p for p in parts if p)


def _join(items: list[str]) -> str:
    items = list(dict.fromkeys(items))
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


_NUM = re.compile(r"\d+(?:\.\d+)?")
_SPELLED = re.compile(r"\b(?:hundred|thousand|million|billion|dot)\b", re.I)  # numbers or addresses written out in words


def grounded(answer: str, f: dict) -> bool:
    """Every number in the answer must already be in the facts, and none may be spelled out in words."""
    if _SPELLED.search(answer):
        return False
    allowed = set(_NUM.findall(json.dumps(f)))
    return all(n in allowed for n in _NUM.findall(answer))


def call_gemini(f: dict, key: str, models: list[str], timeout: float = 12.0) -> tuple[str, str]:
    """Returns (text, model). Raises RuntimeError when no model answered."""
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(f)}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
    }).encode()
    last = "no model tried"
    for model in models:
        req = urllib.request.Request(API.format(model=model), data=body, method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
            if text:
                return text, model
            last = f"{model}: empty answer"
        except urllib.error.HTTPError as e:
            last = f"{model}: HTTP {e.code}"
        except Exception as e:  # network, timeout, malformed answer
            last = f"{model}: {type(e).__name__}"
    raise RuntimeError(last)


class ExplanationService:
    def __init__(self, caller=call_gemini):
        self._caller = caller
        self._lock = threading.Lock()
        self._done: dict[str, dict] = {}
        self._busy: set[str] = set()
        self._failed: dict[str, float] = {}

    @staticmethod
    def configured() -> bool:
        return bool(os.getenv("GEMINI_API_KEY"))

    def _models(self) -> list[str]:
        m = os.getenv("GEMINI_MODEL")
        return [m] if m else DEFAULT_MODELS

    @staticmethod
    def _key(inc: dict) -> str:
        digest = hashlib.sha1(json.dumps(facts(inc), sort_keys=True).encode()).hexdigest()[:12]  # same id after a reset, different content
        return f"{inc['id']}|{inc['status']}|{digest}"

    def explain(self, inc: dict) -> dict:
        """The best explanation available now. `pending` is true while a Gemini answer is on its way."""
        key = self._key(inc)
        base = {"text": template_text(inc), "source": "template", "model": None, "pending": False, "gemini_configured": self.configured()}
        with self._lock:
            if key in self._done:
                return {**base, **self._done[key]}
            if not self.configured():
                return base
            if time.time() - self._failed.get(key, 0) < RETRY_AFTER_S:
                return {**base, "note": "Gemini did not answer; showing the template."}
            if key not in self._busy:
                self._busy.add(key)
                threading.Thread(target=self._work, args=(key, inc), daemon=True, name="explain").start()
            return {**base, "pending": True}

    def _work(self, key: str, inc: dict) -> None:
        f = facts(inc)
        try:
            text, model = self._caller(f, os.environ["GEMINI_API_KEY"], self._models())
            text = text[:MAX_CHARS]
            if not grounded(text, f):
                raise RuntimeError("answer contained a number that is not in the evidence")
            with self._lock:
                self._done[key] = {"text": text, "source": "gemini", "model": model}
        except Exception:
            with self._lock:
                self._failed[key] = time.time()
        finally:
            with self._lock:
                self._busy.discard(key)
