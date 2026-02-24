import { useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Navbar from "./components/Navbar";
import Dashboard from "./components/Dashboard";
import AlertList from "./components/AlertList";
import AlertDetail from "./components/AlertDetail";
import IncidentList from "./components/IncidentList";
import Investigation from "./pages/Investigation";
import AssetList from "./pages/AssetList";
import RuleList from "./pages/RuleList";
import Login from "./pages/Login";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { useWebSocket } from "./hooks/useWebSocket";

// ---------------------------------------------------------------------------
// Notification sonore pour alertes critiques
// ---------------------------------------------------------------------------
function playAlertSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "square";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
  } catch (_) { /* Silencieux si audio non disponible */ }
}

// ---------------------------------------------------------------------------
// Route protégée — redirige vers /login si non authentifié
// ---------------------------------------------------------------------------
function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

// ---------------------------------------------------------------------------
// Shell principal (après authentification)
// ---------------------------------------------------------------------------
function AppShell() {
  const [newAlerts, setNewAlerts]       = useState([]);
  const [criticalCount, setCriticalCount] = useState(0);

  const handleAlert = useCallback((alert) => {
    const level = alert.rule?.level || 0;

    setNewAlerts(prev => [alert, ...prev].slice(0, 50));

    if (level >= 14) {
      setCriticalCount(prev => prev + 1);
      playAlertSound();
    }

    // Toast notification navigateur
    if (Notification.permission === "granted") {
      new Notification("🚨 SOC Alert", {
        body: alert.rule?.description || "Nouvelle alerte",
        icon: "/favicon.ico",
        tag:  "soc-alert",
      });
    }
  }, []);

  const { status: wsStatus } = useWebSocket(handleAlert);

  // Demander permission notifications navigateur au premier rendu
  if (Notification.permission === "default") {
    Notification.requestPermission();
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Navbar wsStatus={wsStatus} criticalCount={criticalCount} />

      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/"           element={<Dashboard newAlerts={newAlerts} />} />
          <Route path="/alerts"     element={<AlertList newAlerts={newAlerts} />} />
          <Route path="/alerts/:id" element={<AlertDetail />} />
          <Route path="/incidents"         element={<IncidentList />} />
          <Route path="/assets"            element={<AssetList />} />
          <Route path="/rules"             element={<RuleList />} />
          <Route path="/investigate/:ip"   element={<Investigation />} />
          <Route path="*"                  element={
            <div className="text-center py-20 text-slate-400">
              <p className="text-4xl mb-4">404</p>
              <p>Page introuvable</p>
            </div>
          } />
        </Routes>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App root avec AuthProvider + routing
// ---------------------------------------------------------------------------
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Page de login (publique) */}
          <Route path="/login" element={<Login />} />

          {/* Toutes les autres routes → protégées */}
          <Route path="/*" element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
