/**
 * ASM / CTEM — registre d'exposition priorisé (CVSS × EPSS × KEV × valeur métier).
 */
import { useState, useEffect, useCallback } from "react";
import { Target, Plus, X, Flame, Send } from "lucide-react";
import { exposureApi } from "../services/api";
import { PageHeader, StatTile, SeverityBadge, EmptyState, Spinner, Toast } from "../components/ui";

const STATUS = {
  open: "Ouvert", triaged: "Trié", mitigated: "Corrigé", accepted: "Accepté", false_positive: "Faux positif",
};

function AddModal({ onClose, onAdded }) {
  const [f, setF] = useState({ asset: "", title: "", cve: "", cvss: 0, description: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async () => {
    if (!f.asset.trim() || !f.title.trim()) { setErr("Asset et titre requis"); return; }
    setBusy(true); setErr("");
    try {
      const created = await exposureApi.addFinding({ ...f, cvss: parseFloat(f.cvss) || 0, source: "manual" });
      onAdded(created);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="flex items-center gap-2"><Send className="h-4 w-4 text-accent" /> Nouveau finding</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fermer"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          {err && <div className="badge-malicious !rounded-lg !py-2 !px-3 w-full">{err}</div>}
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Asset *</label><input className="input" value={f.asset} onChange={(e) => setF((p) => ({ ...p, asset: e.target.value }))} placeholder="api / host01" /></div>
            <div><label className="label">CVE</label><input className="input" value={f.cve} onChange={(e) => setF((p) => ({ ...p, cve: e.target.value.toUpperCase() }))} placeholder="CVE-2021-44228" /></div>
          </div>
          <div><label className="label">Titre *</label><input className="input" value={f.title} onChange={(e) => setF((p) => ({ ...p, title: e.target.value }))} placeholder="Log4Shell RCE" /></div>
          <div><label className="label">CVSS (0–10)</label><input type="number" min="0" max="10" step="0.1" className="input" value={f.cvss} onChange={(e) => setF((p) => ({ ...p, cvss: e.target.value }))} /></div>
          <div><label className="label">Description</label><textarea className="input !h-20 py-2" value={f.description} onChange={(e) => setF((p) => ({ ...p, description: e.target.value }))} /></div>
          <p className="text-meta text-muted">EPSS &amp; KEV seront récupérés automatiquement depuis le CVE.</p>
        </div>
        <div className="flex items-center justify-end gap-2 p-5 border-t border-border">
          <button className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn-primary" disabled={busy} onClick={submit}>{busy ? <Spinner /> : <Send className="h-4 w-4" />} Ajouter</button>
        </div>
      </div>
    </div>
  );
}

export default function Exposure() {
  const [findings, setFindings] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tier, setTier] = useState("");
  const [modal, setModal] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [f, s] = await Promise.all([
        exposureApi.findings(tier ? { tier } : {}),
        exposureApi.stats().catch(() => null),
      ]);
      setFindings(f.items || []);
      setStats(s);
    } catch (e) {
      setToast({ title: "Chargement impossible", desc: e.message });
    } finally { setLoading(false); }
  }, [tier]);

  useEffect(() => { load(); }, [load]);

  const changeStatus = async (id, status) => {
    try {
      const u = await exposureApi.setStatus(id, status);
      setFindings((prev) => prev.map((x) => (x.id === id ? u : x)));
    } catch (e) { setToast({ title: "Mise à jour impossible", desc: e.message }); }
  };

  return (
    <div>
      <PageHeader eyebrow="Surface d'attaque" title="Exposition (ASM / CTEM)"
        desc="Findings priorisés par exposition réelle : CVSS × EPSS × KEV × valeur métier.">
        <button className="btn-primary" onClick={() => setModal(true)}><Plus className="h-4 w-4" /> Nouveau finding</button>
      </PageHeader>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        <StatTile label="Findings" value={stats?.total ?? "—"} icon={Target} />
        <StatTile label="Ouverts" value={stats?.open ?? "—"} />
        <StatTile label="KEV (exploités)" value={stats?.kev ?? "—"} icon={Flame} />
        <StatTile label="Critiques" value={stats?.by_tier?.critical ?? 0} halo />
      </div>

      {/* Filtre par tier */}
      <div className="flex items-center gap-1.5 mb-4">
        {["", "critical", "high", "medium", "low"].map((t) => (
          <button key={t || "all"} onClick={() => setTier(t)}
            className={`px-3 py-1.5 rounded-lg text-meta font-medium transition-colors ${
              tier === t ? "bg-accent/15 text-accent" : "text-muted hover:bg-surface-alt"}`}>
            {t ? t : "Tous"}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="card card-pad space-y-3">{[...Array(6)].map((_, i) => <div key={i} className="skeleton h-9 rounded" />)}</div>
      ) : findings.length === 0 ? (
        <EmptyState icon={Target} title="Aucun finding" desc="Ajoutez un finding (enrichi EPSS/KEV) ou connectez un scanner ASM." />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-body">
              <thead>
                <tr className="text-meta text-muted text-left border-b border-border">
                  <th className="px-4 py-3 font-medium">Priorité</th>
                  <th className="px-4 py-3 font-medium">Finding</th>
                  <th className="px-4 py-3 font-medium">Asset</th>
                  <th className="px-4 py-3 font-medium">CVE</th>
                  <th className="px-4 py-3 font-medium tabnum">CVSS</th>
                  <th className="px-4 py-3 font-medium tabnum">EPSS</th>
                  <th className="px-4 py-3 font-medium">Statut</th>
                </tr>
              </thead>
              <tbody>
                {findings.map((f) => (
                  <tr key={f.id} className="border-b border-border/50 last:border-0 hover:bg-surface-alt/50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="tabnum text-text font-semibold w-7">{f.priority_score}</span>
                        <SeverityBadge level={f.priority_tier} />
                      </div>
                    </td>
                    <td className="px-4 py-3 max-w-[260px] truncate text-text">
                      {f.in_kev && <Flame className="inline h-3.5 w-3.5 text-danger mr-1" title="CISA KEV — exploité" />}
                      {f.title}
                    </td>
                    <td className="px-4 py-3"><span className="mono-chip">{f.asset}</span></td>
                    <td className="px-4 py-3">{f.cve ? <span className="mono-chip">{f.cve}</span> : <span className="text-muted-2">—</span>}</td>
                    <td className="px-4 py-3 tabnum text-muted">{f.cvss || "—"}</td>
                    <td className="px-4 py-3 tabnum text-muted">{f.epss ? `${(f.epss * 100).toFixed(1)}%` : "—"}</td>
                    <td className="px-4 py-3">
                      <select value={f.status} onChange={(e) => changeStatus(f.id, e.target.value)}
                        className="input !h-8 !w-auto !px-2 text-meta">
                        {Object.entries(STATUS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {modal && <AddModal onClose={() => setModal(false)} onAdded={(f) => { setModal(false); setFindings((p) => [f, ...p]); setToast({ title: "Finding ajouté", desc: `Priorité ${f.priority_score} (${f.priority_tier})` }); }} />}
      {toast && <div className="fixed bottom-4 right-4 z-50"><Toast title={toast.title} desc={toast.desc} onClose={() => setToast(null)} /></div>}
    </div>
  );
}
