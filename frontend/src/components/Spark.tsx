/** Tiny bar sparkline over a fixed domain, as in the reference KPI strip. */
export default function Spark({
  values,
  domain,
  color,
  bars = 26,
}: {
  values: number[];
  domain: [number, number];
  color: string;
  bars?: number;
}) {
  const w = 3;
  const gap = 2;
  const h = 34;
  const v = values.slice(-bars);
  const [lo, hi] = domain;
  return (
    <svg width={bars * (w + gap)} height={h} aria-hidden="true" className="spark">
      {v.map((x, i) => {
        const n = Math.max(0.06, Math.min(1, (x - lo) / (hi - lo)));
        const bh = n * h;
        return <rect key={i} x={i * (w + gap)} y={h - bh} width={w} height={bh} rx={1.5} fill={color} opacity={0.35 + 0.65 * (i / Math.max(1, v.length - 1))} />;
      })}
    </svg>
  );
}
