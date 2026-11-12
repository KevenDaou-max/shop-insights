import { useEffect, useState } from "react";
import { analyzeDemo, analyzeUpload, getAnalysis } from "./api.js";
import UploadForm from "./components/UploadForm.jsx";
import Results from "./components/Results.jsx";

const analysisIdFromHash = () => new URLSearchParams(window.location.hash.slice(1)).get("analysis");

export default function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run(promise) {
    setLoading(true);
    setError("");
    try {
      const data = await promise;
      setResult(data);
      const params = new URLSearchParams(window.location.hash.slice(1));
      params.set("analysis", data.id); // a page reload can fetch this result again
      history.replaceState(null, "", `#${params}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // On first load only: reopen a previous analysis from the URL (served from the API cache).
  useEffect(() => {
    const id = analysisIdFromHash();
    if (id) run(getAnalysis(id));
  }, []);

  function startOver() {
    setResult(null);
    setError("");
    history.replaceState(null, "", window.location.pathname);
  }

  return (
    <div className="page">
      <header className="topbar">
        <h1 onClick={startOver} className="brand">Shop Insights</h1>
        <span className="tagline">AI sales advisor for online shops</span>
        {result && <button className="link" onClick={startOver}>New analysis</button>}
      </header>
      <main>
        {result ? (
          <Results result={result} />
        ) : (
          <UploadForm
            loading={loading}
            error={error}
            onUpload={(input) => run(analyzeUpload(input))}
            onDemo={(input) => run(analyzeDemo(input))}
          />
        )}
      </main>
    </div>
  );
}
