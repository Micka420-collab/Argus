import { useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import Dashboard from "./components/Dashboard";
import AlertList from "./components/AlertList";
import AlertDetail from "./components/AlertDetail";
import IncidentList from "./components/IncidentList";
import Investigation from "./pages/Investigation";
import AssetList from "./pages/AssetList";
import RuleList from "./pages/RuleList";
import Crypto from "./pages/Crypto";
import AiConsole from "./pages/AiConsole";
import Vdp from "./pages/Vdp";
import Landing from "./pages/Landing";
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
// Route protégée — guests → page de présentation publique
// ---------------------------------------------------------------------------
function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg">
        <div className="animate-spin-slow rounded-full h-10 w-10 border-2 border-accent border-t-transparent" />
      </div>
    );
  }
  if (!user) return <Navigate to="/welcome" replace />;
  return children;
}

// ---------------------------------------------------------------------------
// Shell applicatif (sidebar + topbar)
// ---------------------------------------------------------------------------
function AppShell() {
  const [newAlerts, setNewAlerts]         = useState([]);
  const [criticalCount, setCriticalCount] = useState(0);

  const handleAlert = useCallback((alert) => {
    const level = alert.rule?.level || 0;
    setNewAlerts(prev => [alert, ...prev].slice(0, 50));
    if (level >= 14) {
      setCriticalCount(prev => prev + 1);
      playAlertSound();
    }
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      new Notification("🚨 Argus Alert", {
        body: alert.rule?.description || "Nouvelle alerte",
        icon: "/favicon.ico",
        tag:  "soc-alert",
      });
    }
  }, []);

  const { status: wsStatus } = useWebSocket(handleAlert);

  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    Notification.requestPermission();
  }

  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar criticalCount={criticalCount} />
      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar wsStatus={wsStatus} criticalCount={criticalCount} />
        <main className="flex-1 overflow-auto mx-auto w-full max-w-content px-4 lg:px-8 py-6">
          <Routes>
            <Route path="/"                element={<Dashboard newAlerts={newAlerts} />} />
            <Route path="/alerts"          element={<AlertList newAlerts={newAlerts} />} />
            <Route path="/alerts/:id"      element={<AlertDetail />} />
            <Route path="/incidents"       element={<IncidentList />} />
            <Route path="/assets"          element={<AssetList />} />
            <Route path="/rules"           element={<RuleList />} />
            <Route path="/crypto"          element={<Crypto />} />
            <Route path="/ai"              element={<AiConsole />} />
            <Route path="/vdp"             element={<Vdp />} />
            <Route path="/investigate/:ip" element={<Investigation />} />
            <Route path="*" element={
              <div className="text-center py-20 text-muted">
                <p className="text-4xl mb-4 text-text">404</p>
                <p>Page introuvable</p>
              </div>
            } />
          </Routes>
        </main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App root
// ---------------------------------------------------------------------------
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Pages publiques */}
          <Route path="/welcome" element={<Landing />} />
          <Route path="/login"   element={<Login />} />
          {/* Application protégée */}
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
