/**
 * Hook React — WebSocket pour alertes temps réel
 * Auth  : token JWT passé en query param (?token=...) car WS ne supporte pas les headers.
 * Retry : backoff exponentiel (1s → 2s → 4s … max 30s).
 */
import { useEffect, useRef, useState, useCallback } from "react";

function getWsUrl() {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const base  = `${proto}://${window.location.host}/api/v1/alerts/ws`;
  // Lire le token depuis localStorage (posé par AuthContext au login)
  const token = localStorage.getItem("access_token");
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

export function useWebSocket(onAlert) {
  const ws           = useRef(null);
  const retryCount   = useRef(0);
  const retryTimer   = useRef(null);
  const pingInterval = useRef(null);
  const [status, setStatus] = useState("connecting");

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;

    setStatus("connecting");
    const url = getWsUrl();

    // Pas de token → ne pas ouvrir la connexion (utilisateur non authentifié)
    if (!url.includes("token=")) {
      setStatus("disconnected");
      return;
    }

    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      setStatus("connected");
      retryCount.current = 0;
      pingInterval.current = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send("ping");
        }
      }, 30_000);
    };

    ws.current.onmessage = (event) => {
      if (event.data === "pong") return;
      try {
        const alert = JSON.parse(event.data);
        onAlert?.(alert);
      } catch (e) {
        console.error("WebSocket: erreur parsing message", e);
      }
    };

    ws.current.onclose = (event) => {
      setStatus("disconnected");
      clearInterval(pingInterval.current);

      // Code 4003 = token invalide → ne pas retenter (éviter boucle infinie)
      if (event.code === 4003 || event.code === 4001) {
        console.warn("WebSocket: auth refusée (code %d) — pas de reconnexion", event.code);
        setStatus("error");
        return;
      }

      // Backoff exponentiel (max 30s)
      const delay = Math.min(1000 * Math.pow(2, retryCount.current), 30_000);
      retryCount.current += 1;
      console.log(`WebSocket déconnecté — reconnexion dans ${delay / 1000}s`);
      retryTimer.current = setTimeout(connect, delay);
    };

    ws.current.onerror = () => setStatus("error");
  }, [onAlert]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(retryTimer.current);
      clearInterval(pingInterval.current);
      ws.current?.close();
    };
  }, [connect]);

  return { status };
}
