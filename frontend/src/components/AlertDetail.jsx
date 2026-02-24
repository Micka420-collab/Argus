import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Shield, Server, Globe, Clock, Tag,
  CheckCircle, AlertTriangle, Zap, ExternalLink, Search
} from "lucide-react";
import { alertsApi, incidentsApi } from "../services/api";
import { format } from "date-fns";
import { fr } from "date-fns/locale";

function InfoRow({ label, value, mono }) {
  if (!value) return null;
  return (
    <div className="flex justify-between py-2 border-b border-slate-700/50 last:border-0">
      <span className="text-slate-400 text-sm">{label}</span>
      <span className={`text-slate-200 text-sm ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

function RiskBadge({ score }) {
  if (score == null) return null;
  const color = score >= 90 ? "red" : score >= 60 ? "orange" : score >= 30 ? "yellow" : "green";
  const classes = {
    red:    "bg-red-900/50 text-red-300 border-red-700",
    orange: "bg-orange-900/50 text-orange-300 border-orange-700",
    yellow: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
    green:  "bg-green-900/50 text-green-300 border-green-700",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm font-bold px-3 py-1.5 rounded-lg border ${classes[color]}`}>
      <Shield size={14} />
      Score risque: {score}/100
    </span>
  );
}

export default function AlertDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [note, setNote] = useState("");
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    const fetchAlert = async () => {
      setLoading(true);
      try {
        const data = await alertsApi.get(id);
        setAlert(data);
      } catch (e) {
        console.error("Erreur chargement alerte:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchAlert();
  }, [id]);

  const handleEnrich = async () => {
    setEnriching(true);
    try {
      await alertsApi.enrich(id);
      setTimeout(async () => {
        const updated = await alertsApi.get(id);
        setAlert(updated);
        setEnriching(false);
      }, 3000);
    } catch (e) {
      setEnriching(false);
    }
  };

  const handleStatusChange = async (status) => {
    setUpdating(true);
    try {
      await alertsApi.update(id, { status });
      setAlert(prev => ({ ...prev, status }));
    } finally {
      setUpdating(false);
    }
  };

  const handleMarkFP = async () => {
    if (!window.confirm("Marquer cette alerte comme faux positif ?")) return;
    await alertsApi.markFalsePositive(id, note);
    setAlert(prev => ({ ...prev, status: "false_positive" }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!alert) {
    return (
      <div className="p-6 text-center text-slate-400">
        Alerte introuvable
        <button onClick={() => navigate(-1)} className="block mx-auto mt-4 text-blue-400 hover:underline">
          ← Retour
        </button>
      </div>
    );
  }

  const rule = alert.rule || {};
  const agent = alert.agent || {};
  const enrichment = alert.enrichment || {};
  const srcIp = alert.data?.srcip || alert.src_ip;
  const mitreIds = rule.mitre?.id || [];
  const ts = alert.timestamp ? format(new Date(alert.timestamp), "dd/MM/yyyy HH:mm:ss", { locale: fr }) : "N/A";

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Navigation */}
      <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
        <ArrowLeft size={16} /> Retour aux alertes
      </button>

      {/* En-tête */}
      <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white mb-2">
              {rule.description || "Alerte sans description"}
            </h1>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-mono text-slate-400">ID: {id}</span>
              <span className="text-xs text-slate-400">
                <Clock size={12} className="inline mr-1" />{ts}
              </span>
              <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                rule.level >= 14 ? "bg-red-900/50 text-red-300 border border-red-700" :
                rule.level >= 10 ? "bg-orange-900/50 text-orange-300 border border-orange-700" :
                "bg-yellow-900/50 text-yellow-300 border border-yellow-700"
              }`}>
                Niveau {rule.level}/15
              </span>
              {alert.status && (
                <span className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded-full capitalize">
                  {alert.status.replace("_", " ")}
                </span>
              )}
            </div>
          </div>
          {enrichment.risk_score != null && <RiskBadge score={enrichment.risk_score} />}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Informations règle */}
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Shield size={16} className="text-blue-400" /> Règle
          </h2>
          <InfoRow label="ID règle" value={rule.id} mono />
          <InfoRow label="Niveau" value={`${rule.level}/15`} />
          <InfoRow label="Groupes" value={rule.groups?.join(", ")} />
          {mitreIds.length > 0 && (
            <div className="py-2 border-b border-slate-700/50">
              <span className="text-slate-400 text-sm block mb-2">MITRE ATT&CK</span>
              <div className="flex flex-wrap gap-2">
                {mitreIds.map(id => (
                  <a
                    key={id}
                    href={`https://attack.mitre.org/techniques/${id.replace(".", "/")}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs bg-purple-900/50 text-purple-300 border border-purple-700 px-2 py-1 rounded hover:bg-purple-800/50"
                  >
                    {id} <ExternalLink size={10} />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Machine concernée */}
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Server size={16} className="text-green-400" /> Machine
          </h2>
          <InfoRow label="Nom" value={agent.name} />
          <InfoRow label="ID agent" value={agent.id} mono />
          <InfoRow label="IP agent" value={agent.ip} mono />
          <InfoRow label="OS" value={agent.os} />
        </div>

        {/* Enrichissement IP */}
        {srcIp && (
          <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-white font-semibold flex items-center gap-2">
                <Globe size={16} className="text-orange-400" /> IP Source: {srcIp}
              </h2>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate(`/investigate/${srcIp}`)}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-purple-700 text-white rounded-lg hover:bg-purple-600 font-medium"
                  title="Lancer une investigation OSINT complète sur cette IP"
                >
                  <Search size={12} /> Investiguer
                </button>
                <button
                  onClick={handleEnrich}
                  disabled={enriching}
                  className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:opacity-50"
                >
                  {enriching ? "..." : "Enrichir"}
                </button>
              </div>
            </div>
            {enrichment.abuseipdb && (
              <>
                <InfoRow label="Score AbuseIPDB" value={`${enrichment.abuseipdb.abuse_score}/100`} />
                <InfoRow label="Pays" value={enrichment.abuseipdb.country} />
                <InfoRow label="ISP" value={enrichment.abuseipdb.isp} />
                <InfoRow label="Signalements" value={enrichment.abuseipdb.reports?.toString()} />
                <InfoRow label="Nœud Tor" value={enrichment.abuseipdb.is_tor ? "Oui" : "Non"} />
              </>
            )}
            {enrichment.virustotal && (
              <>
                <InfoRow label="VT Malveillant" value={`${enrichment.virustotal.malicious} moteurs`} />
                <InfoRow label="VT Suspect" value={`${enrichment.virustotal.suspicious} moteurs`} />
              </>
            )}
            {!enrichment.abuseipdb && !enrichment.virustotal && (
              <p className="text-slate-400 text-sm">Aucun enrichissement disponible — cliquer sur "Enrichir"</p>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Zap size={16} className="text-yellow-400" /> Actions
          </h2>
          <div className="space-y-3">
            <div className="flex gap-2">
              <button
                onClick={() => handleStatusChange("in_progress")}
                disabled={updating}
                className="flex-1 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-500 disabled:opacity-50"
              >
                Prendre en charge
              </button>
              <button
                onClick={() => handleStatusChange("resolved")}
                disabled={updating}
                className="flex-1 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-500 disabled:opacity-50"
              >
                Résoudre
              </button>
            </div>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Note / commentaire..."
              rows={2}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm placeholder-slate-400 focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={handleMarkFP}
              className="w-full py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600 border border-slate-600"
            >
              Marquer faux positif
            </button>
          </div>
        </div>
      </div>

      {/* Données brutes */}
      <details className="bg-slate-800 rounded-xl border border-slate-700">
        <summary className="px-5 py-4 text-white font-semibold cursor-pointer hover:bg-slate-700/50 rounded-xl">
          Données brutes (JSON)
        </summary>
        <div className="px-5 pb-5">
          <pre className="text-xs text-slate-300 bg-slate-900 rounded-lg p-4 overflow-auto max-h-64 font-mono">
            {JSON.stringify(alert, null, 2)}
          </pre>
        </div>
      </details>
    </div>
  );
}
