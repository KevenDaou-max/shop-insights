// Horizontal bars comparing the model with baselines on ONE metric. Every bar carries a direct
// value label, so the colour (blue = model, orange = baseline) is never the only cue.
export default function CompareBars({ title, rows, format, lowerIsBetter = false }) {
  const max = Math.max(...rows.map((r) => r.value ?? 0), 1e-9);
  const valid = rows.filter((r) => r.value != null);
  const best = valid.reduce((a, b) => ((lowerIsBetter ? b.value < a.value : b.value > a.value) ? b : a), valid[0]);
  return (
    <figure className="compare">
      <figcaption>
        {title} <span className="muted">({lowerIsBetter ? "lower" : "higher"} is better)</span>
      </figcaption>
      {rows.map((r) => (
        <div className="compare-row" key={r.label} title={`${r.label}: ${format(r.value)}`}>
          <span className="compare-label">{r.label}</span>
          <div className="compare-track">
            <div
              className={`compare-bar ${r.isModel ? "model" : "baseline"}`}
              style={{ width: `${((r.value ?? 0) / max) * 100}%` }}
            />
            <span className="compare-value">
              {format(r.value)}
              {r === best && valid.length > 1 && " ✓ best"}
            </span>
          </div>
        </div>
      ))}
    </figure>
  );
}
