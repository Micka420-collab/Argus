import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Server, Search, Plus, Wrench, AlertTriangle,
  CheckCircle, Clock, Shield, Activity, RefreshCw
} from "lucide-react";
import { assetsApi } from "../services/api";

// ─── Badges ───────────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const cfg = {
    online:      { cls: "bg-green-900/50 text-green-300 border-green-700",  label: "En ligne" },
    offline:     { cls: "bg-red-900/50 text-red-300 border-red-700",        label: "Hors ligne" },
    maintenance: { cls: "bg-yellow-900/50 text-yellow-300 border-yellow-700", label: "Maintenance" },
    unknown:     { cls: "bg-slate-700 text-slate-400 border-slate-600",     label: "Inconnu" },
  };
  const { cls, label } = cfg[status] ?? cfg.unknown;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${cls}`}>
      {label}
    </span>
  );
}

function TypeIcon({ type }) {
  const icons = {
    server:     <Server size={16} className="text-blue-400" />,
    workstation:<Activity size={16} className="text-green-400" />,
    network:    <Shield size={16} className="text-orange-400" />,
    vm:         <Server size={16} className="text-purple-400" />,
  };
  return icons[type?.toLowerCase()] ?? <Server size={16} className="text-slate-400" />;
}

// ─── Carte asset ──────────────────────────────────────────────────────────────

function AssetCard({ asset, onClick }) {
  const lastSeen = asset.last_seen
    ? new Date(asset.last_seen).toLocaleString("fr-FR")
    : "Jamais";

  return (
    <div
      onClick={() => onClick(asset.id)}
      className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-blue-500/50 hover:bg-slate-700/50 cursor-pointer transition-all group"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <TypeIcon type={asset.type} />
          <span className="text-white font-semibold truncate max-w-[160px]">{asset.hostname}</span>
        </div>
        <StatusBadge status={asset.status} />
      </div>

      <div className="space-y-1.5 text-sm">
        {asset.ip && (
          <div className="flex items-center justify-between">
            <span className="text-slate-400">IP</span>
            <span className="font-mono text-slate-200">{asset.ip}</span>
          </div>
        )}
        {asset.os && (
          <div className="flex items-center justify-between">
            <span className="text-slate-400">OS</span>
            <span className="text-slate-300 truncate max-w-[150px]">{asset.os}</span>
          </div>
        )}
        {asset.criticality && (
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Criticité</span>
            <span className={`font-medium capitalize ${
              asset.criticality === "critical" ? "text-red-400" :
              asset.criticality === "high"     ? "text-orange-400" :
              asset.criticality === "medium"   ? "text-yellow-400" : "text-green-400"
            }`}>{asset.criticality}</span>
          </div>
        )}
        <div className="flex items-center justify-between pt-1 border-t border-slate-700/50">
          <span className="text-slate-500 text-xs flex items-center gap-1">
            <Clock size={10} /> Vu le
          </span>
          <span className="text-slate-400 text-xs">{lastSeen}</span>
        </div>
      </div>

      {asset.alert_count > 0 && (
        <div className="mt-3 flex items-center gap-1.5 text-xs text-orange-300 bg-orange-900/20 border border-orange-700/40 rounded-lg px-2 py-1">
          <AlertTriangle size={11} />
          {asset.alert_count} alerte{asset.alert_count > 1 ? "s" : ""} récente{asset.alert_count > 1 ? "s" : ""}
        </div>
      )}

      {asset.maintenance_mode && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-yellow-300 bg-yellow-900/20 border border-yellow-700/40 rounded-lg px-2 py-1">
          <Wrench size={11} /> En maintenance
        </div>
      )}
    </div>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────

export default function AssetList() {
  const navigate = useNavigate();
  const [assets, setAssets]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [search, setSearch]   = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterType,   setFilterType]   = useState("all");

  const fetchAssets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await assetsApi.list();
      setAssets(Array.isArray(data) ? data : data?.assets ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAssets(); }, []);

  // Filtres
  const filtered = assets.filter(a => {
    const matchSearch = !search ||
      a.hostname?.toLowerCase().includes(search.toLowerCase()) ||
      a.ip?.includes(search) ||
      a.os?.toLowerCase().includes(search.toLowerCase());
    const matchStatus = filterStatus === "all" || a.status === filterStatus;
    const matchType   = filterType   === "all" || a.type?.toLowerCase() === filterType;
    return matchSearch && matchStatus && matchType;
  });

  // Compteurs par statut
  const counts = {
    online:      assets.filter(a => a.status === "online").length,
    offline:     assets.filter(a => a.status === "offline").length,
    maintenance: assets.filter(a => a.status === "maintenance").length,
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">

      {/* En-tête */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Server size={24} className="text-blue-400" />
            Inventaire des Assets
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            {assets.length} machine{assets.length > 1 ? "s" : ""} supervisée{assets.length > 1 ? "s" : ""}
          </p>
        </div>
        <button
          onClick={fetchAssets}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 text-sm transition-colors"
        >
          <RefreshCw size={14} /> Actualiser
        </button>
      </div>

      {/* Cartes de résumé */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "En ligne",     count: counts.online,      icon: <CheckCircle size={18} />, color: "text-green-400",  bg: "bg-green-900/20 border-green-700/40" },
          { label: "Hors ligne",   count: counts.offline,     icon: <AlertTriangle size={18} />, color: "text-red-400", bg: "bg-red-900/20 border-red-700/40" },
          { label: "Maintenance",  count: counts.maintenance, icon: <Wrench size={18} />, color: "text-yellow-400",    bg: "bg-yellow-900/20 border-yellow-700/40" },
        ].map(({ label, count, icon, color, bg }) => (
          <div key={label} className={`flex items-center gap-3 rounded-xl border p-4 ${bg}`}>
            <span className={color}>{icon}</span>
            <div>
              <p className="text-2xl font-bold text-white">{count}</p>
              <p className={`text-xs ${color}`}>{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher par hostname, IP, OS..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 bg-slate-800 border border-slate-600 rounded-lg text-sm text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
          />
        </div>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="px-3 py-2.5 bg-slate-800 border border-slate-600 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">Tous les statuts</option>
          <option value="online">En ligne</option>
          <option value="offline">Hors ligne</option>
          <option value="maintenance">Maintenance</option>
        </select>
        <select
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
          className="px-3 py-2.5 bg-slate-800 border border-slate-600 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">Tous les types</option>
          <option value="server">Serveur</option>
          <option value="workstation">Workstation</option>
          <option value="vm">VM</option>
          <option value="network">Réseau</option>
        </select>
      </div>

      {/* Contenu */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-400">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-4" />
          Chargement des assets...
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-16 text-red-400 bg-red-900/10 border border-red-700/30 rounded-xl">
          <AlertTriangle size={32} className="mb-3" />
          <p className="font-semibold">Erreur de chargement</p>
          <p className="text-sm mt-1 text-red-300">{error}</p>
          <button
            onClick={fetchAssets}
            className="mt-4 px-4 py-2 bg-red-700 text-white rounded-lg text-sm hover:bg-red-600"
          >
            Réessayer
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          <Server size={40} className="mb-3 opacity-30" />
          <p className="font-semibold">Aucun asset trouvé</p>
          {search || filterStatus !== "all" || filterType !== "all" ? (
            <p className="text-sm mt-1">Modifier les filtres pour voir plus de résultats</p>
          ) : (
            <p className="text-sm mt-1">Les agents Wazuh apparaîtront ici une fois connectés</p>
          )}
        </div>
      ) : (
        <>
          <p className="text-slate-500 text-sm">
            {filtered.length} résultat{filtered.length > 1 ? "s" : ""}
            {(search || filterStatus !== "all" || filterType !== "all") && ` sur ${assets.length}`}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.map(asset => (
              <AssetCard
                key={asset.id}
                asset={asset}
                onClick={(id) => navigate(`/assets/${id}`)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
