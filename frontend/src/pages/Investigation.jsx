/**
 * Page Investigation OSINT
 * Analyse complète d'une IP suspecte : identité, réputation, type d'attaque, actions
 */
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, Search, Globe, Shield, AlertTriangle, Server,
  MapPin, Building2, Wifi, Clock, Activity, ExternalLink,
  CheckCircle, XCircle, HelpCircle, Zap, Eye,
  Brain, Sparkles, RefreshCw, ShieldCheck, ShieldAlert,
} from "lucide-react";
import { investigationApi } from "../services/api";
import { format, formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

// ---------------------------------------------------------------------------
// Score de risque — jauge circulaire SVG
// ---------------------------------------------------------------------------
function RiskGauge({ score, level }) {
  const circumference = 2 * Math.PI * 52;
  const offset = circumference - (score / 100) * circumference;
  const colors = {
    critical: "#ef4444",
    high:     "#f97316",
    medium:   "#eab308",
    low:      "#22c55e",
  };
  const color = colors[level] || "#64748b";
  const labels = {
    critical: "CRITIQUE", high: "ÉLEVÉ", medium: "MODÉRÉ", low: "FAIBLE"
  };

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-36 h-36">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
          {/* Piste de fond */}
          <circle cx="60" cy="60" r="52" fill="none" stroke="#1e293b" strokeWidth="10" />
          {/* Arc coloré */}
          <circle
            cx="60" cy="60" r="52"
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 1s ease-in-out", filter: `drop-shadow(0 0 6px ${color}80)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-white">{score}</span>
          <span className="text-xs text-slate-400">/100</span>
        </div>
      </div>
      <span className="mt-2 text-sm font-bold" style={{ color }}>{labels[level] || level}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Badge sévérité
// ---------------------------------------------------------------------------
function SeverityBadge({ level }) {
  const styles = {
    critical: "bg-red-900/50 text-red-300 border-red-700",
    high:     "bg-orange-900/50 text-orange-300 border-orange-700",
    medium:   "bg-yellow-900/50 text-yellow-300 border-yellow-700",
    low:      "bg-green-900/50 text-green-300 border-green-700",
    unknown:  "bg-slate-700 text-slate-300 border-slate-600",
  };
  const labels = { critical: "Critique", high: "Élevé", medium: "Modéré", low: "Faible" };
  return (
    <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${styles[level] || styles.unknown}`}>
      {labels[level] || level}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Verdict 3 états (façon Qevlar) — malicious / benign / inconclusive
// ---------------------------------------------------------------------------
function VerdictBadge({ verdict, confidence }) {
  const map = {
    malicious:    { label: "MALVEILLANT",  icon: ShieldAlert, cls: "bg-red-500/15 text-red-300 border-red-500/40" },
    benign:       { label: "BÉNIN",        icon: ShieldCheck, cls: "bg-green-500/15 text-green-300 border-green-500/40" },
    inconclusive: { label: "INDÉTERMINÉ",  icon: HelpCircle,  cls: "bg-yellow-500/15 text-yellow-300 border-yellow-500/40" },
  };
  const m = map[verdict] || map.inconclusive;
  const Icon = m.icon;
  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border ${m.cls}`}>
      <Icon size={18} />
      <div className="flex flex-col leading-tight">
        <span className="text-sm font-bold">{m.label}</span>
        {typeof confidence === "number" && (
          <span className="text-[10px] opacity-80">confiance {confidence}%</span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Carte info générique glassmorphism
// ---------------------------------------------------------------------------
function InfoCard({ title, icon: Icon, iconColor = "text-blue-400", children }) {
  return (
    <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-5">
      <h3 className="text-white font-semibold text-sm mb-4 flex items-center gap-2">
        <Icon size={15} className={iconColor} />
        {title}
      </h3>
      {children}
    </div>
  );
}

function Row({ label, value, mono, badge }) {
  if (value === undefined || value === null || value === "") return null;
  return (
    <div className="flex justify-between items-center py-2 border-b border-slate-700/30 last:border-0">
      <span className="text-slate-400 text-xs">{label}</span>
      {badge ? (
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badge}`}>{value}</span>
      ) : (
        <span className={`text-slate-200 text-xs text-right max-w-[200px] ${mono ? "font-mono" : ""}`}>
          {value}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Type d'attaque → icône + libellé
// ---------------------------------------------------------------------------
function AttackTypeBadge({ type }) {
  const map = {
    ddos:       { label: "🌊 DDoS",          color: "bg-red-500/20 text-red-300 border-red-500/40" },
    bruteforce: { label: "🔨 Brute Force",   color: "bg-orange-500/20 text-orange-300 border-orange-500/40" },
    portscan:   { label: "🔍 Port Scan",     color: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40" },
    exploit:    { label: "💥 Exploit",       color: "bg-purple-500/20 text-purple-300 border-purple-500/40" },
    webattack:  { label: "🕷️ Web Attack",   color: "bg-pink-500/20 text-pink-300 border-pink-500/40" },
    unknown:    { label: "❓ Indéterminé",   color: "bg-slate-700 text-slate-300 border-slate-600" },
  };
  const m = map[type] || map.unknown;
  return (
    <span className={`inline-flex items-center px-3 py-1.5 rounded-xl border text-sm font-semibold ${m.color}`}>
      {m.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Indicateur proxy/VPN/Datacenter
// ---------------------------------------------------------------------------
function HostingBadges({ geo }) {
  const badges = [];
  if (geo.is_proxy)   badges.push({ label: "Proxy/VPN/Tor", color: "text-red-400 bg-red-400/10" });
  if (geo.is_hosting) badges.push({ label: "Datacenter",    color: "text-orange-400 bg-orange-400/10" });
  if (geo.is_mobile)  badges.push({ label: "Mobile",        color: "text-blue-400 bg-blue-400/10" });
  if (!badges.length) badges.push({ label: "Résidentiel",   color: "text-green-400 bg-green-400/10" });
  return (
    <div className="flex flex-wrap gap-2">
      {badges.map((b, i) => (
        <span key={i} className={`text-xs px-2.5 py-1 rounded-full font-medium ${b.color}`}>{b.label}</span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drapeau pays (emoji)
// ---------------------------------------------------------------------------
function countryFlag(code) {
  if (!code) return "🌐";
  return code.toUpperCase().replace(/./g, c =>
    String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65)
  );
}

// ---------------------------------------------------------------------------
// Page principale
// ---------------------------------------------------------------------------
export default function Investigation() {
  const { ip }       = useParams();
  const navigate     = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [blocking, setBlocking] = useState(false);
  const [blocked, setBlocked]   = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await investigationApi.investigate(ip, true);
      setReport(data);
    } catch (e) {
      setError(e.message || "Erreur lors de la ré-analyse");
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await investigationApi.investigate(ip);
        setReport(data);
      } catch (e) {
        setError(e.message || "Erreur lors de l'investigation");
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [ip]);

  const handleBlockIp = async () => {
    if (!window.confirm(`Bloquer définitivement ${ip} sur toute l'infrastructure ?`)) return;
    setBlocking(true);
    try {
      await fetch(`/api/v1/playbooks/block-ip?ip=${ip}`, { method: "POST" });
      setBlocked(true);
    } catch (e) {
      alert("Erreur lors du blocage : " + e.message);
    } finally {
      setBlocking(false);
    }
  };

  // ---- Chargement ----
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <div className="relative">
          <div className="w-16 h-16 rounded-full border-2 border-blue-500/30 animate-ping absolute inset-0" />
          <div className="w-16 h-16 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
        </div>
        <div className="text-center">
          <p className="text-white font-semibold">Investigation en cours…</p>
          <p className="text-slate-400 text-sm mt-1">
            Interrogation de AbuseIPDB, VirusTotal, RDAP, ip-api.com
          </p>
          <p className="text-slate-500 text-xs mt-1">IP cible : <span className="font-mono text-blue-400">{ip}</span></p>
        </div>
      </div>
    );
  }

  // ---- Erreur ----
  if (error || !report) {
    return (
      <div className="p-6 text-center">
        <XCircle size={48} className="text-red-400 mx-auto mb-3" />
        <p className="text-white font-semibold">Investigation échouée</p>
        <p className="text-slate-400 text-sm mt-1">{error}</p>
        <button onClick={() => navigate(-1)} className="mt-4 text-blue-400 hover:underline text-sm">
          ← Retour
        </button>
      </div>
    );
  }

  const { geo, abuse, virustotal: vt, attack_profile: profile, risk, raw_rdap } = report;

  // Extraire le contact d'abus depuis RDAP
  let abuseContact = "";
  try {
    const entities = raw_rdap?.entities || [];
    for (const e of entities) {
      if (e.roles?.includes("abuse")) {
        abuseContact = e.vcardArray?.[1]?.find(v => v[0] === "email")?.[3] || "";
        break;
      }
    }
  } catch (_) {}

  // Formatage des dates
  const fmtDate = (s) => {
    if (!s) return "—";
    try { return format(new Date(s), "dd/MM/yyyy HH:mm", { locale: fr }); }
    catch { return s; }
  };
  const fmtAgo = (s) => {
    if (!s) return "";
    try { return formatDistanceToNow(new Date(s), { addSuffix: true, locale: fr }); }
    catch { return ""; }
  };

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm"
        >
          <ArrowLeft size={15} /> Retour
        </button>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 text-indigo-300 hover:text-indigo-200 disabled:opacity-50 transition-colors text-sm bg-indigo-500/10 border border-indigo-500/30 rounded-lg px-3 py-1.5"
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          {refreshing ? "Ré-analyse…" : "Ré-analyser (IA)"}
        </button>
      </div>

      {/* ===== EN-TÊTE ===== */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800/80 border border-slate-700/50 rounded-2xl p-6">
        <div className="flex flex-col lg:flex-row items-start lg:items-center gap-6">

          {/* IP + localisation */}
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <Search size={18} className="text-blue-400" />
              <span className="text-slate-400 text-sm font-medium">Investigation OSINT</span>
              <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
                {fmtDate(report.timestamp)}
              </span>
            </div>
            <h1 className="text-3xl font-bold font-mono text-white mb-2">{ip}</h1>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-2xl">{countryFlag(geo.country_code)}</span>
              <span className="text-slate-300">
                {[geo.city, geo.region, geo.country].filter(Boolean).join(", ") || "Localisation inconnue"}
              </span>
              {geo.asn && (
                <span className="text-xs font-mono text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
                  {geo.asn}
                </span>
              )}
              {geo.reverse_dns && (
                <span className="text-xs text-slate-500 font-mono">↳ {geo.reverse_dns}</span>
              )}
            </div>
            {geo.isp && (
              <p className="text-slate-400 text-sm mt-1 flex items-center gap-1">
                <Building2 size={12} />
                {geo.isp} {geo.asn_name && geo.asn_name !== geo.isp ? `/ ${geo.asn_name}` : ""}
              </p>
            )}
          </div>

          {/* Jauge de risque + verdict */}
          <div className="flex flex-col items-center gap-3">
            <RiskGauge score={risk.score} level={risk.level} />
            <AttackTypeBadge type={profile.type} />
            {risk.verdict && <VerdictBadge verdict={risk.verdict} confidence={risk.confidence} />}
          </div>

        </div>
      </div>

      {/* ===== ANALYSE IA (analyste autonome borné) ===== */}
      {report.ai && (
        <div className="bg-gradient-to-br from-indigo-950/40 to-slate-900/60 border border-indigo-700/40 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-white font-semibold text-sm flex items-center gap-2">
              <Brain size={16} className="text-indigo-400" />
              Analyse IA — Analyste autonome
            </h3>
            <span className="text-[10px] text-slate-400 bg-slate-800/80 px-2 py-1 rounded-full flex items-center gap-1">
              <Sparkles size={10} /> {report.ai.generated_by}
            </span>
          </div>

          {report.ai.summary && (
            <p className="text-slate-100 text-sm font-medium mb-3">{report.ai.summary}</p>
          )}
          {report.ai.narrative && (
            <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">
              {report.ai.narrative}
            </p>
          )}

          {report.ai.recommended_actions?.length > 0 && (
            <div className="mt-4">
              <p className="text-slate-400 text-xs mb-2">Actions de remédiation suggérées :</p>
              <ul className="space-y-1.5">
                {report.ai.recommended_actions.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-200">
                    <CheckCircle size={13} className="text-indigo-400 flex-shrink-0 mt-0.5" /> {a}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="mt-4 text-[10px] text-slate-500 italic">
            Le verdict ({risk.verdict}, {risk.confidence}% de confiance) est calculé de façon
            déterministe. L'IA rédige l'analyse — elle ne décide pas du verdict.
          </p>
        </div>
      )}

      {/* ===== GRILLE PRINCIPALE ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* ---- Géolocalisation ---- */}
        <InfoCard title="Géolocalisation & Réseau" icon={MapPin} iconColor="text-green-400">
          <div className="mb-3">
            <HostingBadges geo={geo} />
          </div>
          <Row label="Pays"         value={`${countryFlag(geo.country_code)} ${geo.country}`} />
          <Row label="Région / Ville" value={[geo.region, geo.city].filter(Boolean).join(", ")} />
          <Row label="Coordonnées"  value={geo.lat && geo.lon ? `${geo.lat.toFixed(2)}, ${geo.lon.toFixed(2)}` : ""} mono />
          <Row label="Fuseau"       value={geo.timezone} />
          <Row label="ISP / FAI"    value={geo.isp} />
          <Row label="Organisation" value={geo.org} />
          <Row label="ASN"          value={geo.asn} mono />
          <Row label="AS Name"      value={geo.asn_name} />
          <Row label="Reverse DNS"  value={geo.reverse_dns} mono />
          {abuseContact && (
            <Row label="Contact abus"
              value={abuseContact}
              badge="text-xs text-blue-300 bg-blue-900/30 border border-blue-700"
            />
          )}
          {/* Lien IP-API */}
          <a
            href={`https://db-ip.com/${ip}`}
            target="_blank" rel="noreferrer"
            className="flex items-center gap-1 text-blue-400 hover:text-blue-300 text-xs mt-3"
          >
            <ExternalLink size={11} /> Voir sur DB-IP
          </a>
        </InfoCard>

        {/* ---- AbuseIPDB ---- */}
        <InfoCard title="Réputation AbuseIPDB" icon={Shield} iconColor="text-orange-400">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-4xl font-bold" style={{
                color: abuse.confidence_score >= 80 ? "#ef4444"
                  : abuse.confidence_score >= 50 ? "#f97316"
                  : abuse.confidence_score >= 20 ? "#eab308" : "#22c55e"
              }}>
                {abuse.confidence_score}
                <span className="text-lg text-slate-400">/100</span>
              </div>
              <p className="text-slate-400 text-xs">Score de confiance</p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-white">{abuse.total_reports}</div>
              <p className="text-slate-400 text-xs">Signalements</p>
            </div>
          </div>

          <Row label="Dernier signalement" value={abuse.last_reported ? `${fmtDate(abuse.last_reported)} (${fmtAgo(abuse.last_reported)})` : "—"} />
          <Row label="Usage type"    value={abuse.usage_type} />
          <Row label="Domaine"       value={abuse.domain} />
          <Row label="ISP (AIPDB)"   value={abuse.isp} />

          {abuse.categories.length > 0 && (
            <div className="mt-3">
              <p className="text-slate-400 text-xs mb-2">Catégories signalées :</p>
              <div className="flex flex-wrap gap-1.5">
                {abuse.categories.map((cat, i) => (
                  <span key={i} className="text-xs bg-orange-900/30 text-orange-300 border border-orange-800/50 px-2 py-0.5 rounded-full">
                    {cat}
                  </span>
                ))}
              </div>
            </div>
          )}

          {abuse.recent_comments.length > 0 && (
            <div className="mt-3">
              <p className="text-slate-400 text-xs mb-2">Commentaires récents :</p>
              <div className="space-y-1.5">
                {abuse.recent_comments.slice(0, 3).map((c, i) => (
                  <p key={i} className="text-slate-300 text-xs bg-slate-800/60 rounded-lg p-2 italic">
                    "{c.substring(0, 120)}{c.length > 120 ? "…" : ""}"
                  </p>
                ))}
              </div>
            </div>
          )}

          <a
            href={`https://www.abuseipdb.com/check/${ip}`}
            target="_blank" rel="noreferrer"
            className="flex items-center gap-1 text-orange-400 hover:text-orange-300 text-xs mt-3"
          >
            <ExternalLink size={11} /> Voir sur AbuseIPDB
          </a>
        </InfoCard>

        {/* ---- VirusTotal ---- */}
        <InfoCard title="VirusTotal" icon={Activity} iconColor="text-purple-400">
          {/* Barre détections */}
          <div className="space-y-2 mb-4">
            {[
              { label: "Malveillant", value: vt.malicious,  color: "bg-red-500",    total: (vt.malicious + vt.suspicious + vt.harmless + vt.undetected) || 1 },
              { label: "Suspect",     value: vt.suspicious, color: "bg-orange-500", total: (vt.malicious + vt.suspicious + vt.harmless + vt.undetected) || 1 },
              { label: "Inoffensif",  value: vt.harmless,   color: "bg-green-500",  total: (vt.malicious + vt.suspicious + vt.harmless + vt.undetected) || 1 },
            ].map(({ label, value, color, total }) => (
              <div key={label}>
                <div className="flex justify-between text-xs text-slate-400 mb-1">
                  <span>{label}</span>
                  <span className="text-slate-200 font-medium">{value}</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${color}`}
                    style={{ width: `${Math.round((value / total) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <Row label="Réputation VT"    value={String(vt.reputation)} />
          <Row label="Dernière analyse" value={fmtDate(vt.last_analysis_date)} />

          {vt.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {vt.tags.map((tag, i) => (
                <span key={i} className="text-xs bg-purple-900/30 text-purple-300 border border-purple-800/50 px-2 py-0.5 rounded-full">
                  {tag}
                </span>
              ))}
            </div>
          )}

          <div className="mt-4 flex items-center gap-2">
            {vt.malicious === 0 ? (
              <CheckCircle size={14} className="text-green-400" />
            ) : (
              <XCircle size={14} className="text-red-400" />
            )}
            <span className={`text-xs font-medium ${vt.malicious === 0 ? "text-green-400" : "text-red-400"}`}>
              {vt.malicious === 0 ? "Aucune détection" : `${vt.malicious} moteur(s) positif(s)`}
            </span>
          </div>

          <a
            href={`https://www.virustotal.com/gui/ip-address/${ip}`}
            target="_blank" rel="noreferrer"
            className="flex items-center gap-1 text-purple-400 hover:text-purple-300 text-xs mt-3"
          >
            <ExternalLink size={11} /> Voir sur VirusTotal
          </a>
        </InfoCard>
      </div>

      {/* ===== PROFIL D'ATTAQUE ===== */}
      <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-5">
        <h3 className="text-white font-semibold text-sm mb-5 flex items-center gap-2">
          <Zap size={15} className="text-yellow-400" />
          Profil d'attaque — Analyse de nos alertes internes
        </h3>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
          {[
            { label: "Alertes enregistrées",  value: profile.alert_count,           color: "text-red-400" },
            { label: "Req/minute (pic)",       value: profile.requests_per_minute + " req/min", color: "text-orange-400" },
            { label: "Première attaque",       value: fmtDate(profile.first_seen),   color: "text-slate-300" },
            { label: "Dernière activité",      value: fmtDate(profile.last_seen),    color: "text-slate-300" },
          ].map(({ label, value, color }, i) => (
            <div key={i} className="bg-slate-800/60 rounded-xl p-3 text-center">
              <div className={`text-lg font-bold ${color}`}>{value || "—"}</div>
              <div className="text-slate-500 text-xs mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Services ciblés */}
          <div>
            <p className="text-slate-400 text-xs mb-2">Services ciblés :</p>
            {profile.targeted_services.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {profile.targeted_services.map((svc, i) => (
                  <span key={i} className="text-xs bg-blue-900/30 text-blue-300 border border-blue-800/50 px-2.5 py-1 rounded-lg flex items-center gap-1">
                    <Server size={10} /> {svc}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-slate-600 text-xs">Aucun service identifié (IP privée ou données insuffisantes)</p>
            )}
          </div>

          {/* Top règles déclenchées */}
          <div>
            <p className="text-slate-400 text-xs mb-2">Règles Wazuh les plus déclenchées :</p>
            {profile.top_rules.length > 0 ? (
              <div className="space-y-1.5">
                {profile.top_rules.map((r, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-yellow-500"
                        style={{ width: `${Math.round((r.count / (profile.top_rules[0]?.count || 1)) * 100)}%` }}
                      />
                    </div>
                    <span className="text-slate-300 text-xs w-8 text-right font-medium">{r.count}</span>
                    <span className="text-slate-500 text-xs max-w-[200px] truncate">{r.rule}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-600 text-xs">Aucune alerte interne trouvée pour cette IP</p>
            )}
          </div>
        </div>

        {profile.sub_type && (
          <p className="mt-4 text-slate-400 text-xs bg-slate-800/40 rounded-lg px-3 py-2">
            <span className="text-slate-300 font-medium">Sous-type : </span>{profile.sub_type}
          </p>
        )}
      </div>

      {/* ===== ÉVALUATION DU RISQUE + ACTIONS ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* Facteurs de risque */}
        <InfoCard title="Facteurs de risque identifiés" icon={AlertTriangle} iconColor="text-red-400">
          {risk.factors.length > 0 ? (
            <ul className="space-y-2">
              {risk.factors.map((factor, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                  <AlertTriangle size={13} className="text-orange-400 flex-shrink-0 mt-0.5" />
                  {factor}
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex items-center gap-2 text-green-400">
              <CheckCircle size={16} />
              <span className="text-sm">Aucun facteur de risque majeur détecté</span>
            </div>
          )}
        </InfoCard>

        {/* Actions recommandées */}
        <InfoCard title="Actions recommandées" icon={Eye} iconColor="text-blue-400">
          <div className="space-y-2">
            {risk.recommended_actions.map((action, i) => {
              const priorityStyles = {
                high:   "border-red-500/40 bg-red-500/5",
                medium: "border-orange-500/40 bg-orange-500/5",
                low:    "border-slate-600 bg-slate-800/40",
              };
              return (
                <div key={i} className={`rounded-xl border px-3 py-2.5 ${priorityStyles[action.priority] || priorityStyles.low}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-white">{action.label}</span>
                    {action.action === "block_ip" && (
                      <button
                        onClick={handleBlockIp}
                        disabled={blocking || blocked}
                        className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${
                          blocked
                            ? "bg-green-700 text-green-200"
                            : "bg-red-600 hover:bg-red-500 text-white"
                        } disabled:opacity-60`}
                      >
                        {blocked ? "✓ Bloqué" : blocking ? "…" : "Exécuter"}
                      </button>
                    )}
                  </div>
                  <p className="text-slate-400 text-xs mt-0.5">{action.description}</p>
                </div>
              );
            })}
          </div>
        </InfoCard>

      </div>

      {/* ===== DONNÉES BRUTES RDAP ===== */}
      {Object.keys(raw_rdap).length > 0 && (
        <details className="bg-slate-900/60 border border-slate-700/50 rounded-2xl">
          <summary className="px-5 py-4 text-white font-semibold text-sm cursor-pointer hover:bg-slate-800/50 rounded-2xl">
            Données WHOIS/RDAP brutes
          </summary>
          <div className="px-5 pb-5">
            <pre className="text-xs text-slate-300 bg-slate-950/80 rounded-xl p-4 overflow-auto max-h-64 font-mono">
              {JSON.stringify(raw_rdap, null, 2)}
            </pre>
          </div>
        </details>
      )}

    </div>
  );
}
