/**
 * AI Console (pilier Qevlar) — investigations autonomes.
 * Master-detail : file des investigations + rapport (verdict, preuves, trace,
 * actions proposées) + boucle de feedback analyste (RAG).
 */
import { useState, useEffect, useCallback } from "react";
import {
  Bot, Search, ShieldAlert, ShieldCheck, HelpCircle, Clock, Cpu, Globe,
  GitBranch, AlertTriangle, CheckCircle2, Network, Brain, ChevronRight,
} from "lucide-react";
import { format, formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { aiApi } from "../services/api";
import {
  PageHeader, VerdictBadge, Confidence, Spinner, EmptyState, Toast,
} from "../components/ui";

const VERDICT_UI = {
  malicious:    { tint: "bg-danger/10 border-danger/30",   text: "text-danger",  Icon: ShieldAlert, label: "Malveillant" },
  benign:       { tint: "bg-success/10 border-success/30", text: "text-success", Icon: ShieldCheck, label: "Bénin" },
  inconclusive: { tint: "bg-warning/10 border-warning/30", text: "text-warning", Icon: HelpCircle,  label: "Indéterminé" },
};

const fmtAgo = (s) => { try { return formatDistanceToNow(new Date(s), { addSuffix: true, locale: fr }); } catch { return ""; } };

// ---------------------------------------------------------------------------
// Élément de la file
// ---------------------------------------------------------------------------
function QueueItem({ report, active, onClick }) {
  const meta = report.alert_meta || {};
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded-lg border transition-colors ${
        active ? "border-accent/40 bg-surface-alt" : "border-border hover:bg-surface-alt"
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <VerdictBadge verdict={report.decision} confidence={report.verdict?.confidence} />
        <span className="text-meta text-muted-2 tabnum">{fmtAgo(report.timestamp)}</span>
      </div>
      <p className="text-body text-text truncate">{meta.rule_desc || report.ip || "Investigation"}</p>
      <div className="flex items-center gap-2 mt-1">
        {report.ip && <span className="mono-chip">{report.ip}</span>}
        {report.source === "auto" && <span className="badge-neutral text-meta"><span className="pulse-ai" /> auto</span>}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Timeline de la trace du graphe
// ---------------------------------------------------------------------------
const NODE_ICON = {
  ingest: ChevronRight, enrich: Globe, correlate: Network, retrieve_feedback: Brain,
  score: Cpu, decide: GitBranch, report: Bot, propose_actions: AlertTriangle,
  persist: CheckCircle2, escalate: AlertTriangle,
};
function Trace({ trace = [] }) {
  return (
    <div className="space-y-0">
      {trace.map((step, i) => {
        const Icon = NODE_ICON[step.node] || ChevronRight;
        const ok = step.status === "ok";
        return (
          <div key={i} className="flex items-start gap-3 relative pb-3 last:pb-0">
            {i < trace.length - 1 && <span className="absolute left-[11px] top-6 bottom-0 w-px bg-border" />}
            <span className={`h-6 w-6 grid place-items-center rounded-full border shrink-0 ${
              ok ? "border-accent/40 text-accent" : "border-danger/40 text-danger"}`}>
              <Icon className="h-3 w-3" />
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-body text-text capitalize">{step.node.replace(/_/g, " ")}</p>
              {step.detail && <p className="text-meta text-danger truncate">{step.detail}</p>}
            </div>
            <span className="text-meta text-muted-2 tabnum">{step.ms}ms</span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rapport (panneau de droite)
// ---------------------------------------------------------------------------
function Report({ report, onFeedback, busy }) {
  const v = VERDICT_UI[report.decision] || VERDICT_UI.inconclusive;
  const verdict = report.verdict || {};
  const ai = report.ai || {};
  const corr = report.correlation || {};
  const meta = report.alert_meta || {};

  return (
    <div className="space-y-5">
      {/* Bandeau verdict */}
      <div className={`card card-pad ${v.tint}`}>
        <div className="flex items-center gap-3">
          <v.Icon className={`h-6 w-6 ${v.text}`} />
          <div>
            <p className={`eyebrow ${v.text} opacity-80`}>Verdict autonome</p>
            <h1 className={v.text}>{v.label}</h1>
          </div>
          <div className="ml-auto text-right">
            <span className="mono-chip">{report.id}</span>
            <p className="text-meta text-muted mt-1 tabnum">score {verdict.score}/100</p>
          </div>
        </div>
        <div className="mt-4 max-w-xs">
          <Confidence value={verdict.confidence || 0} verdict={report.decision} />
        </div>
      </div>

      {/* Résumé IA */}
      {(ai.summary || ai.narrative) && (
        <div className="card card-pad">
          <div className="flex items-center justify-between mb-3">
            <h2 className="flex items-center gap-2"><Brain className="h-4 w-4 text-accent2" /> Analyse</h2>
            <span className="badge-neutral text-meta">{ai.generated_by}</span>
          </div>
          {ai.summary && <p className="text-body text-text font-medium mb-2">{ai.summary}</p>}
          {ai.narrative && <p className="text-body text-muted leading-6 whitespace-pre-line">{ai.narrative}</p>}
        </div>
      )}

      {/* Facteurs + Corrélation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="card card-pad">
          <h2 className="mb-3 flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-warning" /> Facteurs</h2>
          {(verdict.factors || []).length ? (
            <ul className="space-y-2">
              {verdict.factors.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-body text-muted">
                  <span className="badge-dot bg-accent mt-2" /> {f}
                </li>
              ))}
            </ul>
          ) : <p className="text-body text-muted">Aucun facteur de risque majeur.</p>}
        </div>

        <div className="card card-pad">
          <h2 className="mb-3 flex items-center gap-2"><Network className="h-4 w-4 text-accent" /> Corrélation</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              ["Alertes liées (7j)", corr.related_count ?? 0],
              ["Machines touchées",  corr.distinct_agents ?? 0],
              ["Beaconing/C2",       corr.beaconing ? "Oui" : "Non"],
              ["IP source",          report.ip || "—"],
            ].map(([k, val], i) => (
              <div key={i} className="bg-surface-alt rounded-lg p-3">
                <p className="text-stat tabnum text-text">{val}</p>
                <p className="text-meta text-muted mt-0.5">{k}</p>
              </div>
            ))}
          </div>
          {(meta.mitre || []).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {meta.mitre.map((m, i) => <span key={i} className="mono-chip">{m}</span>)}
            </div>
          )}
        </div>
      </div>

      {/* Actions proposées (human-gated) */}
      {(report.proposed_actions || []).length > 0 && (
        <div className="card card-pad">
          <h2 className="mb-3">Actions proposées</h2>
          <div className="space-y-2">
            {report.proposed_actions.map((a, i) => (
              <div key={i} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface-alt px-3 py-2.5">
                <span className="text-body text-text">{a.label}</span>
                {a.requires_confirmation
                  ? <span className="badge-inconclusive text-meta">confirmation requise</span>
                  : <span className="badge-neutral text-meta">auto</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trace du graphe */}
      <div className="card card-pad">
        <h2 className="mb-4 flex items-center gap-2"><GitBranch className="h-4 w-4 text-muted" /> Trace d'investigation</h2>
        <Trace trace={report.trace} />
      </div>

      {/* Feedback analyste */}
      <div className="card card-pad sticky bottom-0">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <p className="text-body text-muted">Ce verdict est-il correct&nbsp;?</p>
          <div className="flex items-center gap-2">
            <button disabled={busy} onClick={() => onFeedback(report.decision)} className="btn-primary btn-sm">
              <CheckCircle2 className="h-4 w-4" /> Valider
            </button>
            {["malicious", "benign", "inconclusive"].filter(x => x !== report.decision).map(x => (
              <button key={x} disabled={busy} onClick={() => onFeedback(x)} className="btn-ghost btn-sm">
                Corriger → {VERDICT_UI[x].label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AiConsole() {
  const [reports, setReports] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [ip, setIp] = useState("");
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await aiApi.reports({ size: 50 });
      const items = data.items || [];
      setReports(items);
      setSelected((cur) => cur || items[0] || null);
    } catch (e) {
      setToast({ title: "Chargement impossible", desc: e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const runIp = async () => {
    if (!ip.trim()) return;
    setRunning(true);
    try {
      const report = await aiApi.investigateIp(ip.trim());
      setReports((prev) => [report, ...prev]);
      setSelected(report);
      setIp("");
    } catch (e) {
      setToast({ title: "Investigation échouée", desc: e.message });
    } finally {
      setRunning(false);
    }
  };

  const sendFeedback = async (verdict) => {
    if (!selected) return;
    setBusy(true);
    try {
      await aiApi.feedback(selected.id, verdict, "");
      setToast({ title: "Feedback enregistré", desc: `Verdict : ${verdict}` });
    } catch (e) {
      setToast({ title: "Feedback impossible", desc: e.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Pilier autonome"
        title="AI Console"
        desc="Investigations autonomes de bout en bout — verdict déterministe, rapport rédigé par IA bornée."
      >
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted pointer-events-none" />
            <input
              value={ip}
              onChange={(e) => setIp(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runIp()}
              placeholder="Investiguer une IP…"
              className="input-search w-56"
            />
          </div>
          <button onClick={runIp} disabled={running} className="btn-ai">
            {running ? <Spinner /> : <Bot className="h-4 w-4" />}
            {running ? "Analyse…" : "Lancer"}
          </button>
        </div>
      </PageHeader>

      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
        {/* File */}
        <div className="space-y-2">
          {loading ? (
            <div className="card card-pad space-y-3">
              {[...Array(5)].map((_, i) => <div key={i} className="skeleton h-14 rounded-lg" />)}
            </div>
          ) : reports.length === 0 ? (
            <EmptyState
              icon={Bot}
              title="Aucune investigation"
              desc="Lancez une investigation sur une IP, ou activez AI_AUTO_INVESTIGATE pour le mode autonome sur alertes critiques."
            />
          ) : (
            reports.map((r) => (
              <QueueItem key={r.id} report={r} active={selected?.id === r.id} onClick={() => setSelected(r)} />
            ))
          )}
        </div>

        {/* Rapport */}
        <div>
          {selected ? (
            <Report report={selected} onFeedback={sendFeedback} busy={busy} />
          ) : !loading ? (
            <EmptyState icon={Clock} title="Sélectionnez une investigation" desc="Choisissez un élément dans la file pour afficher le rapport complet." />
          ) : null}
        </div>
      </div>

      {toast && (
        <div className="fixed bottom-4 right-4 z-50">
          <Toast title={toast.title} desc={toast.desc} onClose={() => setToast(null)} />
        </div>
      )}
    </div>
  );
}
