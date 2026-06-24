/**
 * Argus — Système (administration)
 * Infos serveur + actions d'exploitation : mise à jour GitHub et redémarrage.
 * Les actions sont réservées au rôle admin (déléguées au conteneur argus-ops).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Settings, RefreshCw, DownloadCloud, RotateCcw, GitBranch, Cpu, ShieldCheck, AlertTriangle,
} from "lucide-react";
import { systemApi } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import { PageHeader, Card, StatTile, Spinner, Toast } from "../components/ui";

const OPS_STATE = {
  idle:    { label: "Inactif",       cls: "badge-neutral" },
  queued:  { label: "En file",       cls: "badge-inconclusive" },
  running: { label: "En cours…",     cls: "badge-inconclusive" },
  done:    { label: "Terminé",       cls: "badge-benign" },
  error:   { label: "Erreur",        cls: "badge-malicious" },
  unknown: { label: "Inconnu",       cls: "badge-neutral" },
};

export default function System() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [info, setInfo]       = useState(null);
  const [ops, setOps]         = useState({ state: "idle", detail: "" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy]       = useState("");      // "update" | "restart" | ""
  const [toast, setToast]     = useState(null);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await systemApi.info();
      setInfo(data);
      if (data.ops) setOps(data.ops);
    } catch (e) {
      setToast({ title: "Chargement impossible", desc: e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Sondage de l'état des opérations (après update/restart)
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await systemApi.opsStatus();
        setOps(s);
        if (s.state === "done" || s.state === "error" || s.state === "idle") {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setBusy("");
        }
      } catch (_) { /* l'API redémarre peut-être — on continue à sonder */ }
    }, 3000);
  }, []);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const trigger = async (kind) => {
    const msg = kind === "update"
      ? "Mettre à jour Argus depuis GitHub puis reconstruire ?\nLes services seront brièvement indisponibles (1-3 min)."
      : "Redémarrer l'application (api, frontend, nginx) ?\nCoupure de quelques secondes.";
    if (!window.confirm(msg)) return;
    setBusy(kind);
    setOps({ state: "queued", detail: kind });
    try {
      const res = kind === "update" ? await systemApi.update() : await systemApi.restart();
      setToast({ title: kind === "update" ? "Mise à jour lancée" : "Redémarrage lancé", desc: res.message });
      startPolling();
    } catch (e) {
      setBusy("");
      setOps({ state: "error", detail: e.message });
      setToast({ title: "Action impossible", desc: e.message });
    }
  };

  const st = OPS_STATE[ops.state] || OPS_STATE.unknown;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Système"
        desc="État du serveur Argus et actions d'exploitation."
      >
        <button onClick={load} className="btn-ghost" disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin-slow" : ""}`} /> Actualiser
        </button>
      </PageHeader>

      {/* Infos serveur */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile label="Version"     value={info?.version || "—"}     icon={GitBranch} />
        <StatTile label="Environnement" value={info?.environment || "—"} icon={Settings} />
        <StatTile label="Analyste IA" value={info?.llm_provider || "—"} icon={Cpu} />
        <StatTile label="JWT post-quantique" value={info?.pqc_jwt ? "Activé" : "Ed25519"} icon={ShieldCheck} />
      </div>

      {info?.llm_provider === "ollama" && (
        <p className="text-meta text-muted -mt-2">Modèle LLM local : <code className="text-text">{info?.llm_model || "—"}</code></p>
      )}

      {/* Opérations */}
      <Card className="card-pad space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-accent" />
            <h2 className="text-text font-medium">Exploitation</h2>
          </div>
          <span className={st.cls}>
            {ops.state === "running" || ops.state === "queued" ? <Spinner className="h-3.5 w-3.5" /> : <span className="badge-dot" />}
            {st.label}{ops.detail ? ` · ${ops.detail}` : ""}
          </span>
        </div>

        {!isAdmin && (
          <div className="flex items-start gap-2 text-meta text-muted">
            <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" />
            Ces actions sont réservées au rôle administrateur.
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-4">
          {/* Mise à jour */}
          <div className="rounded-xl border border-border p-4 space-y-3">
            <div className="flex items-center gap-2">
              <DownloadCloud className="h-4 w-4 text-accent" />
              <p className="text-text font-medium">Mettre à jour</p>
            </div>
            <p className="text-meta text-muted">
              Récupère la dernière version depuis GitHub (git pull) puis reconstruit
              et redémarre la stack. Données et configuration préservées.
            </p>
            <button
              onClick={() => trigger("update")}
              disabled={!isAdmin || !!busy}
              className="btn-primary btn-sm w-full"
            >
              {busy === "update" ? <Spinner className="h-4 w-4" /> : <DownloadCloud className="h-4 w-4" />}
              {busy === "update" ? "Mise à jour…" : "Mettre à jour depuis GitHub"}
            </button>
          </div>

          {/* Redémarrage */}
          <div className="rounded-xl border border-border p-4 space-y-3">
            <div className="flex items-center gap-2">
              <RotateCcw className="h-4 w-4 text-warning" />
              <p className="text-text font-medium">Redémarrer</p>
            </div>
            <p className="text-meta text-muted">
              Redémarre les services applicatifs (API, interface, reverse-proxy).
              Utile après un changement de configuration. ~10 s d'indisponibilité.
            </p>
            <button
              onClick={() => trigger("restart")}
              disabled={!isAdmin || !!busy}
              className="btn-ghost btn-sm w-full"
            >
              {busy === "restart" ? <Spinner className="h-4 w-4" /> : <RotateCcw className="h-4 w-4" />}
              {busy === "restart" ? "Redémarrage…" : "Redémarrer l'application"}
            </button>
          </div>
        </div>

        <p className="text-meta text-muted">
          Astuce : la mise à jour peut couper l'interface 1 à 3 min (reconstruction des images).
          Rechargez la page une fois l'opération « Terminé ».
        </p>
      </Card>

      {toast && (
        <div className="fixed bottom-6 right-6 z-50">
          <Toast title={toast.title} desc={toast.desc} onClose={() => setToast(null)} />
        </div>
      )}
    </div>
  );
}
