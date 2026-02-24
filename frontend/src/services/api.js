/**
 * Service API — Centralise tous les appels HTTP vers le backend FastAPI
 */

const BASE_URL = process.env.REACT_APP_API_URL || "/api/v1";

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const config = {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Erreur inconnue" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

// ----------------------------------------------------------
// Alertes
// ----------------------------------------------------------
export const alertsApi = {
  list: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/alerts${qs ? "?" + qs : ""}`);
  },
  get: (id) => request(`/alerts/${id}`),
  update: (id, data) => request(`/alerts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  enrich: (id) => request(`/alerts/${id}/enrich`, { method: "POST" }),
  markFalsePositive: (id, reason) =>
    request(`/alerts/${id}/false-positive?reason=${encodeURIComponent(reason)}`, { method: "POST" }),
  stats: (periodHours = 24) => request(`/alerts/stats?period_hours=${periodHours}`),
};

// ----------------------------------------------------------
// Incidents
// ----------------------------------------------------------
export const incidentsApi = {
  list: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/incidents${qs ? "?" + qs : ""}`);
  },
  get: (id) => request(`/incidents/${id}`),
  create: (data) => request("/incidents", { method: "POST", body: JSON.stringify(data) }),
  update: (id, data) => request(`/incidents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  addNote: (id, note, author = "analyst") =>
    request(`/incidents/${id}/notes`, {
      method: "POST",
      body: JSON.stringify({ note, author }),
    }),
  linkAlert: (incidentId, alertId) =>
    request(`/incidents/${incidentId}/alerts/${alertId}`, { method: "POST" }),
  delete: (id) => request(`/incidents/${id}`, { method: "DELETE" }),
};

// ----------------------------------------------------------
// Assets
// ----------------------------------------------------------
export const assetsApi = {
  list: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/assets${qs ? "?" + qs : ""}`);
  },
  get: (id) => request(`/assets/${id}`),
  create: (data) => request("/assets", { method: "POST", body: JSON.stringify(data) }),
  update: (id, data) => request(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  toggleMaintenance: (id, enable, until = null) =>
    request(`/assets/${id}/maintenance?enable=${enable}${until ? "&until=" + until : ""}`, {
      method: "POST",
    }),
  getAlerts: (id) => request(`/assets/${id}/alerts`),
  delete: (id) => request(`/assets/${id}`, { method: "DELETE" }),
};

// ----------------------------------------------------------
// Playbooks
// ----------------------------------------------------------
export const playbooksApi = {
  list: () => request("/playbooks"),
  run: (data) => request("/playbooks/run", { method: "POST", body: JSON.stringify(data) }),
  confirmIsolation: (alertId) =>
    request(`/playbooks/confirm-isolation/${alertId}?confirmed=true`, { method: "POST" }),
  blockIp: (ip) => request(`/playbooks/block-ip?ip=${ip}`, { method: "POST" }),
};

// ----------------------------------------------------------
// Système
// ----------------------------------------------------------
export const systemApi = {
  health: () => request("/health".replace("/api/v1", "")),
  status: () => request("/status"),
};

// ----------------------------------------------------------
// Règles Wazuh
// ----------------------------------------------------------
export const rulesApi = {
  list: () => request("/rules"),
};

// ----------------------------------------------------------
// Investigation OSINT
// ----------------------------------------------------------
export const investigationApi = {
  /**
   * Lance une investigation complète sur une IP suspecte.
   * Retourne : géo, AbuseIPDB, VirusTotal, RDAP, historique interne, profil attaque, risque.
   */
  investigate: (ip) => request(`/investigate/${encodeURIComponent(ip)}`),
};
