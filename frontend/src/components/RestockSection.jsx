import DataTable from "./DataTable.jsx";
import { fmtInt, fmtNum } from "../format.js";

function Reason({ text }) {
  return text.startsWith("URGENT") ? <strong className="urgent">⚠ {text}</strong> : text;
}

export default function RestockSection({ rows, settings }) {
  const withStock = settings.stock_file;
  const columns = [
    { key: "description", label: "Product" },
    { key: "recommended_quantity", label: withStock ? "Units to order" : "Stock to hold", numeric: true, format: fmtInt },
    { key: "expected_weekly_demand", label: "Expected / week", numeric: true, format: fmtNum },
    ...(withStock
      ? [
          { key: "current_stock", label: "In stock", numeric: true, format: fmtInt },
          { key: "weeks_of_stock_left", label: "Weeks left", numeric: true, format: fmtNum },
        ]
      : []),
    { key: "safety_stock", label: "Safety stock", numeric: true, format: fmtInt },
    { key: "reason", label: "Why", format: (v) => <Reason text={v} /> },
  ];

  return (
    <>
      <h2>{withStock ? "Restock list: most urgent first" : "Recommended stock levels"}</h2>
      <p className="muted">
        Needed stock = forecast demand for {settings.lead_time_weeks} weeks lead time
        + {settings.coverage_weeks} weeks coverage, plus safety stock for weeks that sell more than expected.
        {withStock
          ? " Only products whose current stock is below that level are listed."
          : " Upload a current-stock file to get exact order quantities."}
      </p>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.stock_code}
        empty={withStock ? "Nothing needs reordering." : "No products to plan."}
      />
    </>
  );
}
