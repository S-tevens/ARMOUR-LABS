import { useEffect, useState } from "react";
import type { Explanation } from "../api";
import type { Incident } from "../types";

/** Plain-language summary of an incident. It is always labelled with who wrote it, and sits above the raw evidence it is built from. */
export default function PlainWords({ incident, load }: { incident: Incident; load: (id: string) => Promise<Explanation> }) {
  const [x, setX] = useState<Explanation | null>(null);
  const state = `${incident.id}|${incident.status}|${incident.classification}|${incident.evidence.length}`;

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    const go = () =>
      load(incident.id)
        .then((r) => {
          if (!alive) return;
          setX(r);
          if (r.pending) timer = window.setTimeout(go, 2000); // a Gemini answer is on its way
        })
        .catch(() => undefined);
    void go();
    return () => { alive = false; window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  if (!x) return null;
  const gemini = x.source === "gemini";
  const who = gemini ? `Written by Gemini (${x.model ?? "model"}) from the evidence below` : x.pending ? "Template summary. Gemini is writing a clearer version…" : "Summary generated from the evidence below";
  return (
    <div className="plain-words" aria-live="polite">
      <div className="plain-head">
        <span className="plain-label">In plain words</span>
        {(gemini || x.pending) && (
          <span className={`ai-badge ${gemini ? "" : "working"}`} title={gemini ? `Written by Google Gemini (${x.model ?? "model"})` : "Gemini is writing this summary"}>
            <img src="/gemini.png" alt="" width="20" height="20" />
            {gemini ? "AI summary · Gemini" : "Gemini is writing…"}
          </span>
        )}
      </div>
      <p>{x.text}</p>
      <small className="muted">{who}{x.note ? `. ${x.note}` : ""}. Check it against the evidence.</small>
    </div>
  );
}
