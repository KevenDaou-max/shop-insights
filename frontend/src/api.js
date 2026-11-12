// All HTTP calls live here, so components never build URLs or parse errors themselves.
const BASE = import.meta.env.VITE_API_URL ?? "";

async function request(path, options) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, options);
  } catch {
    throw new Error("Can't reach the server. Is the backend running on port 8000?");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    // FastAPI sends {detail: "..."} or, for validation errors, {detail: [{msg: ...}]}.
    const detail = body?.detail;
    const message = Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail;
    throw new Error(message || `Request failed (${response.status})`);
  }
  return body;
}

function settingsForm({ leadTimeWeeks, coverageWeeks }) {
  const form = new FormData();
  form.append("lead_time_weeks", leadTimeWeeks);
  form.append("coverage_weeks", coverageWeeks);
  return form;
}

export function analyzeUpload({ salesFile, stockFile, ...settings }) {
  const form = settingsForm(settings);
  form.append("sales_file", salesFile);
  if (stockFile) form.append("stock_file", stockFile);
  return request("/api/analyses", { method: "POST", body: form });
}

export function analyzeDemo({ useSampleStock, ...settings }) {
  const form = settingsForm(settings);
  form.append("use_sample_stock", useSampleStock);
  return request("/api/analyses/demo", { method: "POST", body: form });
}

export function getAnalysis(id) {
  return request(`/api/analyses/${encodeURIComponent(id)}`);
}

export function getSummary(id) {
  return request(`/api/analyses/${encodeURIComponent(id)}/summary`);
}
