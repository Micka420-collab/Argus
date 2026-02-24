/**
 * Threat Feed — Flux d'alertes critiques en temps réel
 * Défile automatiquement comme un ticker de news
 */
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Shield, Activity, Globe } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

const SEVERITY_CONFIG = {
  critical: { icon: AlertTriangle, color: "text-red-400",    bg: "bg-red-500/10 border-red-500/30",    pulse: "animate-pulse" },
  high:     { icon: AlertTriangle, color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30", pulse: "" },
  medium:   { icon: Activity,      color: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/30", pulse: "" },
  low:      { icon: Shield,        color: "text-green-400",  bg: "bg-green-500/10 border-green-500/30",  pulse: "" },
};

function getSeverity(level) {
  if (level >= 14) return "critical";
  if (level >= 10) return "high";
  if (level >= 7)  return "medium";
  return "low";
}

function FeedItem({ alert, isNew }) {
  const level    = alert.rule?.level || 0;
  const severity = getSeverity(level);
  const cfg      = SEVERITY_CONFIG[severity];
  const Icon     = cfg.icon;

  return (
    <div className={`flex items-start gap-3 p-3 rounded-xl border transition-all duration-500 ${cfg.bg} ${isNew ? "ring-1 ring-blue-500/50" : ""}`}>
      <div className={`mt-0.5 ${cfg.pulse}`}>
        <Icon size={14} className={cfg.color} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-slate-200 text-xs leading-tight line-clamp-2">
          {alert.rule?.description || "Alerte inconnue"}
        </p>
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${cfg.color}`}>
            {severity.toUpperCase()}
          </span>
          {alert.agent?.name && (
            <span className="text-slate-500 text-xs flex items-center gap-1">
              <Shield size={10} /> {alert.agent.name}
            </span>
          )}
          {(alert.data?.srcip || alert.src_ip) && (
            <span className="text-slate-500 text-xs flex items-center gap-1 font-mono">
              <Globe size={10} /> {alert.data?.srcip || alert.src_ip}
            </span>
          )}
          <span className="text-slate-600 text-xs ml-auto">
            {alert.timestamp
              ? formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true, locale: fr })
              : "maintenant"}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ThreatFeed({ alerts = [], maxItems = 30 }) {
  const [items, setItems]    = useState(alerts.slice(0, maxItems));
  const [newIds, setNewIds]  = useState(new Set());
  const containerRef         = useRef(null);
  const prevAlertsRef        = useRef(alerts);

  useEffect(() => {
    if (!alerts.length) return;

    // Détecter les nouvelles alertes
    const prevIds = new Set(prevAlertsRef.current.map(a => a.id));
    const fresh   = alerts.filter(a => !prevIds.has(a.id));

    if (fresh.length > 0) {
      const freshIds = new Set(fresh.map(a => a.id));
      setNewIds(freshIds);
      setTimeout(() => setNewIds(new Set()), 3000); // Retirer highlight après 3s

      // Auto-scroll vers le haut si nouvelles alertes
      containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    }

    setItems(alerts.slice(0, maxItems));
    prevAlertsRef.current = alerts;
  }, [alerts, maxItems]);

  const criticalCount = items.filter(a => (a.rule?.level || 0) >= 14).length;
  const highCount     = items.filter(a => { const l = a.rule?.level || 0; return l >= 10 && l < 14; }).length;

  return (
    <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 flex flex-col h-full">
      {/* En-tête */}
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          <h2 className="text-white font-semibold text-sm">Threat Feed</h2>
          <span className="text-slate-500 text-xs">live</span>
        </div>
        <div className="flex items-center gap-2">
          {criticalCount > 0 && (
            <span className="text-xs bg-red-500/20 text-red-300 border border-red-500/30 px-2 py-0.5 rounded-full animate-pulse">
              {criticalCount} critique{criticalCount > 1 ? "s" : ""}
            </span>
          )}
          {highCount > 0 && (
            <span className="text-xs bg-orange-500/20 text-orange-300 border border-orange-500/30 px-2 py-0.5 rounded-full">
              {highCount} haute
            </span>
          )}
        </div>
      </div>

      {/* Liste scrollable */}
      <div ref={containerRef} className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-slate-600">
            <Shield size={32} className="mb-2 opacity-30" />
            <p className="text-sm">Aucune alerte récente</p>
          </div>
        ) : (
          items.map(alert => (
            <FeedItem
              key={alert.id || Math.random()}
              alert={alert}
              isNew={newIds.has(alert.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
