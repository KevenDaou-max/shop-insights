import AiSummary from "./AiSummary.jsx";
import { fmtInt, fmtMoney } from "../format.js";

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

export default function Overview({ result, summary }) {
  const { data, promote, dying, bundles, restock, settings, timings_seconds: timings, cached } = result;
  const bestBundle = bundles[0] ? `${bundles[0].description_a} + ${bundles[0].description_b}` : "none";
  return (
    <>
      <h2>Your shop at a glance</h2>
      <p className="muted">Sales from {data.first_date} to {data.last_date} (after cleaning).</p>
      <div className="stats">
        <Stat label="Order lines" value={fmtInt(data.rows)} />
        <Stat label="Orders" value={fmtInt(data.orders)} />
        <Stat label="Products" value={fmtInt(data.products)} />
        <Stat label="Units sold" value={fmtInt(data.units_sold)} />
        <Stat label="Revenue" value={fmtMoney(data.revenue)} />
      </div>

      <AiSummary summary={summary} />

      <h3>Quick advice</h3>
      <ul className="advice">
        <li><strong>{promote.length}</strong> products to promote. Top: {promote[0]?.description ?? "none"}</li>
        <li><strong>{dying.length}</strong> products dying. Biggest drop: {dying[0]?.description ?? "none"}</li>
        <li><strong>{bundles.length}</strong> bundle ideas. Best: {bestBundle}</li>
        <li>
          <strong>{restock.length}</strong>{" "}
          {settings.stock_file ? "products to reorder" : "products with a recommended stock level"}
          {" "}(lead time {settings.lead_time_weeks} + coverage {settings.coverage_weeks} weeks)
        </li>
      </ul>

      <p className="muted small">
        Analysis time: {Object.entries(timings).map(([step, s]) => `${step} ${s.toFixed(2)}s`).join(" · ")}
        {cached && " · served from cache"}
      </p>
    </>
  );
}
