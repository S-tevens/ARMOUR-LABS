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
  const who = x.source === "gemini" ? `Written by Gemini (${x.model ?? "model"}) from the evidence below` : x.pending ? "Template summary. Gemini is writing a clearer version…" : "Summary generated from the evidence below";
  return (
    <div className="plain-words" aria-live="polite">
      <span className="plain-label">In plain words</span>
      <p>{x.text}</p>
      <small className="muted">{who}{x.note ? `. ${x.note}` : ""}. Check it against the evidence.</small>
    </div>
  );
}
