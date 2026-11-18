import type { PlcState, Telemetry } from "../types";

const plcColor = (s: PlcState) => (s === "compromised" ? "var(--red)" : s === "suspicious" ? "var(--amber)" : "var(--green)");

function Tank({ x, label, level }: { x: number; label: string; level: number }) {
  const h = 140;
  const fill = (Math.max(0, Math.min(100, level)) / 100) * h;
  return (
    <g>
      <rect x={x} y={70} width={90} height={h} rx={6} fill="var(--panel2)" stroke="var(--line)" strokeWidth={2} />
      <rect x={x + 2} y={70 + h - fill} width={86} height={fill} fill="var(--blue)" opacity={0.75} />
      <text x={x + 45} y={60} textAnchor="middle" className="svg-label">{label}</text>
      <text x={x + 45} y={140} textAnchor="middle" className="svg-value">{level.toFixed(1)}%</text>
    </g>
  );
}

function Pipe({ x1, x2, y, flow }: { x1: number; x2: number; y: number; flow: number }) {
  const active = flow > 5;
  const dur = active ? Math.max(0.4, 130 / flow) : 0;
  return (
    <line
      x1={x1} x2={x2} y1={y} y2={y}
      className={active ? "pipe flowing" : "pipe"}
      style={active ? { animationDuration: `${dur}s` } : undefined}
    />
  );
}

function Pump({ x, label, on }: { x: number; label: string; on: boolean }) {
  return (
    <g>
      <circle cx={x} cy={140} r={24} fill="var(--panel2)" stroke={on ? "var(--green)" : "var(--line)"} strokeWidth={3} />
      <text x={x} y={145} textAnchor="middle" className="svg-small">{on ? "ON" : "OFF"}</text>
      <text x={x} y={108} textAnchor="middle" className="svg-label">{label}</text>
    </g>
  );
}

export default function PlantView({ t }: { t: Telemetry | null }) {
  if (!t) return <div className="empty">Waiting for plant telemetry…</div>;
  const blocked = !t.valve1;
  return (
    <svg viewBox="0 0 800 300" className="plant" role="img" aria-label="Live plant view">
      <Tank x={20} label="TANK 1" level={t.tank1_level} />
      <Pipe x1={110} x2={175} y={140} flow={t.flow} />
      <Pump x={200} label="PUMP 1" on={t.pump1} />
      <Pipe x1={224} x2={285} y={140} flow={t.flow} />
      <rect x={285} y={115} width={60} height={50} rx={6} fill="var(--panel2)" stroke="var(--line)" strokeWidth={2} />
      <text x={315} y={105} textAnchor="middle" className="svg-label">FILTER</text>
      <Pipe x1={345} x2={405} y={140} flow={t.flow} />
      <g>
        <polygon points="430,115 455,140 430,165 405,140" fill="var(--panel2)" stroke={blocked ? "var(--red)" : "var(--green)"} strokeWidth={3} />
        <text x={430} y={105} textAnchor="middle" className="svg-label">VALVE 1</text>
        <text x={430} y={185} textAnchor="middle" className="svg-small">{t.valve1 ? "OPEN" : "CLOSED"}</text>
      </g>
      <Pipe x1={455} x2={540} y={140} flow={t.flow} />
      <Tank x={540} label="TANK 2" level={t.tank2_level} />
      <Pipe x1={630} x2={690} y={140} flow={t.flow} />
      <Pump x={715} label="PUMP 2" on={t.pump2} />

      {/* readouts */}
      <g className="readouts">
        <text x={20} y={250} className="svg-value">Pressure {t.pressure.toFixed(2)} bar</text>
        <text x={230} y={250} className="svg-value">Flow {t.flow.toFixed(0)} L/min</text>
        <text x={420} y={250} className="svg-value">Temp {t.temperature.toFixed(1)} °C</text>
      </g>
      {/* PLC indicators */}
      {(["plc01", "plc02", "plc03"] as const).map((k, i) => (
        <g key={k}>
          <circle cx={30 + i * 110} cy={282} r={6} fill={plcColor(t.plc_status[k])} />
          <text x={42 + i * 110} y={286} className="svg-small">{k.toUpperCase().replace("PLC", "PLC-")}</text>
        </g>
      ))}
    </svg>
  );
}
