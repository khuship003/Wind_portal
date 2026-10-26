// Tiny fetch wrapper: throws Error(message) using the API's {error} body.
async function get(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
  ).toString();
  const res = await fetch(`/api/${path}${qs ? `?${qs}` : ""}`);
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error */
  }
  if (!res.ok) throw new Error(body?.error || `Request failed (${res.status})`);
  return body;
}

export const api = {
  meta: () => get("meta"),
  decision: (decision_date, cutoff) => get("decision", { decision_date, cutoff }),
  accuracy: (start, end, cutoff) => get("accuracy", { start, end, cutoff }),
  horizon: (start, end) => get("horizon", { start, end }),
};
