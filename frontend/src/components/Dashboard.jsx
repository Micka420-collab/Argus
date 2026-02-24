/**
 * Dashboard SOC — Glassmorphism redesign
 * Intègre MitreHeatmap + ThreatFeed live + salutation personnalisée
 */
import { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  AlertTriangle, Shield, Activity, Server,
  TrendingUp, Clock, ChevronUp,
} from "lucide-react";
import { alertsApi } from "../services/api";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { useAuth } from "../contexts/AuthContext";
import MitreHeatmap from "./MitreHeatmap";
import ThreatFeed from "./ThreatFeed";

// ---------------------------------------------------------------------------
// Couleurs sévérité
// ---------------------------------------------------------------------------
const SEV_COLORS = {
  critical: "#ef4444",
  high:     "#f97316",
  medium:   "#eab308",
  low:      "#22c55e",
};

// ---------------------------------------------------------------------------
// StatCard glassmorphism
// ---------------------------------------------------------------------------
function StatCard({ title, value, icon: Icon, gradient, subtitle, trend }) {
  const gradients = {
    red:    "from-red-500/20 to-red-600/5 border-red-500/30 shadow-red-500/10",
    orange: "from-orange-500/20 to-orange-600/5 border-orange-500/30 shadow-orange-500/10",
    green:  "from-green-500/20 to-green-600/5 border-green-500/30 shadow-green-500/10",
    blue:   "from-blue-500/20 to-blue-600/5 border-blue-500/30 shadow-blue-500/10",
    indigo: "from-indigo-500/20 to-indigo-600/5 border-indigo-500/30 shadow-indigo-500/10",
  };
  const iconColors = {
    red: "text-red-400", orange: "text-orange-400",
    green: "text-green-400", blue: "text-blue-400", indigo: "text-indigo-400",
  };
  const g = gradients[gradient] || gradients.blue;
  const ic = iconColors[gradient] || iconColors.blue;

  return (
    <div className={`relative bg-gradient-to-br ${g} backdrop-blur-sm rounded-2xl border p-5 shadow-lg hover:scale-[1.02] transition-transform duration-200 overflow-hidden`}>
      {/* Cercle décoratif */}
      <div className="absolute -right-4 -top-4 w-20 h-20 rounded-full opacity-10 bg-white" />
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2.5 rounded-xl bg-white/5 border border-white/10`}>
          <Icon size={18} className={ic} />
        </div>
        {trend !== undefined && (
          <span className={`flex items-center gap-1 text-xs font-medium ${trend >= 0 ? "text-red-400" : "text-green-400"}`}>
            <ChevronUp size={12} className={trend < 0 ? "rotate-180" : ""} />
            {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div className="text-3xl font-bold text-white tabular-nums">{value ?? "—"}</div>
      <div className="text-slate-300 text-sm font-medium mt-0.5">{title}</div>
      {subtitle && <div className="text-slate-500 text-xs mt-1">{subtitle}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tooltip customisé pour les graphiques
// ---------------------------------------------------------------------------
const DarkTooltip = {
  contentStyle: {
    background: "#0f172a",
    border: "1px solid #334155",
    borderRadius: 10,
    fontSize: 12,
  },
  labelStyle: { color: "#e2e8f0" },
};

// ---------------------------------------------------------------------------
// Salutation selon l'heure
// ---------------------------------------------------------------------------
function getGreeting() {
  const h = new Date().getHours();
  if (h < 6)  return "Bonne nuit";
  if (h < 12) return "Bonjour";
  if (h < 18) return "Bon après-midi";
  return "Bonsoir";
}

// ---------------------------------------------------------------------------
// Dashboard principal
// ---------------------------------------------------------------------------
export default function Dashboard({ newAlerts = [] }) {
  const { user } = useAuth();
  const [stats, setStats]   = useState(null);
  const [period, setPeriod] = useState(24);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const data = await alertsApi.stats(period);
      setStats(data);
    } catch (e) {
      console.error("Erreur stats:", e);
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => {
    if (newAlerts.length > 0) fetchStats();
  }, [newAlerts, fetchStats]);

  const aggs = stats?.aggregations || {};

  // ---- Données graphiques ----
  const severityData = [
    { name: "Critique", value: aggs.by_level?.buckets?.find(b => b.key === "critical")?.doc_count || 0, color: SEV_COLORS.critical },
    { name: "Haute",    value: aggs.by_level?.buckets?.find(b => b.key === "high")?.doc_count    || 0, color: SEV_COLORS.high },
    { name: "Moyenne",  value: aggs.by_level?.buckets?.find(b => b.key === "medium")?.doc_count  || 0, color: SEV_COLORS.medium },
    { name: "Basse",    value: aggs.by_level?.buckets?.find(b => b.key === "low")?.doc_count     || 0, color: SEV_COLORS.low },
  ];

  const timelineData = (aggs.alerts_over_time?.buckets || []).map(b => ({
    time: format(new Date(b.key_as_string || b.key), "HH:mm", { locale: fr }),
    alertes: b.doc_count,
  }));

  const topRules = (aggs.top_rules?.buckets || []).slice(0, 8).map((b, i) => ({
    rule: b.key.substring(0, 32) + (b.key.length > 32 ? "…" : ""),
    count: b.doc_count,
    fill: `hsl(${220 - i * 15}, 80%, ${60 - i * 4}%)`,
  }));

  const topAgents = (aggs.top_agents?.buckets || []).slice(0, 8);
  const totalAlerts   = severityData.reduce((s, d) => s + d.value, 0);
  const criticalCount = severityData.find(d => d.name === "Critique")?.value || 0;
  const highCount     = severityData.find(d => d.name === "Haute")?.value    || 0;

  // ---- MITRE data depuis les alertes ----
  const mitreData = {};
  newAlerts.forEach(alert => {
    const tactic = alert.rule?.mitre?.tactic;
    const tech   = alert.rule?.mitre?.technique;
    if (tactic && tech) {
      mitreData[tactic] = mitreData[tactic] || {};
      mitreData[tactic][tech] = (mitreData[tactic][tech] || 0) + 1;
    }
  });

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-10 w-10 border-2 border-blue-500 border-t-transparent" />
          <p className="text-slate-400 text-sm">Chargement du dashboard…</p>
        </div>
      </div>
    );
  }

  const displayName = user?.full_name || user?.username || "Analyste";
  const today = format(new Date(), "EEEE d MMMM yyyy", { locale: fr });

  return (
    <div className="p-6 space-y-6 min-h-full">

      {/* ---- En-tête personnalisé ---- */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {getGreeting()}, <span className="text-blue-400">{displayName}</span> 👋
          </h1>
          <p className="text-slate-400 text-sm mt-1 flex items-center gap-2">
            <Clock size={13} />
            {today} · Vue sur les {period === 168 ? "7 derniers jours" : `${period} dernières heures`}
          </p>
        </div>

        {/* Sélecteur de période */}
        <div className="flex items-center gap-1.5 bg-slate-800/60 border border-slate-700/50 rounded-xl p-1 backdrop-blur-sm">
          {[6, 24, 48, 168].map(h => (
            <button
              key={h}
              onClick={() => setPeriod(h)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                period === h
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30"
                  : "text-slate-300 hover:bg-slate-700"
              }`}
            >
              {h === 168 ? "7j" : `${h}h`}
            </button>
          ))}
        </div>
      </div>

      {/* ---- Bannière alertes critiques ---- */}
      {criticalCount > 0 && (
        <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/40 rounded-xl px-4 py-3 animate-pulse">
          <AlertTriangle size={18} className="text-red-400 flex-shrink-0" />
          <p className="text-red-300 font-medium text-sm">
            ⚠️ {criticalCount} alerte{criticalCount > 1 ? "s critiques" : " critique"} en cours — vérifier immédiatement
          </p>
        </div>
      )}

      {/* ---- StatCards ---- */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total alertes"
          value={totalAlerts}
          icon={Activity}
          gradient="blue"
          subtitle={`sur ${period === 168 ? "7 jours" : `${period}h`}`}
        />
        <StatCard
          title="Critiques"
          value={criticalCount}
          icon={AlertTriangle}
          gradient="red"
          subtitle="Niveau ≥ 14"
        />
        <StatCard
          title="Haute sévérité"
          value={highCount}
          icon={TrendingUp}
          gradient="orange"
          subtitle="Niveau 10–13"
        />
        <StatCard
          title="Machines actives"
          value={topAgents.length}
          icon={Server}
          gradient="green"
          subtitle="avec alertes"
        />
      </div>

      {/* ---- Timeline + ThreatFeed ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Timeline alertes (2/3) */}
        <div className="lg:col-span-2 bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-5">
          <h2 className="text-white font-semibold text-sm mb-4 flex items-center gap-2">
            <Activity size={14} className="text-blue-400" />
            Alertes dans le temps
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={timelineData}>
              <defs>
                <linearGradient id="alertGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...DarkTooltip} />
              <Area
                type="monotone"
                dataKey="alertes"
                stroke="#3b82f6"
                fill="url(#alertGrad)"
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Threat Feed live (1/3) */}
        <div className="h-72 lg:h-auto">
          <ThreatFeed alerts={newAlerts} maxItems={20} />
        </div>
      </div>

      {/* ---- MITRE ATT&CK Heatmap ---- */}
      <MitreHeatmap data={mitreData} />

      {/* ---- Top règles + Répartition + Machines ---- */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Top règles (barres horizontales) */}
        <div className="lg:col-span-2 bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-5">
          <h2 className="text-white font-semibold text-sm mb-4 flex items-center gap-2">
            <Shield size={14} className="text-indigo-400" />
            Top règles déclenchées
          </h2>
          {topRules.length > 0 ? (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={topRules} layout="vertical" margin={{ left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  dataKey="rule"
                  type="category"
                  width={175}
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip {...DarkTooltip} />
                <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                  {topRules.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-40 text-slate-600">
              <p className="text-sm">Aucune donnée disponible</p>
            </div>
          )}
        </div>

        {/* Répartition + Machines */}
        <div className="space-y-4">

          {/* PieChart sévérité */}
          <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-4">
            <h2 className="text-white font-semibold text-sm mb-2">Répartition</h2>
            <ResponsiveContainer width="100%" height={130}>
              <PieChart>
                <Pie
                  data={severityData.filter(d => d.value > 0)}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={30}
                  outerRadius={55}
                >
                  {severityData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip {...DarkTooltip} />
              </PieChart>
            </ResponsiveContainer>
            {/* Légende compacte */}
            <div className="grid grid-cols-2 gap-1 mt-1">
              {severityData.map((d, i) => (
                <div key={i} className="flex items-center gap-1.5 text-xs text-slate-400">
                  <div className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                  {d.name}: <span className="text-slate-200 font-medium">{d.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Machines les plus alertées */}
          <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-4 flex-1">
            <h2 className="text-white font-semibold text-sm mb-3">Machines actives</h2>
            <div className="space-y-2.5">
              {topAgents.slice(0, 5).map((agent, i) => {
                const pct = totalAlerts > 0 ? Math.round((agent.doc_count / totalAlerts) * 100) : 0;
                const hue = 220 - i * 20;
                return (
                  <div key={i}>
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span className="truncate max-w-[120px]">{agent.key}</span>
                      <span className="text-slate-200 font-medium">{agent.doc_count}</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${pct}%`, background: `hsl(${hue}, 75%, 55%)` }}
                      />
                    </div>
                  </div>
                );
              })}
              {topAgents.length === 0 && (
                <p className="text-slate-600 text-xs">Aucune machine détectée</p>
              )}
            </div>
          </div>

        </div>
      </div>

    </div>
  );
}
