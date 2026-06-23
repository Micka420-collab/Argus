/**
 * Argus UI kit — primitives partagés (design system "Obsidian Signal").
 * Réutilisés par les nouvelles pages (AI Console, Landing) et la refonte.
 */
import {
  ShieldAlert, ShieldCheck, HelpCircle, Loader2, Inbox, X, CheckCircle2,
  ArrowUpRight, ArrowDownRight,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------
export const Card = ({ className = "", hover = false, children }) => (
  <div className={`card ${hover ? "card-hover" : ""} ${className}`}>{children}</div>
);

// ---------------------------------------------------------------------------
// PageHeader
// ---------------------------------------------------------------------------
export function PageHeader({ eyebrow, title, desc, children }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
        <h1>{title}</h1>
        {desc && <p className="text-body text-muted mt-1 max-w-xl">{desc}</p>}
      </div>
      {children && <div className="flex items-center gap-2 shrink-0">{children}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Verdict & severity badges (icon + texte — jamais couleur seule)
// ---------------------------------------------------------------------------
const VERDICT = {
  malicious:    { cls: "badge-malicious",    Icon: ShieldAlert, label: "Malveillant" },
  benign:       { cls: "badge-benign",       Icon: ShieldCheck, label: "Bénin" },
  inconclusive: { cls: "badge-inconclusive", Icon: HelpCircle,  label: "Indéterminé" },
};
export function VerdictBadge({ verdict, confidence }) {
  const v = VERDICT[verdict] || VERDICT.inconclusive;
  const { cls, Icon, label } = v;
  return (
    <span className={cls}>
      <Icon className="h-3.5 w-3.5" /> {label}
      {confidence != null && <span className="tabnum opacity-80">· {confidence}%</span>}
    </span>
  );
}

const SEV = { critical: "badge-critical", high: "badge-high", medium: "badge-medium", low: "badge-low" };
export const SeverityBadge = ({ level }) => (
  <span className={`${SEV[level] || "badge-neutral"} capitalize`}>
    <span className="badge-dot" />{level}
  </span>
);

// ---------------------------------------------------------------------------
// Confidence meter
// ---------------------------------------------------------------------------
export function Confidence({ value = 0, verdict = "inconclusive" }) {
  const color = { malicious: "#E5564B", benign: "#3FB984", inconclusive: "#E0A93C" }[verdict];
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-meta text-muted">
        <span>Confiance</span><span className="tabnum text-text">{value}%</span>
      </div>
      <div className="meter"><i style={{ width: `${value}%`, background: color }} /></div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StatTile
// ---------------------------------------------------------------------------
export function StatTile({ label, value, delta, ai = false, halo = false, icon: Icon }) {
  const up = (delta ?? 0) >= 0;
  const haloCls = halo ? (ai ? "drop-shadow-[0_0_18px_rgba(94,230,211,0.45)]"
                             : "drop-shadow-[0_0_18px_rgba(79,141,255,0.45)]") : "";
  return (
    <div className="stat-tile card-hover">
      <div className="flex items-center justify-between">
        <p className="eyebrow">{label}</p>
        {Icon && <Icon className={`h-4 w-4 ${ai ? "text-accent2" : "text-muted"}`} />}
      </div>
      <span className={`stat tabnum ${ai ? "text-accent2" : ""} ${haloCls}`}>{value ?? "—"}</span>
      {delta != null && (
        <p className={`text-meta inline-flex items-center gap-1 ${up ? "text-danger" : "text-success"}`}>
          {up ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
          {Math.abs(delta)}% <span className="text-muted">vs préc.</span>
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyState
// ---------------------------------------------------------------------------
export function EmptyState({ icon: Icon = Inbox, title, desc, action }) {
  return (
    <div className="card card-pad py-16 flex flex-col items-center text-center gap-3">
      <div className="h-12 w-12 grid place-items-center rounded-xl bg-surface-alt border border-border">
        <Icon className="h-5 w-5 text-muted" />
      </div>
      <div>
        <p className="text-text font-medium">{title}</p>
        {desc && <p className="text-body text-muted mt-1 max-w-sm">{desc}</p>}
      </div>
      {action}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spinner / Skeleton
// ---------------------------------------------------------------------------
export const Spinner = ({ className = "h-4 w-4" }) => (
  <Loader2 className={`animate-spin-slow text-accent ${className}`} />
);

export const SkeletonRow = () => (
  <div className="flex items-center gap-3 py-3">
    <div className="skeleton h-4 w-4 rounded" />
    <div className="skeleton h-4 flex-1" />
    <div className="skeleton h-4 w-20" />
  </div>
);

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
export function Toast({ title, desc, onClose }) {
  return (
    <div className="card shadow-pop card-pad flex items-start gap-3 w-80 animate-toast-in" role="status">
      <CheckCircle2 className="h-5 w-5 text-success shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-body text-text font-medium">{title}</p>
        {desc && <p className="text-meta text-muted mt-0.5">{desc}</p>}
      </div>
      {onClose && (
        <button onClick={onClose} className="icon-btn h-7 w-7 -mr-1 -mt-1" aria-label="Fermer">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
