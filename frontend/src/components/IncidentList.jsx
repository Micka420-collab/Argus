import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, AlertTriangle, Clock, CheckCircle, X } from "lucide-react";
import { incidentsApi } from "../services/api";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

const SEVERITY_STYLES = {
  critical: "bg-red-900/50 text-red-300 border-red-700",
  high:     "bg-orange-900/50 text-orange-300 border-orange-700",
  medium:   "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  low:      "bg-green-900/50 text-green-300 border-green-700",
};

const STATUS_STYLES = {
  open:          "text-blue-400",
  investigating: "text-yellow-400",
  contained:     "text-orange-400",
  eradicated:    "text-purple-400",
  recovered:     "text-teal-400",
  closed:        "text-slate-400",
};

function CreateIncidentModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: "", description: "", severity: "medium", category: "other",
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const inc = await incidentsApi.create(form);
      onCreated(inc);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b border-slate-700">
          <h2 className="text-white font-semibold">Nouvel incident</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X size={20} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-slate-400 text-sm mb-1">Titre *</label>
            <input
              type="text"
              required
              value={form.title}
              onChange={e => setForm(p => ({ ...p, title: e.target.value }))}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Description</label>
            <textarea
              rows={3}
              value={form.description}
              onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-400 text-sm mb-1">Sévérité</label>
              <select
                value={form.severity}
                onChange={e => setForm(p => ({ ...p, severity: e.target.value }))}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="critical">Critique</option>
                <option value="high">Haute</option>
                <option value="medium">Moyenne</option>
                <option value="low">Basse</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Catégorie</label>
              <select
                value={form.category}
                onChange={e => setForm(p => ({ ...p, category: e.target.value }))}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="malware">Malware</option>
                <option value="ransomware">Ransomware</option>
                <option value="phishing">Phishing</option>
                <option value="data_breach">Fuite de données</option>
                <option value="brute_force">Brute force</option>
                <option value="insider_threat">Menace interne</option>
                <option value="other">Autre</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-500 disabled:opacity-50"
            >
              {saving ? "Création..." : "Créer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function IncidentList() {
  const navigate = useNavigate();
  const [incidents, setIncidents] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");

  const fetchIncidents = async () => {
    setLoading(true);
    try {
      const params = statusFilter ? { status: statusFilter } : {};
      const result = await incidentsApi.list(params);
      setIncidents(result.items || []);
      setTotal(result.total || 0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchIncidents(); }, [statusFilter]);

  const openCount = incidents.filter(i => !["closed", "recovered"].includes(i.status)).length;

  return (
    <div className="p-6 space-y-5">
      {showCreate && (
        <CreateIncidentModal
          onClose={() => setShowCreate(false)}
          onCreated={(inc) => setIncidents(prev => [inc, ...prev])}
        />
      )}

      {/* En-tête */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Incidents</h1>
          <p className="text-slate-400 text-sm mt-1">{openCount} ouverts · {total} total</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors"
        >
          <Plus size={16} /> Créer incident
        </button>
      </div>

      {/* Filtres statut */}
      <div className="flex gap-2">
        {["", "open", "investigating", "contained", "closed"].map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 text-sm rounded-lg capitalize transition-colors ${
              statusFilter === s
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700"
            }`}
          >
            {s || "Tous"}
          </button>
        ))}
      </div>

      {/* Liste incidents */}
      <div className="space-y-3">
        {loading ? (
          <div className="text-center py-12 text-slate-400">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3" />
            Chargement...
          </div>
        ) : incidents.length === 0 ? (
          <div className="text-center py-12 text-slate-400 bg-slate-800 rounded-xl border border-slate-700">
            Aucun incident
          </div>
        ) : incidents.map(inc => (
          <div
            key={inc.id}
            onClick={() => navigate(`/incidents/${inc.id}`)}
            className="bg-slate-800 rounded-xl border border-slate-700 p-5 cursor-pointer hover:border-slate-500 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className={`text-xs font-semibold px-2 py-1 rounded-full border ${SEVERITY_STYLES[inc.severity]}`}>
                    {inc.severity?.toUpperCase()}
                  </span>
                  <span className={`text-sm font-medium ${STATUS_STYLES[inc.status]}`}>
                    {inc.status?.replace("_", " ")}
                  </span>
                  <span className="text-xs text-slate-500">{inc.category?.replace("_", " ")}</span>
                </div>
                <h3 className="text-white font-semibold">{inc.title}</h3>
                {inc.description && (
                  <p className="text-slate-400 text-sm mt-1 line-clamp-2">{inc.description}</p>
                )}
                <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                  <span>{inc.alert_ids?.length || 0} alertes liées</span>
                  {inc.assigned_to && <span>→ {inc.assigned_to}</span>}
                  {inc.opened_at && (
                    <span>
                      Ouvert {formatDistanceToNow(new Date(inc.opened_at), { addSuffix: true, locale: fr })}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
