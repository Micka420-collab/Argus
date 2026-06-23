/**
 * Service API — Centralise tous les appels HTTP vers le backend FastAPI
 */

const BASE_URL = process.env.REACT_APP_API_URL || "/api/v1";

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const token = (typeof localStorage !== "undefined") ? localStorage.getItem("soc_token") : null;
  const { headers: optHeaders, ...rest } = options;
  const config = {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...optHeaders,
    },
    ...rest,
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
// Investigation OSINT (+ verdict IA borné)
// ----------------------------------------------------------
export const investigationApi = {
  /**
   * Lance une investigation complète sur une IP suspecte.
   * Retourne : géo, AbuseIPDB, VirusTotal, RDAP, historique interne, profil
   * attaque, verdict déterministe (risk.verdict/confidence) et analyse IA (ai).
   * @param {string} ip
   * @param {boolean} refresh - ignore le cache et relance une analyse fraîche
   */
  investigate: (ip, refresh = false) =>
    request(`/investigate/${encodeURIComponent(ip)}${refresh ? "?refresh=true" : ""}`),
};

// ----------------------------------------------------------
// Analyste IA autonome (pilier Qevlar)
// ----------------------------------------------------------
export const aiApi = {
  /** Liste des investigations autonomes (filtrable par verdict). */
  reports: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/ai/reports${qs ? "?" + qs : ""}`);
  },
  /** Détail d'un rapport (état + trace du graphe). */
  report: (id) => request(`/ai/report/${encodeURIComponent(id)}`),
  /** Déclenche l'agent autonome sur une alerte. */
  investigateAlert: (alertId) =>
    request(`/ai/investigate/${encodeURIComponent(alertId)}`, { method: "POST" }),
  /** Déclenche l'agent autonome sur une IP. */
  investigateIp: (ip) =>
    request(`/ai/investigate-ip/${encodeURIComponent(ip)}`, { method: "POST" }),
  /** Feedback analyste (corriger/valider un verdict → RAG). */
  feedback: (id, correctedVerdict, rationale = "") =>
    request(
      `/ai/feedback/${encodeURIComponent(id)}?corrected_verdict=${encodeURIComponent(correctedVerdict)}&rationale=${encodeURIComponent(rationale)}`,
      { method: "POST" }
    ),
};

// ----------------------------------------------------------
// VDP / Bug-Bounty (pilier YesWeHack)
// ----------------------------------------------------------
export const vdpApi = {
  submit: (data) => request("/vdp/reports", { method: "POST", body: JSON.stringify(data) }),
  list: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/vdp/reports${qs ? "?" + qs : ""}`);
  },
  get: (id) => request(`/vdp/reports/${encodeURIComponent(id)}`),
  setStatus: (id, status, note = "") =>
    request(`/vdp/reports/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, note }),
    }),
  programs: () => request("/vdp/programs"),
  cvss: (vector) => request(`/vdp/cvss?vector=${encodeURIComponent(vector)}`),
  stats: () => request("/vdp/stats"),
};

// ----------------------------------------------------------
// ASM / CTEM — surface d'exposition
// ----------------------------------------------------------
export const exposureApi = {
  findings: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/exposure/findings${qs ? "?" + qs : ""}`);
  },
  addFinding: (data) => request("/exposure/findings", { method: "POST", body: JSON.stringify(data) }),
  setStatus: (id, status) =>
    request(`/exposure/findings/${encodeURIComponent(id)}/status`, {
      method: "PATCH", body: JSON.stringify({ status }),
    }),
  assets: () => request("/exposure/assets"),
  upsertAsset: (data) => request("/exposure/assets", { method: "POST", body: JSON.stringify(data) }),
  cve: (cve) => request(`/exposure/cve/${encodeURIComponent(cve)}`),
  stats: () => request("/exposure/stats"),
};

// ----------------------------------------------------------
// Posture post-quantique (pilier CryptoNext)
// ----------------------------------------------------------
export const cryptoApi = {
  /** Auto-évaluation de la crypto déclarée d'Argus (TLS, certificat, JWT). */
  readiness: () => request("/crypto/readiness"),
  /** CBOM observé : inventaire des handshakes TLS vus par Suricata. */
  inventory: (periodHours = 24) => request(`/crypto/inventory?period_hours=${periodHours}`),
};
