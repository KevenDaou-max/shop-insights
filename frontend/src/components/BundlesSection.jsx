import DataTable from "./DataTable.jsx";
import { fmtInt, fmtNum, fmtPct } from "../format.js";

const asPct = (share) => fmtPct(share * 100);

const columns = [
  { key: "description_a", label: "Product A" },
  { key: "description_b", label: "Product B" },
  { key: "orders_together", label: "Orders with both", numeric: true, format: fmtInt },
  { key: "confidence_a_to_b", label: "A → B", numeric: true, format: asPct },
  { key: "confidence_b_to_a", label: "B → A", numeric: true, format: asPct },
  { key: "lift", label: "Lift", numeric: true, format: (v) => `${fmtNum(v)}×` },
];

export default function BundlesSection({ rows }) {
  return (
    <>
      <h2>Bought together: bundle ideas</h2>
      <p className="muted">
        Pairs that appear in the same order far more often than chance (last 52 weeks).{" "}
        <strong>A → B</strong> = share of orders with A that also contain B.{" "}
        <strong>Lift</strong> = how many times more often the two are bought together than if
        customers picked them independently.
      </p>
      <DataTable columns={columns} rows={rows} rowKey={(r) => `${r.product_a}-${r.product_b}`} />
    </>
  );
}
