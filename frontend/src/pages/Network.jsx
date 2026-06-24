/**
 * Argus — Réseau / Machines
 * Liste les machines surveillées (agents Wazuh) et explique comment en
 * connecter une nouvelle au SOC.
 */
import { useCallback, useEffect, useState } from "react";
import {
  Network as NetIcon, RefreshCw, Server, Copy, Check, Plus, Wifi, WifiOff,
} from "lucide-react";
import { networkApi } from "../services/api";
import { PageHeader, Card, StatTile, EmptyState, Spinner, Toast } from "../components/ui";

const STATUS = {
  active:          { cls: "badge-benign",       label: "Actif",        Icon: Wifi },
  disconnected:    { cls: "badge-high",         label: "Déconnecté",   Icon: WifiOff },
  never_connected: { cls: "badge-neutral",      label: "Jamais vu",    Icon: WifiOff },
  pending:         { cls: "badge-inconclusive", label: "En attente",   Icon: Spinner },
};

function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.never_connected;
  return <span className={s.cls}><span className="badge-dot" />{s.label}</span>;
}

function CopyBlock({ label, command }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch (_) { /* clipboard indisponible */ }
  };
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <p className="eyebrow">{label}</p>
        <button onClick={copy} className="icon-btn h-7 px-2 gap-1.5 text-meta">
          {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copié" : "Copier"}
        </button>
      </div>
      <pre className="bg-surface-alt border border-border rounded-lg p-3 text-meta text-muted overflow-x-auto whitespace-pre-wrap break-all">
        {command}
      </pre>
    </div>
  );
}

const fmtDate = (s) => { try { return s ? new Date(s).toLocaleString("fr-FR") : "—"; } catch { return s || "—"; } };

export default function Network() {
  const [data, setData]       = useState(null);
  const [enroll, setEnroll]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast]     = useState(null);
  const [showConnect, setShowConnect] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [agents, enr] = await Promise.all([
        networkApi.agents(),
        networkApi.enroll().catch(() => null),
      ]);
      setData(agents);
      setEnroll(enr);
    } catch (e) {
      setToast({ title: "Chargement impossible", desc: e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const agents  = data?.agents || [];
  const summary = data?.summary || {};

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Inventaire"
        title="Machines du réseau"
        desc="Les endpoints surveillés par Argus (agents Wazuh) et leur état en temps réel."
      >
        <button onClick={() => setShowConnect((v) => !v)} className="btn-primary">
          <Plus className="h-4 w-4" /> Connecter une machine
        </button>
        <button onClick={load} className="btn-ghost" disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin-slow" : ""}`} /> Actualiser
        </button>
      </PageHeader>

      {/* Connexion d'une machine */}
      {showConnect && enroll && (
        <Card className="card-pad space-y-4 border-accent/30">
          <div className="flex items-center gap-2">
            <NetIcon className="h-4 w-4 text-accent" />
            <h2 className="text-text font-medium">Connecter une machine au SOC</h2>
          </div>
          <p className="text-body text-muted">
            Serveur SOC (manager) : <code className="text-text">{enroll.manager_host}</code> ·
            ports <code className="text-text">{enroll.agent_port}/udp</code> &
            <code className="text-text"> {enroll.enrollment_port}/tcp</code>.
            Exécutez la commande sur la machine à surveiller :
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            <CopyBlock label="Linux (Debian/Ubuntu)" command={enroll.linux} />
            <CopyBlock label="Windows (PowerShell admin)" command={enroll.windows} />
          </div>
          <p className="text-meta text-muted">{enroll.note}</p>
        </Card>
      )}

      {/* Résumé */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile label="Total"        value={summary.total ?? 0}        icon={Server} />
        <StatTile label="Actives"      value={summary.active ?? 0}       icon={Wifi} />
        <StatTile label="Déconnectées" value={summary.disconnected ?? 0} icon={WifiOff} />
        <StatTile label="Jamais vues"  value={summary.never_connected ?? 0} icon={WifiOff} />
      </div>

      {/* Indisponibilité du manager */}
      {data && !data.available && (
        <Card className="card-pad">
          <p className="text-body text-text font-medium">Manager Wazuh injoignable</p>
          <p className="text-meta text-muted mt-1">
            {data.error || "Vérifiez que le service wazuh-manager est démarré et que WAZUH_API_PASSWORD est configuré."}
            {" "}La connexion d'une machine reste possible via le bouton ci-dessus.
          </p>
        </Card>
      )}

      {/* Liste */}
      {loading ? (
        <Card className="card-pad flex items-center gap-3 text-muted"><Spinner /> Chargement des machines…</Card>
      ) : agents.length === 0 ? (
        <EmptyState
          icon={Server}
          title="Aucune machine connectée"
          desc="Cliquez sur « Connecter une machine » et lancez la commande sur l'endpoint à surveiller."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-body">
              <thead>
                <tr className="text-meta text-muted text-left border-b border-border">
                  <th className="px-4 py-3 font-medium">Machine</th>
                  <th className="px-4 py-3 font-medium">Adresse IP</th>
                  <th className="px-4 py-3 font-medium">Système</th>
                  <th className="px-4 py-3 font-medium">État</th>
                  <th className="px-4 py-3 font-medium">Vue pour la dernière fois</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
                  <tr key={a.id} className="border-b border-border/60 hover:bg-surface-alt/50">
                    <td className="px-4 py-3">
                      <span className="text-text">{a.name || "—"}</span>
                      <span className="text-meta text-muted ml-2">#{a.id}</span>
                    </td>
                    <td className="px-4 py-3 tabnum text-muted">{a.ip || "—"}</td>
                    <td className="px-4 py-3 text-muted">{[a.os, a.os_version].filter(Boolean).join(" ") || "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
                    <td className="px-4 py-3 text-meta text-muted">{fmtDate(a.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 z-50">
          <Toast title={toast.title} desc={toast.desc} onClose={() => setToast(null)} />
        </div>
      )}
    </div>
  );
}
