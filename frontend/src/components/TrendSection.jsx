import DataTable from "./DataTable.jsx";
import { fmtInt } from "../format.js";

const TEXT = {
  promote: {
    title: "Products to promote",
    intro:
      "Sales grew over the last 8 weeks vs the 8 weeks before, in units AND in number of orders " +
      "(so one big order doesn't count). Ranked by extra units sold.",
  },
  dying: {
    title: "Dying products",
    intro:
      "Products that sold at least 50 units in the previous 8 weeks but dropped by half or more, " +
      "or almost stopped. Consider a clearance discount or not restocking them.",
  },
};

const columns = [
  { key: "description", label: "Product" },
  { key: "stock_code", label: "Code" },
  { key: "previous_units", label: "Units (8 wks before)", numeric: true, format: fmtInt },
  { key: "recent_units", label: "Units (last 8 wks)", numeric: true, format: fmtInt },
  { key: "reason", label: "Why" },
];

export default function TrendSection({ kind, rows }) {
  return (
    <>
      <h2>{TEXT[kind].title}</h2>
      <p className="muted">{TEXT[kind].intro}</p>
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.stock_code} />
    </>
  );
}
