import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Filter, RefreshCw, AlertCircle, CheckCircle, Clock } from "lucide-react";
import { alertsApi } from "../services/api";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

const SEVERITY_STYLES = {
  critical: "bg-red-900/50 text-red-300 border border-red-700",
  high:     "bg-orange-900/50 text-orange-300 border border-orange-700",
  medium:   "bg-yellow-900/50 text-yellow-300 border border-yellow-700",
  low:      "bg-green-900/50 text-green-300 border border-green-700",
};

const STATUS_ICONS = {
  new:            <AlertCircle size={14} className="text-blue-400" />,
  in_progress:    <Clock size={14} className="text-yellow-400" />,
  resolved:       <CheckCircle size={14} className="text-green-400" />,
  false_positive: <CheckCircle size={14} className="text-slate-400" />,
};

function getSeverity(level) {
  if (level >= 14) return "critical";
  if (level >= 10) return "high";
  if (level >= 7)  return "medium";
  return "low";
}

export default function AlertList({ newAlerts }) {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    q: "", severity: "", status: "", agent_name: "",
  });

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, per_page: 50 };
      if (filters.q)          params.q = filters.q;
      if (filters.severity)   params.severity = filters.severity;
      if (filters.status)     params.status = filters.status;
      if (filters.agent_name) params.agent_name = filters.agent_name;

      const result = await alertsApi.list(params);
      setAlerts(result.items || []);
      setTotal(result.total || 0);
    } catch (e) {
      console.error("Erreur chargement alertes:", e);
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => { fetchAlerts(); }, [fetchAlerts]);

  // Ajouter les nouvelles alertes en tête de liste
  useEffect(() => {
    if (newAlerts && newAlerts.length > 0) {
      setAlerts(prev => {
        const newIds = new Set(newAlerts.map(a => a.id));
        const filtered = prev.filter(a => !newIds.has(a.id));
        return [...newAlerts, ...filtered];
      });
    }
  }, [newAlerts]);

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({ ...prev, [field]: value }));
    setPage(1);
  };

  return (
    <div className="p-6 space-y-5">
      {/* En-tête */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Alertes</h1>
          <p className="text-slate-400 text-sm mt-1">{total} alertes trouvées</p>
        </div>
        <button
          onClick={fetchAlerts}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
        >
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          Actualiser
        </button>
      </div>

      {/* Filtres */}
      <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Rechercher..."
              value={filters.q}
              onChange={e => handleFilterChange("q", e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm placeholder-slate-400 focus:outline-none focus:border-blue-500"
            />
          </div>

          <select
            value={filters.severity}
            onChange={e => handleFilterChange("severity", e.target.value)}
            className="py-2 px-3 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="">Toutes sévérités</option>
            <option value="critical">Critique</option>
            <option value="high">Haute</option>
            <option value="medium">Moyenne</option>
            <option value="low">Basse</option>
          </select>

          <select
            value={filters.status}
            onChange={e => handleFilterChange("status", e.target.value)}
            className="py-2 px-3 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="">Tous statuts</option>
            <option value="new">Nouveau</option>
            <option value="in_progress">En cours</option>
            <option value="resolved">Résolu</option>
            <option value="false_positive">Faux positif</option>
          </select>

          <input
            type="text"
            placeholder="Nom machine..."
            value={filters.agent_name}
            onChange={e => handleFilterChange("agent_name", e.target.value)}
            className="py-2 px-3 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm placeholder-slate-400 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Table des alertes */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-900/50">
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Sévérité</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Description</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Machine</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">IP Source</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">MITRE</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Statut</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Temps</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {loading && alerts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-400">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto mb-2" />
                    Chargement...
                  </td>
                </tr>
              ) : alerts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-400">
                    Aucune alerte trouvée
                  </td>
                </tr>
              ) : (
                alerts.map((alert) => {
                  const level = alert.rule?.level || 0;
                  const severity = getSeverity(level);
                  const mitreIds = alert.rule?.mitre?.id || [];
                  const status = alert.status || "new";
                  const ts = alert.timestamp ? new Date(alert.timestamp) : null;

                  return (
                    <tr
                      key={alert.id}
                      onClick={() => navigate(`/alerts/${alert.id}`)}
                      className="hover:bg-slate-700/50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${SEVERITY_STYLES[severity]}`}>
                          {severity.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-200 max-w-xs truncate">
                        {alert.rule?.description || "N/A"}
                      </td>
                      <td className="px-4 py-3 text-slate-300">
                        {alert.agent?.name || "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                        {alert.data?.srcip || alert.src_ip || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {mitreIds.slice(0, 2).map(id => (
                            <span key={id} className="text-xs bg-purple-900/50 text-purple-300 border border-purple-700 px-1.5 py-0.5 rounded">
                              {id}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          {STATUS_ICONS[status]}
                          <span className="text-slate-300 text-xs capitalize">
                            {status.replace("_", " ")}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        {ts ? formatDistanceToNow(ts, { addSuffix: true, locale: fr }) : "—"}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 50 && (
          <div className="px-4 py-3 border-t border-slate-700 flex items-center justify-between">
            <span className="text-slate-400 text-sm">
              Page {page} — {Math.min(page * 50, total)} / {total}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
                className="px-3 py-1.5 text-sm bg-slate-700 text-slate-300 rounded-lg disabled:opacity-50 hover:bg-slate-600"
              >
                Précédent
              </button>
              <button
                disabled={page * 50 >= total}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 text-sm bg-slate-700 text-slate-300 rounded-lg disabled:opacity-50 hover:bg-slate-600"
              >
                Suivant
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
