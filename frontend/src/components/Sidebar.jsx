/**
 * Argus — Sidebar de navigation (design "Obsidian Signal").
 * Groupée, repliable, marque ScanEye, pied utilisateur avec déconnexion.
 */
import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  ScanEye, LayoutDashboard, Bell, AlertTriangle, Bot, Atom, Server,
  BookOpen, ChevronsLeft, LogOut, User, Bug, Target, Network, Settings,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const GROUPS = [
  {
    title: "Overview",
    items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }],
  },
  {
    title: "Détection",
    items: [
      { to: "/alerts",    label: "Alertes",    icon: Bell, badgeKey: "critical" },
      { to: "/incidents", label: "Incidents",  icon: AlertTriangle },
      { to: "/ai",        label: "AI Console", icon: Bot, live: true },
    ],
  },
  {
    title: "Exposition",
    items: [
      { to: "/exposure", label: "Surface (ASM)",    icon: Target },
      { to: "/vdp",      label: "VDP / Bug-Bounty", icon: Bug },
      { to: "/crypto",   label: "Post-Quantum",     icon: Atom },
    ],
  },
  {
    title: "Inventaire",
    items: [
      { to: "/assets",  label: "Assets",   icon: Server },
      { to: "/network", label: "Machines", icon: Network },
      { to: "/rules",   label: "Règles",   icon: BookOpen },
    ],
  },
  {
    title: "Administration",
    items: [
      { to: "/system", label: "Système", icon: Settings },
    ],
  },
];

export default function Sidebar({ criticalCount = 0 }) {
  const [open, setOpen] = useState(true);
  const { user, logout } = useAuth();

  const badgeFor = (key) => (key === "critical" && criticalCount > 0 ? criticalCount : null);

  return (
    <aside
      className={`${open ? "w-60" : "w-[68px]"} shrink-0 hidden md:flex flex-col
        bg-surface border-r border-border transition-[width] duration-200 ease-out-soft`}
    >
      {/* Marque */}
      <div className="h-14 flex items-center gap-2.5 px-4 border-b border-border">
        <span className="h-8 w-8 grid place-items-center rounded-lg bg-accent/10 ring-1 ring-accent/20 shrink-0">
          <ScanEye className="h-[18px] w-[18px] text-accent" />
        </span>
        {open && (
          <span className="font-semibold tracking-[-0.02em] text-text">
            Argus<span className="text-muted-2 text-meta ml-1 align-top">v3</span>
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-5">
        {GROUPS.map((group) => (
          <div key={group.title}>
            {open && <p className="eyebrow px-2 mb-1.5 text-muted-2">{group.title}</p>}
            <ul className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon, end, badgeKey, live }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={end}
                    title={!open ? label : undefined}
                    className={({ isActive }) =>
                      `flex items-center gap-3 h-10 px-2.5 rounded-lg text-body transition-colors ${
                        isActive
                          ? "bg-accent/10 text-accent"
                          : "text-muted hover:text-text hover:bg-surface-alt"
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon className={`h-[18px] w-[18px] shrink-0 ${isActive ? "text-accent" : ""}`} />
                        {open && <span className="flex-1 truncate">{label}</span>}
                        {open && live && <span className="pulse-ai" />}
                        {open && badgeFor(badgeKey) != null && (
                          <span className="badge-critical !px-1.5 !py-0 text-meta tabnum">
                            {badgeFor(badgeKey)}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Pied utilisateur */}
      <div className="border-t border-border p-2 space-y-1">
        <div className="flex items-center gap-3 h-11 px-2 rounded-lg">
          <div className="h-8 w-8 rounded-full bg-surface-2 grid place-items-center shrink-0">
            <User className="h-4 w-4 text-muted" />
          </div>
          {open && (
            <div className="flex-1 leading-tight min-w-0">
              <p className="text-body text-text truncate">{user?.full_name || user?.username || "Analyste"}</p>
              <p className="text-meta text-muted truncate capitalize">{user?.role || "viewer"}</p>
            </div>
          )}
          {open && (
            <button onClick={logout} className="icon-btn h-8 w-8" title="Se déconnecter" aria-label="Se déconnecter">
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
        <button
          onClick={() => setOpen((o) => !o)}
          className="w-full icon-btn justify-center"
          aria-label="Replier la barre latérale"
        >
          <ChevronsLeft className={`h-4 w-4 transition-transform ${open ? "" : "rotate-180"}`} />
        </button>
      </div>
    </aside>
  );
}
