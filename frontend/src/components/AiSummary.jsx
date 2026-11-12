// Shows the Gemini summary. The parent fetches it once per analysis and passes the state down.
export default function AiSummary({ summary }) {
  if (summary.loading) return <p className="muted ai-summary">Writing a plain-English summary with Gemini…</p>;
  if (!summary.data?.available) {
    return <p className="muted small">AI summary not available: {summary.data?.message ?? summary.error}</p>;
  }
  return (
    <div className="ai-summary">
      <strong>AI summary</strong> <span className="muted small">(written by Gemini from the numbers below)</span>
      {summary.data.text.split(/\n+/).map((line, i) => (
        // Plain text only: the model's output is never injected as HTML.
        <p key={i}>{line.replace(/^\s*[-*]\s+/, "• ").replace(/\*\*/g, "")}</p>
      ))}
    </div>
  );
}
