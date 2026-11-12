import CompareBars from "./CompareBars.jsx";
import { fmtInt, fmtNum, fmtPct } from "../format.js";

function verdict(model, baseline, lowerIsBetter) {
  if (model == null || baseline == null) return "Not enough data to compare.";
  if (model === baseline) return "Model and baseline tied.";
  const modelWins = lowerIsBetter ? model < baseline : model > baseline;
  return modelWins ? "The model beat the simple baseline." : "The simple baseline did better here.";
}

function Legend() {
  return (
    <div className="legend" aria-hidden="true">
      <span><i className="swatch model" /> Model</span>
      <span><i className="swatch baseline" /> Simple baseline</span>
    </div>
  );
}

export default function BacktestSection({ backtest: bt }) {
  if (!bt.available) return <p className="muted">Backtest not available: {bt.reason}</p>;
  const { forecast: fc, forecast_previous_month: prev, trends, bundles, restock } = bt;

  const restockRows = (metric) => [
    { label: "Model + safety stock", value: restock.model_with_safety_stock[metric], isModel: true },
    { label: "Model, no safety stock", value: restock.model_forecast_only[metric], isModel: true },
    { label: "Same as last month", value: restock.baseline_same_as_last_month[metric] },
  ];

  return (
    <>
      <h2>Proof: does it work?</h2>
      <p className="muted">
        We hid the last 4 weeks ({bt.cutoff} → {bt.hidden_until}), made every recommendation using only the
        data before {bt.cutoff}, then checked what really happened. Each result is compared with a simple
        baseline a shop owner could do without any model.
      </p>
      <Legend />

      <h3>1. Forecast accuracy ({fc.products} top products, 4 weeks)</h3>
      <div className="grid2">
        <CompareBars
          title="Hidden month: error (WAPE)"
          format={fmtPct}
          lowerIsBetter
          rows={[
            { label: "Model", value: fc.wape_pct.model, isModel: true },
            { label: "Avg of last 4 weeks", value: fc.wape_pct.baseline_last_4_weeks_avg },
            { label: "Same weeks last year", value: fc.wape_pct.baseline_same_weeks_last_year },
          ]}
        />
        <CompareBars
          title="Month before (extra check): error (WAPE)"
          format={fmtPct}
          lowerIsBetter
          rows={[
            { label: "Model", value: prev.wape_pct.model, isModel: true },
            { label: "Avg of last 4 weeks", value: prev.wape_pct.baseline_last_4_weeks_avg },
            { label: "Same weeks last year", value: prev.wape_pct.baseline_same_weeks_last_year },
          ]}
        />
      </div>
      <p className="note">
        Hidden month: {verdict(fc.wape_pct.model, fc.wape_pct.baseline_last_4_weeks_avg, true)} Month before:{" "}
        {verdict(prev.wape_pct.model, prev.wape_pct.baseline_last_4_weeks_avg, true)} WAPE = total units we were
        off by ÷ total units sold. Model total bias in the hidden month: {fmtPct(fc.bias_pct.model)}.
      </p>

      <h3>2. Promote list (top 20)</h3>
      <CompareBars
        title="Products that beat the shop's overall growth in the hidden month"
        format={fmtPct}
        rows={[
          { label: "Model's promote list", value: trends.promote.model.hit_rate_pct, isModel: true },
          { label: "Last month's best sellers", value: trends.promote.baseline_last_month_best_sellers.hit_rate_pct },
        ]}
      />
      <p className="note">
        {verdict(trends.promote.model.hit_rate_pct, trends.promote.baseline_last_month_best_sellers.hit_rate_pct, false)}{" "}
        The whole shop grew {fmtPct(trends.shop_growth_pct)}, so we count a product only if it gained share.
      </p>

      <h3>3. Dying list (top 20)</h3>
      <CompareBars
        title="Products that really sold < half their earlier normal month"
        format={fmtPct}
        rows={[
          { label: "Model's dying list", value: trends.dying.model.hit_rate_pct, isModel: true },
          { label: "Last month's worst sellers", value: trends.dying.baseline_last_month_worst_sellers.hit_rate_pct },
        ]}
      />
      <p className="note">
        {verdict(trends.dying.model.hit_rate_pct, trends.dying.baseline_last_month_worst_sellers.hit_rate_pct, false)}{" "}
        The model's list covers bigger products ({fmtInt(trends.dying.model.earlier_normal_month_units)} vs{" "}
        {fmtInt(trends.dying.baseline_last_month_worst_sellers.earlier_normal_month_units)} units in a normal month).
      </p>

      <h3>4. Bought-together pairs (top 20)</h3>
      <CompareBars
        title="Median lift in the hidden month"
        format={(v) => `${fmtNum(v)}×`}
        rows={[
          { label: "Model (highest lift)", value: bundles.model_top_lift_pairs.median_lift, isModel: true },
          { label: "Most common pairs", value: bundles.baseline_most_common_pairs.median_lift },
        ]}
      />
      <p className="note">
        {fmtPct(bundles.model_top_lift_pairs.pct_still_bought_together)} of the model's pairs that were bought
        in the hidden month were still bought together more than by chance (baseline:{" "}
        {fmtPct(bundles.baseline_most_common_pairs.pct_still_bought_together)}).
      </p>

      <h3>5. Restock ({restock.products} products, {fmtInt(restock.actual_units)} units really sold)</h3>
      <div className="grid2">
        <CompareBars title="Products that ran out" format={fmtPct} lowerIsBetter rows={restockRows("ran_out_pct")} />
        <CompareBars title="Units left over" format={fmtInt} lowerIsBetter rows={restockRows("units_left_over")} />
      </div>
      <p className="note">
        Safety stock is a trade-off: it prevents most stock-outs (fill rate{" "}
        {fmtPct(restock.model_with_safety_stock.fill_rate_pct)} vs{" "}
        {fmtPct(restock.baseline_same_as_last_month.fill_rate_pct)} for "same as last month") but leaves more
        stock on the shelf.
      </p>
    </>
  );
}
