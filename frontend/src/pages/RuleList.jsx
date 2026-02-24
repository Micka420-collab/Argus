import { useState, useEffect } from "react";
import {
  Shield, Search, AlertTriangle, ExternalLink,
  ChevronDown, ChevronUp, RefreshCw, Tag
} from "lucide-react";
import { rulesApi } from "../services/api";

// ─── Badges ───────────────────────────────────────────────────────────────────

function LevelBadge({ level }) {
  const cfg =
    level >= 13 ? { cls: "bg-red-900/50 text-red-300 border-red-700",        label: `Critique (${level})` } :
    level >= 10 ? { cls: "bg-orange-900/50 text-orange-300 border-orange-700", label: `Élevé (${level})` } :
    level >= 7  ? { cls: "bg-yellow-900/50 text-yellow-300 border-yellow-700", label: `Moyen (${level})` } :
                  { cls: "bg-slate-700 text-slate-300 border-slate-600",       label: `Faible (${level})` };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

// ─── Ligne de règle ───────────────────────────────────────────────────────────

function RuleRow({ rule }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 bg-slate-800 hover:bg-slate-700/50 transition-colors text-left"
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Shield size={15} className={
            rule.level >= 13 ? "text-red-400" :
            rule.level >= 10 ? "text-orange-400" :
            rule.level >= 7  ? "text-yellow-400" : "text-slate-400"
          } />
          <span className="font-mono text-slate-400 text-sm w-20 shrink-0">#{rule.id}</span>
          <span className="text-white text-sm truncate">{rule.description}</span>
        </div>
        <div className="flex items-center gap-3 ml-3 shrink-0">
          <LevelBadge level={rule.level} />
          {open ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
        </div>
      </button>

      {open && (
        <div className="px-5 py-4 bg-slate-900/50 border-t border-slate-700 space-y-3">

          {/* Groupes */}
          {rule.groups?.length > 0 && (
            <div className="flex items-start gap-2">
              <Tag size={13} className="text-slate-500 mt-0.5 shrink-0" />
              <div className="flex flex-wrap gap-1.5">
                {rule.groups.map(g => (
                  <span
                    key={g}
                    className="text-xs bg-slate-700 text-slate-300 border border-slate-600 px-2 py-0.5 rounded-full"
                  >
                    {g}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* MITRE ATT&CK */}
          {rule.mitre_ids?.length > 0 && (
            <div className="flex items-start gap-2">
              <Shield size={13} className="text-purple-400 mt-0.5 shrink-0" />
              <div className="flex flex-wrap gap-1.5">
                {rule.mitre_ids.map(id => (
                  <a
                    key={id}
                    href={`https://attack.mitre.org/techniques/${id.replace(".", "/")}`}
                    target="_blank"
                    rel="noreferrer"
                    onClick={e => e.stopPropagation()}
                    className="inline-flex items-center gap-1 text-xs bg-purple-900/50 text-purple-300 border border-purple-700 px-2 py-0.5 rounded-full hover:bg-purple-800/50"
                  >
                    {id} <ExternalLink size={9} />
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Statut */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${rule.enabled ? "bg-green-400" : "bg-slate-500"}`} />
            <span className="text-xs text-slate-400">{rule.enabled ? "Règle active" : "Règle désactivée"}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────

export default function RuleList() {
  const [rules, setRules]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [search, setSearch]     = useState("");
  const [filterLevel, setFilterLevel] = useState("all");
  const [sortBy, setSortBy]     = useState("level_desc");

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await rulesApi.list();
      setRules(Array.isArray(data) ? data : data?.rules ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchRules(); }, []);

  // Filtres + tri
  const filtered = rules
    .filter(r => {
      const matchSearch = !search ||
        r.description?.toLowerCase().includes(search.toLowerCase()) ||
        String(r.id).includes(search) ||
        r.groups?.some(g => g.toLowerCase().includes(search.toLowerCase()));
      const matchLevel =
        filterLevel === "all"     ? true :
        filterLevel === "critical" ? r.level >= 13 :
        filterLevel === "high"     ? r.level >= 10 && r.level < 13 :
        filterLevel === "medium"   ? r.level >= 7  && r.level < 10 :
        r.level < 7;
      return matchSearch && matchLevel;
    })
    .sort((a, b) => {
      if (sortBy === "level_desc") return b.level - a.level;
      if (sortBy === "level_asc")  return a.level - b.level;
      if (sortBy === "id_asc")     return Number(a.id) - Number(b.id);
      return 0;
    });

  // Compteurs par criticité
  const counts = {
    critical: rules.filter(r => r.level >= 13).length,
    high:     rules.filter(r => r.level >= 10 && r.level < 13).length,
    medium:   rules.filter(r => r.level >= 7  && r.level < 10).length,
    low:      rules.filter(r => r.level < 7).length,
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">

      {/* En-tête */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Shield size={24} className="text-purple-400" />
            Règles de Détection
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Règles Wazuh custom actives sur la plateforme
          </p>
        </div>
        <button
          onClick={fetchRules}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 text-sm transition-colors"
        >
          <RefreshCw size={14} /> Actualiser
        </button>
      </div>

      {/* Résumé par niveau */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Critique",  count: counts.critical, color: "text-red-400",    bg: "bg-red-900/20 border-red-700/40" },
          { label: "Élevé",     count: counts.high,     color: "text-orange-400", bg: "bg-orange-900/20 border-orange-700/40" },
          { label: "Moyen",     count: counts.medium,   color: "text-yellow-400", bg: "bg-yellow-900/20 border-yellow-700/40" },
          { label: "Faible",    count: counts.low,      color: "text-slate-400",  bg: "bg-slate-800 border-slate-600" },
        ].map(({ label, count, color, bg }) => (
          <div key={label} className={`rounded-xl border p-3 text-center ${bg}`}>
            <p className={`text-2xl font-bold ${color}`}>{count}</p>
            <p className={`text-xs ${color} mt-0.5`}>{label}</p>
          </div>
        ))}
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher règle, ID, groupe..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 bg-slate-800 border border-slate-600 rounded-lg text-sm text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
          />
        </div>
        <select
          value={filterLevel}
          onChange={e => setFilterLevel(e.target.value)}
          className="px-3 py-2.5 bg-slate-800 border border-slate-600 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">Tous les niveaux</option>
          <option value="critical">Critique (≥ 13)</option>
          <option value="high">Élevé (10-12)</option>
          <option value="medium">Moyen (7-9)</option>
          <option value="low">Faible (&lt; 7)</option>
        </select>
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="px-3 py-2.5 bg-slate-800 border border-slate-600 rounded-lg text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="level_desc">Niveau ↓</option>
          <option value="level_asc">Niveau ↑</option>
          <option value="id_asc">ID ↑</option>
        </select>
      </div>

      {/* Contenu */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-400">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-purple-500 mb-4" />
          Chargement des règles...
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-16 text-red-400 bg-red-900/10 border border-red-700/30 rounded-xl">
          <AlertTriangle size={32} className="mb-3" />
          <p className="font-semibold">Erreur de chargement</p>
          <p className="text-sm mt-1 text-red-300">{error}</p>
          <button
            onClick={fetchRules}
            className="mt-4 px-4 py-2 bg-red-700 text-white rounded-lg text-sm hover:bg-red-600"
          >
            Réessayer
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          <Shield size={40} className="mb-3 opacity-30" />
          <p className="font-semibold">Aucune règle trouvée</p>
          {search || filterLevel !== "all" ? (
            <p className="text-sm mt-1">Modifier les filtres pour afficher plus de résultats</p>
          ) : (
            <p className="text-sm mt-1">Ajouter des règles dans <code className="font-mono text-slate-500">/var/ossec/etc/rules/local_rules.xml</code></p>
          )}
        </div>
      ) : (
        <>
          <p className="text-slate-500 text-sm">
            {filtered.length} règle{filtered.length > 1 ? "s" : ""}
            {(search || filterLevel !== "all") && ` sur ${rules.length}`}
          </p>
          <div className="space-y-2">
            {filtered.map(rule => (
              <RuleRow key={rule.id} rule={rule} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
