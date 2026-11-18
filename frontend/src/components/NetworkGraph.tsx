import type { LinkStat } from "../useStream";
import type { PlcState, Telemetry } from "../types";

const W = 940, Ht = 430;
const stroke: Record<PlcState, string> = { normal: "#2F6BFF", suspicious: "#F0A030", compromised: "#E5484D" };

const PLCS = [
  { id: "PLC-01", key: "plc01" as const, y: 40, kids: ["Pump 1", "Pump 2"] },
  { id: "PLC-02", key: "plc02" as const, y: 165, kids: ["Valve 1"] },
  { id: "PLC-03", key: "plc03" as const, y: 290, kids: ["Sensors"] },
];
const PX = 640, PW = 270, PH = 100;
const SCADA = { x: 360, y: 190, w: 130, h: 60 };
const EXT = { x: 30, y: 60, w: 130, h: 50 };

function Node({ x, y, w, h, title, sub, tone = "#2F6BFF", alarm = false }: { x: number; y: number; w: number; h: number; title: string; sub?: string; tone?: string; alarm?: boolean }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={16} className={`gnode ${alarm ? "alarm" : ""}`} />
      <rect x={x + 10} y={y + 10} width={16} height={16} rx={5} fill={tone} />
      <text x={x + 34} y={y + 23} className="gtitle">{title}</text>
      {sub && <text x={x + 34} y={y + 40} className="gsub">{sub}</text>}
    </g>
  );
}

function Link({ d, bad, active }: { d: string; bad?: boolean; active?: boolean }) {
  return (
    <g>
      <path d={d} className={`glink ${bad ? "bad" : ""} ${active ? "active" : ""}`} fill="none" />
    </g>
  );
}

export default function NetworkGraph({ t, links }: { t: Telemetry | null; links: Record<string, LinkStat> }) {
  const stat = (k: string): LinkStat => links[k] ?? { total: 0, bad: 0 };
  const attackToScada = stat("10.0.0.66>SCADA").bad > 0;
  const status = (key: "plc01" | "plc02" | "plc03"): PlcState => t?.plc_status[key] ?? "normal";
  const sx = SCADA.x + SCADA.w, sy = SCADA.y + SCADA.h / 2;

  return (
    <section className="glass graph">
      <header className="panel-head">
        <h2>Network</h2>
        <span className="muted small">Message counts since you opened this page</span>
      </header>
      <svg viewBox={`0 0 ${W} ${Ht}`} className="graph-svg" role="img" aria-label="Network topology">
        {/* external -> firewall -> SCADA */}
        <Link d={`M ${EXT.x + EXT.w} ${EXT.y + EXT.h / 2} C 220 ${EXT.y + 25}, 240 ${sy}, ${SCADA.x} ${sy}`} bad={attackToScada} active={attackToScada} />
        {PLCS.map((p) => {
          const s = stat(`SCADA>${p.id}`);
          const atk = stat(`10.0.0.66>${p.id}`);
          const cy = p.y + PH / 2;
          const mid = (sx + PX) / 2;
          return (
            <g key={p.id}>
              <Link d={`M ${sx} ${sy} C ${mid} ${sy}, ${mid} ${cy}, ${PX} ${cy}`} active={s.total > 0} />
              <text x={mid - 34} y={(sy + cy) / 2 - 6} className="glabel">{s.total} messages</text>
              {atk.bad > 0 && (
                <g>
                  <path d={`M ${EXT.x + EXT.w / 2} ${EXT.y + EXT.h} C ${EXT.x + 60} ${Ht - 20}, ${PX - 120} ${Ht - 10}, ${PX} ${cy + 20}`} className="glink bad active" fill="none" />
                  <text x={PX - 210} y={Ht - 22} className="glabel red">{atk.bad} unauthorised from 10.0.0.66</text>
                </g>
              )}
            </g>
          );
        })}
        {attackToScada && <text x={190} y={sy - 40} className="glabel red">Spoofed report from 10.0.0.66</text>}

        <Node x={EXT.x} y={EXT.y} w={EXT.w} h={EXT.h} title="External" sub="Outside the plant" tone="#98A5C3" />
        <Node x={SCADA.x} y={SCADA.y} w={SCADA.w} h={SCADA.h} title="SCADA" sub="Operator station" />
        {PLCS.map((p) => {
          const st = status(p.key);
          return (
            <g key={p.id}>
              <rect x={PX} y={p.y} width={PW} height={PH} rx={20} className={`gnode big ${st === "compromised" ? "alarm" : ""}`} />
              <path d={`M ${PX} ${p.y + 20} a 20 20 0 0 1 20 -20 h 30 v ${PH} h -30 a 20 20 0 0 1 -20 -20 z`} fill={stroke[st]} opacity={0.95} />
              <text x={PX + 66} y={p.y + 30} className="gtitle">{p.id}</text>
              <text x={PX + 66} y={p.y + 49} className="gsub">{st === "normal" ? "Normal" : st === "suspicious" ? "Suspicious" : "Compromised"}</text>
              {p.kids.map((k, i) => (
                <g key={k}>
                  <text x={PX + 66} y={p.y + 72 + i * 16} className="gkid">{k}</text>
                </g>
              ))}
            </g>
          );
        })}
      </svg>
    </section>
  );
}
