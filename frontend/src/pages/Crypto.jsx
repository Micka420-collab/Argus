/**
 * Page Posture Post-Quantique (pilier CryptoNext)
 * ------------------------------------------------
 * Auto-évaluation crypto-agility de la plateforme + CBOM observé (TLS).
 */
import { useState, useEffect } from "react";
import {
  ShieldCheck, ShieldAlert, HelpCircle, Lock, KeyRound, FileText,
  Cpu, RefreshCw, Atom, AlertTriangle,
} from "lucide-react";
import { cryptoApi } from "../services/api";

// ---------------------------------------------------------------------------
// Jauge circulaire de readiness (SVG)
// ---------------------------------------------------------------------------
function ReadinessGauge({ score, grade }) {
  const circumference = 2 * Math.PI * 52;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 75 ? "#22c55e" : score >= 60 ? "#84cc16" :
    score >= 45 ? "#eab308" : score >= 25 ? "#f97316" : "#ef4444";
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-40 h-40">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="52" fill="none" stroke="#1e293b" strokeWidth="10" />
          <circle
            cx="60" cy="60" r="52" fill="none" stroke={color} strokeWidth="10"
            strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 1s ease-in-out", filter: `drop-shadow(0 0 6px ${color}80)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold text-white">{score}</span>
          <span className="text-xs text-slate-400">/100</span>
        </div>
      </div>
      <span className="mt-2 text-2xl font-bold" style={{ color }}>{grade}</span>
      <span className="text-xs text-slate-400">Readiness PQC</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Badge de statut crypto
// ---------------------------------------------------------------------------
const STATUS = {
  safe:       { label: "Sûr",        cls: "bg-green-500/15 text-green-300 border-green-500/40" },
  hybrid:     { label: "Hybride PQC", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" },
  weak:       { label: "Faible",     cls: "bg-yellow-500/15 text-yellow-300 border-yellow-500/40" },
  vulnerable: { label: "Vulnérable", cls: "bg-orange-500/15 text-orange-300 border-orange-500/40" },
  broken:     { label: "Cassé",      cls: "bg-red-500/15 text-red-300 border-red-500/40" },
  unknown:    { label: "Inconnu",    cls: "bg-slate-700 text-slate-300 border-slate-600" },
};

const KIND_ICON = {
  kex: KeyRound, signature: FileText, symmetric: Lock, hash: Cpu, token: ShieldCheck,
};

function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.unknown;
  return <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${s.cls}`}>{s.label}</span>;
}

function ComponentRow({ c }) {
  const Icon = KIND_ICON[c.kind] || HelpCircle;
  return (
    <div className="flex items-start gap-3 py-3 border-b border-slate-700/30 last:border-0">
      <Icon size={16} className="text-slate-400 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-slate-200 text-sm font-medium">{c.name}</span>
          <StatusBadge status={c.status} />
        </div>
        <p className="text-slate-400 text-xs font-mono mt-0.5 truncate">{c.value}</p>
        {c.note && <p className="text-slate-500 text-xs mt-1">{c.note}</p>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page principale
// ---------------------------------------------------------------------------
export default function Crypto() {
  const [readiness, setReadiness] = useState(null);
  const [cbom, setCbom]           = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, c] = await Promise.all([
        cryptoApi.readiness(),
        cryptoApi.inventory(24).catch(() => null),
      ]);
      setReadiness(r);
      setCbom(c);
    } catch (e) {
      setError(e.message || "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-14 h-14 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
        <p className="text-slate-400 text-sm">Évaluation de la posture cryptographique…</p>
      </div>
    );
  }

  if (error || !readiness) {
    return (
      <div className="p-6 text-center">
        <AlertTriangle size={40} className="text-red-400 mx-auto mb-3" />
        <p className="text-white font-semibold">Impossible de charger la posture crypto</p>
        <p className="text-slate-400 text-sm mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">

      {/* En-tête */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Atom size={22} className="text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Posture Post-Quantique</h1>
            <p className="text-slate-400 text-sm">Crypto-agility & inventaire (CBOM) — pilier CryptoNext</p>
          </div>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 text-indigo-300 hover:text-indigo-200 text-sm bg-indigo-500/10 border border-indigo-500/30 rounded-lg px-3 py-1.5"
        >
          <RefreshCw size={14} /> Actualiser
        </button>
      </div>

      {/* Carte readiness */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800/80 border border-slate-700/50 rounded-2xl p-6">
        <div className="flex flex-col lg:flex-row items-center gap-8">
          <ReadinessGauge score={readiness.readiness_score} grade={readiness.grade} />
          <div className="flex-1">
            <h3 className="text-white font-semibold text-sm mb-2">Synthèse</h3>
            <p className="text-slate-300 text-sm leading-relaxed">{readiness.summary}</p>
            <p className="text-slate-500 text-xs mt-3">
              Évalué le {new Date(readiness.timestamp).toLocaleString("fr-FR")}
            </p>
          </div>
        </div>
      </div>

      {/* Composants évalués */}
      <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-5">
        <h3 className="text-white font-semibold text-sm mb-2 flex items-center gap-2">
          <ShieldAlert size={15} className="text-indigo-400" />
          Composants cryptographiques déclarés
        </h3>
        <div>
          {readiness.components.map((c, i) => <ComponentRow key={i} c={c} />)}
        </div>
      </div>

      {/* CBOM observé */}
      <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-5">
        <h3 className="text-white font-semibold text-sm mb-4 flex items-center gap-2">
          <KeyRound size={15} className="text-green-400" />
          CBOM observé — handshakes TLS (24h)
        </h3>

        {!cbom || cbom.source === "unavailable" ? (
          <p className="text-slate-500 text-sm">
            Aucune donnée TLS observée (Suricata/OpenSearch indisponible). L'auto-évaluation
            ci-dessus reste valable.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
              {[
                { label: "Sessions vues",  value: cbom.sessions_seen, color: "text-slate-200" },
                { label: "Hybride PQC",    value: cbom.hybrid,        color: "text-emerald-400" },
                { label: "Quantum-safe",   value: cbom.quantum_safe,  color: "text-green-400" },
                { label: "Vulnérables",    value: cbom.vulnerable,    color: "text-orange-400" },
              ].map(({ label, value, color }, i) => (
                <div key={i} className="bg-slate-800/60 rounded-xl p-3 text-center">
                  <div className={`text-2xl font-bold ${color}`}>{value}</div>
                  <div className="text-slate-500 text-xs mt-0.5">{label}</div>
                </div>
              ))}
            </div>

            {Object.keys(cbom.by_tls_version || {}).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(cbom.by_tls_version).map(([ver, cnt]) => (
                  <span key={ver} className="text-xs bg-slate-800 text-slate-300 px-2.5 py-1 rounded-full font-mono">
                    {ver} · {cnt}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
      </div>

    </div>
  );
}
