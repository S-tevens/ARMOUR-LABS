/** Thin line meter with a triangle marker, as in the reference. Value is 0..1. */
export default function Meter({
  label,
  display,
  value,
  tone = "green",
  threshold,
}: {
  label?: string;
  display: string;
  value: number;
  tone?: "green" | "amber" | "red";
  threshold?: number;
}) {
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className="meter">
      <div className="meter-top">
        <span>{label}</span>
        <b>{display}</b>
      </div>
      <div className={`meter-line ${tone}`} role="meter" aria-label={label ?? display} aria-valuemin={0} aria-valuemax={1} aria-valuenow={v}>
        <i className="meter-fill" style={{ width: `${v * 100}%` }} />
        {threshold !== undefined && <i className="meter-tick" style={{ left: `${threshold * 100}%` }} title={`Alert threshold ${threshold}`} />}
        <i className="meter-marker" style={{ left: `${v * 100}%` }} />
      </div>
    </div>
  );
}
