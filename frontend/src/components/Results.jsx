import { useEffect, useState } from "react";
import { getSummary } from "../api.js";
import Overview from "./Overview.jsx";
import TrendSection from "./TrendSection.jsx";
import BundlesSection from "./BundlesSection.jsx";
import ForecastSection from "./ForecastSection.jsx";
import RestockSection from "./RestockSection.jsx";
import BacktestSection from "./BacktestSection.jsx";

// Every tab renders from the single result object fetched once; switching tabs never re-fetches.
const TABS = [
  { id: "overview", label: "Overview", render: (r, summary) => <Overview result={r} summary={summary} /> },
  { id: "promote", label: "Promote", render: (r) => <TrendSection kind="promote" rows={r.promote} /> },
  { id: "dying", label: "Dying", render: (r) => <TrendSection kind="dying" rows={r.dying} /> },
  { id: "bundles", label: "Bought together", render: (r) => <BundlesSection rows={r.bundles} /> },
  { id: "forecast", label: "Forecast", render: (r) => <ForecastSection forecast={r.forecast} /> },
  { id: "restock", label: "Restock", render: (r) => <RestockSection rows={r.restock} settings={r.settings} /> },
  { id: "proof", label: "Proof (backtest)", render: (r) => <BacktestSection backtest={r.backtest} /> },
];

// The open tab lives in the URL hash (e.g. #analysis=abc&tab=restock), so a link can open it directly.
function tabFromHash() {
  const tab = new URLSearchParams(window.location.hash.slice(1)).get("tab");
  return TABS.some((t) => t.id === tab) ? tab : "overview";
}

export default function Results({ result }) {
  const [tab, setTabState] = useState(tabFromHash);
  const [summary, setSummary] = useState({ loading: true });

  // The LLM summary is slower than the analysis, so it loads separately, once per analysis.
  useEffect(() => {
    let cancelled = false;
    setSummary({ loading: true });
    getSummary(result.id)
      .then((data) => !cancelled && setSummary({ data }))
      .catch((err) => !cancelled && setSummary({ error: err.message }));
    return () => {
      cancelled = true;
    };
  }, [result.id]);

  function setTab(id) {
    setTabState(id);
    const params = new URLSearchParams(window.location.hash.slice(1));
    params.set("tab", id);
    history.replaceState(null, "", `#${params}`);
  }
  const current = TABS.find((t) => t.id === tab);
  return (
    <>
      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === tab}
            className={t.id === tab ? "active" : ""}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <section className="card" role="tabpanel">{current.render(result, summary)}</section>
    </>
  );
}
