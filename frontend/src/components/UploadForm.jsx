import { useState } from "react";

export default function UploadForm({ loading, error, onUpload, onDemo }) {
  const [salesFile, setSalesFile] = useState(null);
  const [stockFile, setStockFile] = useState(null);
  const [leadTimeWeeks, setLeadTimeWeeks] = useState(2);
  const [coverageWeeks, setCoverageWeeks] = useState(2);
  const [useSampleStock, setUseSampleStock] = useState(true);
  const settings = { leadTimeWeeks, coverageWeeks };

  function submit(event) {
    event.preventDefault();
    if (salesFile) onUpload({ salesFile, stockFile, ...settings });
  }

  if (loading) {
    return (
      <section className="card center" aria-live="polite">
        <div className="spinner" aria-hidden="true" />
        <h2>Analysing your sales…</h2>
        <p className="muted">
          Cleaning orders, finding trends and bundles, training the forecast and running the backtest.
          A 1-million-row file takes about 15–30 seconds the first time; the same file again is instant.
        </p>
      </section>
    );
  }

  return (
    <section className="card upload">
      <h2>Upload your sales</h2>
      <p className="muted">
        A CSV or Excel export of order lines with columns <code>Invoice, StockCode, Description, Quantity,
        InvoiceDate, Price</code> (Customer ID and Country are optional).
      </p>
      {error && <p className="error" role="alert">{error}</p>}

      <form onSubmit={submit}>
        <label className="field">
          <span>Sales file (.csv or .xlsx, max 100 MB)</span>
          <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => setSalesFile(e.target.files[0] ?? null)} />
        </label>
        <label className="field">
          <span>Current stock (optional CSV: <code>StockCode,CurrentStock</code>)</span>
          <input type="file" accept=".csv" onChange={(e) => setStockFile(e.target.files[0] ?? null)} />
        </label>
        <div className="row">
          <label className="field small">
            <span>Lead time (weeks until delivery)</span>
            <input type="number" min="0" max="8" value={leadTimeWeeks} onChange={(e) => setLeadTimeWeeks(+e.target.value)} />
          </label>
          <label className="field small">
            <span>Coverage (weeks the order should last)</span>
            <input type="number" min="1" max="8" value={coverageWeeks} onChange={(e) => setCoverageWeeks(+e.target.value)} />
          </label>
        </div>
        <button type="submit" className="primary" disabled={!salesFile}>Analyse my file</button>
      </form>

      <div className="demo">
        <h3>No file? Try the demo</h3>
        <p className="muted">
          Real orders from a UK online gift shop (UCI Online Retail II, Dec 2009 – Dec 2011, ~1M rows).
        </p>
        <label className="check">
          <input type="checkbox" checked={useSampleStock} onChange={(e) => setUseSampleStock(e.target.checked)} />
          Include the SAMPLE stock file (made-up stock levels, for testing the restock list)
        </label>
        <button type="button" onClick={() => onDemo({ useSampleStock, ...settings })}>Run demo analysis</button>
      </div>
    </section>
  );
}
