import type { NetworkEvent } from "../types";

export default function EventTable({ events }: { events: NetworkEvent[] }) {
  return (
    <section className="glass table-panel">
      <header className="panel-head"><h2>Recent messages</h2><span className="muted small">Newest first</span></header>
      <table>
        <thead>
          <tr><th>Time</th><th>From</th><th>To</th><th>Message</th><th>Status</th></tr>
        </thead>
        <tbody>
          {events.slice(0, 10).map((e) => (
            <tr key={e.seq} className={e.authorised ? "" : "row-bad"}>
              <td>{e.t.toFixed(0)} s</td>
              <td>{e.src}</td>
              <td>{e.dst}</td>
              <td>{e.function_code} {e.register} = {String(e.value)}</td>
              <td><span className={`pill ${e.authorised ? "ok" : "bad"}`}>{e.authorised ? "Authorised" : "Unauthorised"}</span></td>
            </tr>
          ))}
          {events.length === 0 && <tr><td colSpan={5} className="empty">No messages yet</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
