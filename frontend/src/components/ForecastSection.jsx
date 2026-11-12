import { useState } from "react";
import ForecastChart from "./ForecastChart.jsx";
import DataTable from "./DataTable.jsx";
import { fmtInt } from "../format.js";

const columns = [
  { key: "description", label: "Product" },
  { key: "last_4_weeks_avg", label: "Avg last 4 weeks", numeric: true, format: fmtInt },
  { key: "next_week", label: "Forecast next week", numeric: true, format: fmtInt },
  { key: "forecast", label: "Next 4 weeks", numeric: true, format: (f) => f.map(fmtInt).join(" · ") },
];

export default function ForecastSection({ forecast }) {
  const [code, setCode] = useState(forecast.products[0]?.stock_code);
  const product = forecast.products.find((p) => p.stock_code === code);
  return (
    <>
      <h2>Sales forecast: top products</h2>
      <p className="muted">
        Weekly units for the next 4 weeks from one machine-learning model trained on all top products
        (it looks at recent weeks and the same weeks last year). The Proof tab shows how accurate it was.
      </p>
      <label className="field inline">
        <span>Product</span>
        <select value={code} onChange={(e) => setCode(e.target.value)}>
          {forecast.products.map((p) => (
            <option key={p.stock_code} value={p.stock_code}>{p.description}</option>
          ))}
        </select>
      </label>
      {product && (
        <ForecastChart product={product} historyWeeks={forecast.history_weeks} forecastWeeks={forecast.forecast_weeks} />
      )}
      <DataTable columns={columns} rows={forecast.products} rowKey={(r) => r.stock_code} />
    </>
  );
}
