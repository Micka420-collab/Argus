import { Link, useLocation } from "react-router-dom";
import { Shield, Bell, Activity, Server, BookOpen, AlertTriangle, Atom } from "lucide-react";

const NAV_ITEMS = [
  { path: "/",          label: "Dashboard",  icon: Activity },
  { path: "/alerts",    label: "Alertes",    icon: Bell },
  { path: "/incidents", label: "Incidents",  icon: AlertTriangle },
  { path: "/assets",    label: "Assets",     icon: Server },
  { path: "/rules",     label: "Règles",     icon: BookOpen },
  { path: "/crypto",    label: "Post-Quantum", icon: Atom },
];

export default function Navbar({ wsStatus, criticalCount = 0 }) {
  const location = useLocation();

  const wsColor = {
    connected:    "bg-green-500",
    connecting:   "bg-yellow-500 animate-pulse",
    disconnected: "bg-red-500",
    error:        "bg-red-700",
  }[wsStatus] || "bg-gray-500";

  return (
    <nav className="bg-slate-900 border-b border-slate-700 px-4 py-3 flex items-center justify-between">
      {/* Logo */}
      <div className="flex items-center gap-2">
        <Shield className="text-blue-400" size={24} />
        <span className="text-white font-bold text-lg">SOC Platform</span>
        <span className="text-slate-400 text-xs ml-1">v2.0</span>
      </div>

      {/* Navigation */}
      <ul className="flex items-center gap-1">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const active = location.pathname === path ||
            (path !== "/" && location.pathname.startsWith(path));
          return (
            <li key={path}>
              <Link
                to={path}
                className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  active
                    ? "bg-blue-600 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon size={16} />
                {label}
                {label === "Alertes" && criticalCount > 0 && (
                  <span className="bg-red-600 text-white text-xs px-1.5 py-0.5 rounded-full">
                    {criticalCount}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>

      {/* Statut WebSocket */}
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${wsColor}`} title={`WebSocket: ${wsStatus}`} />
        <span className="text-slate-400 text-xs capitalize">{wsStatus}</span>
      </div>
    </nav>
  );
}
