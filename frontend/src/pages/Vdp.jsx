/**
 * VDP / Bug-Bounty (pilier YesWeHack).
 * File de triage + rapport (CVSS, récompense, triage IA, machine à états) +
 * modale de soumission avec constructeur de vecteur CVSS v3.1.
 */
import { useState, useEffect, useCallback } from "react";
import {
  Bug, Plus, X, Award, ShieldCheck, Clock, FileText, User, Send,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { vdpApi } from "../services/api";
import { PageHeader, SeverityBadge, EmptyState, Spinner, Toast } from "../components/ui";

const STATUS_LABEL = {
  new: "Nouveau", triaging: "En triage", need_info: "Info requise", accepted: "Accepté",
  resolved: "Résolu", duplicate: "Doublon", out_of_scope: "Hors scope", spam: "Spam", rejected: "Rejeté",
};
const NEXT_STATUSES = {
  new: ["triaging", "duplicate", "out_of_scope", "spam", "rejected"],
  triaging: ["need_info", "accepted", "duplicate", "out_of_scope", "rejected"],
  need_info: ["triaging", "accepted", "rejected"],
  accepted: ["resolved", "need_info"],
};
const fmtAgo = (s) => { try { return formatDistanceToNow(new Date(s), { addSuffix: true, locale: fr }); } catch { return ""; } };

// CVSS metric options
const METRICS = [
  ["AV", "Vecteur d'attaque", [["N", "Réseau"], ["A", "Adjacent"], ["L", "Local"], ["P", "Physique"]]],
  ["AC", "Complexité",        [["L", "Faible"], ["H", "Élevée"]]],
  ["PR", "Privilèges",        [["N", "Aucun"], ["L", "Faibles"], ["H", "Élevés"]]],
  ["UI", "Interaction",       [["N", "Aucune"], ["R", "Requise"]]],
  ["S",  "Scope",             [["U", "Inchangé"], ["C", "Changé"]]],
  ["C",  "Confidentialité",   [["N", "Aucune"], ["L", "Faible"], ["H", "Élevée"]]],
  ["I",  "Intégrité",         [["N", "Aucune"], ["L", "Faible"], ["H", "Élevée"]]],
  ["A",  "Disponibilité",     [["N", "Aucune"], ["L", "Faible"], ["H", "Élevée"]]],
];

// ---------------------------------------------------------------------------
// Modale de soumission
// ---------------------------------------------------------------------------
function SubmitModal({ onClose, onSubmitted }) {
  const [form, setForm] = useState({ title: "", description: "", asset: "", endpoint: "", vuln_type: "", poc: "" });
  const [metrics, setMetrics] = useState({ AV: "N", AC: "L", PR: "N", UI: "N", S: "U", C: "H", I: "H", A: "H" });
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const vector = `CVSS:3.1/${METRICS.map(([k]) => `${k}:${metrics[k]}`).join("/")}`;

  useEffect(() => {
    let alive = true;
    vdpApi.cvss(vector).then((r) => { if (alive) setPreview(r); }).catch(() => {});
    return () => { alive = false; };
  }, [vector]);

  const submit = async () => {
    if (!form.title.trim() || !form.description.trim()) { setErr("Titre et description requis"); return; }
    setBusy(true); setErr("");
    try {
      const rep = await vdpApi.submit({ ...form, cvss_vector: vector });
      onSubmitted(rep);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };

  const sevColor = { critical: "text-danger", high: "text-high", medium: "text-warning", low: "text-accent", none: "text-muted" };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="flex items-center gap-2"><Send className="h-4 w-4 text-accent" /> Nouveau rapport</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fermer"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          {err && <div className="badge-malicious !rounded-lg !py-2 !px-3 w-full">{err}</div>}
          <div>
            <label className="label">Titre *</label>
            <input className="input" value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} placeholder="Ex. SQLi sur /api/login" />
          </div>
          <div>
            <label className="label">Description *</label>
            <textarea className="input !h-28 py-2" value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} placeholder="Détail de la vulnérabilité…" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Asset</label><input className="input" value={form.asset} onChange={(e) => setForm((p) => ({ ...p, asset: e.target.value }))} placeholder="api" /></div>
            <div><label className="label">Type (CWE)</label><input className="input" value={form.vuln_type} onChange={(e) => setForm((p) => ({ ...p, vuln_type: e.target.value }))} placeholder="CWE-89 / SQLi" /></div>
          </div>

          {/* Constructeur CVSS */}
          <div className="rounded-lg border border-border bg-surface-alt p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="eyebrow">Vecteur CVSS v3.1</p>
              {preview && (
                <span className={`stat !text-h1 tabnum ${sevColor[preview.severity] || "text-muted"}`}>
                  {preview.score} <span className="text-meta capitalize">{preview.severity}</span>
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {METRICS.map(([k, label, opts]) => (
                <div key={k}>
                  <label className="text-meta text-muted">{label}</label>
                  <select
                    className="input !h-8 !px-2 text-meta"
                    value={metrics[k]}
                    onChange={(e) => setMetrics((p) => ({ ...p, [k]: e.target.value }))}
                  >
                    {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
              ))}
            </div>
            <p className="mono-chip mt-3 w-full !block truncate">{vector}</p>
          </div>

          <div><label className="label">Preuve de concept (PoC)</label><textarea className="input !h-20 py-2 font-mono text-meta" value={form.poc} onChange={(e) => setForm((p) => ({ ...p, poc: e.target.value }))} placeholder="curl -X POST …" /></div>
        </div>
        <div className="flex items-center justify-end gap-2 p-5 border-t border-border">
          <button className="btn-ghost" onClick={onClose}>Annuler</button>
          <button className="btn-primary" disabled={busy} onClick={submit}>
            {busy ? <Spinner /> : <Send className="h-4 w-4" />} Soumettre
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Détail d'un rapport
// ---------------------------------------------------------------------------
function ReportDetail({ report, onTransition, busy }) {
  const next = NEXT_STATUSES[report.status] || [];
  return (
    <div className="space-y-5">
      <div className="card card-pad">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <SeverityBadge level={report.severity} />
              <span className="badge-neutral">{STATUS_LABEL[report.status] || report.status}</span>
            </div>
            <h1>{report.title}</h1>
            <p className="text-meta text-muted mt-1 flex items-center gap-2">
              <User className="h-3.5 w-3.5" /> {report.researcher} · {fmtAgo(report.created_at)}
            </p>
          </div>
          <div className="text-right">
            <p className="stat tabnum text-text">{report.cvss_score}</p>
            <p className="text-meta text-muted">CVSS v3.1</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-4">
          {report.asset && <span className="mono-chip">{report.asset}</span>}
          {report.vuln_type && <span className="mono-chip">{report.vuln_type}</span>}
          {report.cvss_vector && <span className="mono-chip">{report.cvss_vector}</span>}
        </div>
        <div className="mt-4 flex items-center gap-2 rounded-lg bg-accent2/5 border border-accent2/20 px-3 py-2">
          <Award className="h-4 w-4 text-accent2" />
          <span className="text-body text-text">Récompense suggérée :</span>
          <span className="text-body font-semibold text-accent2 tabnum">{report.reward_suggested} {report.reward_currency}</span>
        </div>
      </div>

      {/* Triage IA */}
      {report.triage?.summary && (
        <div className="card card-pad">
          <div className="flex items-center justify-between mb-2">
            <h2 className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-accent2" /> Triage assisté</h2>
            <span className="badge-neutral text-meta">{report.triage.generated_by}</span>
          </div>
          {report.triage.is_duplicate && (
            <p className="badge-inconclusive mb-2 inline-flex">Doublon possible de {report.triage.duplicate_of}</p>
          )}
          <p className="text-body text-muted leading-6">{report.triage.summary}</p>
        </div>
      )}

      {/* Description + PoC */}
      <div className="card card-pad">
        <h2 className="mb-2 flex items-center gap-2"><FileText className="h-4 w-4 text-muted" /> Description</h2>
        <p className="text-body text-muted whitespace-pre-line leading-6">{report.description}</p>
        {report.poc && (
          <pre className="mt-3 text-meta font-mono bg-surface-alt border border-border rounded-lg p-3 overflow-auto text-muted">{report.poc}</pre>
        )}
      </div>

      {/* Transitions */}
      {next.length > 0 && (
        <div className="card card-pad">
          <h2 className="mb-3">Action de triage</h2>
          <div className="flex flex-wrap gap-2">
            {next.map((s) => (
              <button key={s} disabled={busy} onClick={() => onTransition(report.id, s)}
                className={s === "accepted" || s === "resolved" ? "btn-primary btn-sm" : "btn-ghost btn-sm"}>
                {STATUS_LABEL[s]}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Historique */}
      {(report.history || []).length > 0 && (
        <div className="card card-pad">
          <h2 className="mb-3 flex items-center gap-2"><Clock className="h-4 w-4 text-muted" /> Historique</h2>
          <div className="space-y-2">
            {report.history.map((h, i) => (
              <div key={i} className="flex items-center justify-between text-meta">
                <span className="text-muted">{h.actor} · <span className="text-text">{h.action}</span> {h.detail && `— ${h.detail}`}</span>
                <span className="text-muted-2 tabnum">{fmtAgo(h.at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function Vdp() {
  const [reports, setReports] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await vdpApi.list({ size: 100 });
      const items = data.items || [];
      setReports(items);
      setSelected((cur) => (cur ? items.find((r) => r.id === cur.id) || items[0] : items[0]) || null);
    } catch (e) {
      setToast({ title: "Chargement impossible", desc: e.message });
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onTransition = async (id, status) => {
    setBusy(true);
    try {
      const updated = await vdpApi.setStatus(id, status);
      setReports((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setSelected(updated);
      setToast({ title: "Statut mis à jour", desc: STATUS_LABEL[status] });
    } catch (e) {
      setToast({ title: "Transition refusée", desc: e.message });
    } finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Pilier exposition" title="VDP / Bug-Bounty"
        desc="Soumission, triage assisté, scoring CVSS et grille de récompenses.">
        <button className="btn-primary" onClick={() => setModal(true)}><Plus className="h-4 w-4" /> Nouveau rapport</button>
      </PageHeader>

      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
        <div className="space-y-2">
          {loading ? (
            <div className="card card-pad space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="skeleton h-16 rounded-lg" />)}</div>
          ) : reports.length === 0 ? (
            <EmptyState icon={Bug} title="Aucun rapport" desc="Soumettez un premier rapport de vulnérabilité." />
          ) : (
            reports.map((r) => (
              <button key={r.id} onClick={() => setSelected(r)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selected?.id === r.id ? "border-accent/40 bg-surface-alt" : "border-border hover:bg-surface-alt"}`}>
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <SeverityBadge level={r.severity} />
                  <span className="text-meta text-muted-2 tabnum">CVSS {r.cvss_score}</span>
                </div>
                <p className="text-body text-text truncate">{r.title}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="badge-neutral text-meta">{STATUS_LABEL[r.status] || r.status}</span>
                  {r.asset && <span className="mono-chip">{r.asset}</span>}
                </div>
              </button>
            ))
          )}
        </div>

        <div>
          {selected ? <ReportDetail report={selected} onTransition={onTransition} busy={busy} />
            : !loading ? <EmptyState icon={Bug} title="Sélectionnez un rapport" desc="Choisissez un rapport dans la file." /> : null}
        </div>
      </div>

      {modal && (
        <SubmitModal
          onClose={() => setModal(false)}
          onSubmitted={(rep) => { setModal(false); setReports((p) => [rep, ...p]); setSelected(rep); setToast({ title: "Rapport soumis", desc: `${rep.severity} · ${rep.reward_suggested} €` }); }}
        />
      )}

      {toast && <div className="fixed bottom-4 right-4 z-50"><Toast title={toast.title} desc={toast.desc} onClose={() => setToast(null)} /></div>}
    </div>
  );
}
