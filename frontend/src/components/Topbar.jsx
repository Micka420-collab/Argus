/**
 * Argus — Topbar : recherche, plage temporelle, statut WebSocket, notifications.
 */
import { Search, Bell, Wifi, WifiOff, ScanEye } from "lucide-react";

const WS = {
  connected:    { dot: "bg-success", label: "Live",    Icon: Wifi },
  connecting:   { dot: "bg-warning", label: "Liaison…", Icon: Wifi },
  disconnected: { dot: "bg-danger",  label: "Hors-ligne", Icon: WifiOff },
  error:        { dot: "bg-danger",  label: "Erreur",  Icon: WifiOff },
};

export default function Topbar({ wsStatus = "disconnected", criticalCount = 0 }) {
  const ws = WS[wsStatus] || WS.disconnected;

  return (
    <header className="h-14 sticky top-0 z-30 bg-bg/80 backdrop-blur border-b border-border
                       flex items-center gap-3 px-4 lg:px-6">
      {/* Marque (mobile, la sidebar est masquée) */}
      <span className="md:hidden flex items-center gap-2 font-semibold text-text">
        <ScanEye className="h-5 w-5 text-accent" /> Argus
      </span>

      {/* Recherche globale */}
      <div className="relative w-full max-w-md hidden sm:block">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted pointer-events-none" />
        <input className="input-search" placeholder="Rechercher alertes, assets, IOCs…" />
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* Statut WebSocket (point + icône + label, jamais couleur seule) */}
        <span className="badge-neutral" title={`WebSocket : ${wsStatus}`}>
          <span className={`inline-block h-2 w-2 rounded-full ${ws.dot}`} />
          <ws.Icon className="h-3.5 w-3.5" /> {ws.label}
        </span>

        {/* Notifications */}
        <button className="icon-btn relative" aria-label="Notifications">
          <Bell className="h-[18px] w-[18px]" />
          {criticalCount > 0 && (
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-danger ring-2 ring-bg" />
          )}
        </button>
      </div>
    </header>
  );
}
