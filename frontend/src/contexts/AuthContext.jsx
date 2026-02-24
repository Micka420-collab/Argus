import { createContext, useContext, useState, useEffect, useCallback } from "react";

const AuthContext = createContext(null);

const API = "/api/v1/auth";

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  // Vérifier si déjà connecté au chargement
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/me`, { credentials: "include" });
        if (r.ok) {
          const data = await r.json();
          setUser(data);
          // Stocker aussi le token depuis le cookie si renvoyé en header
        }
      } catch {/* non connecté */}
      finally { setLoading(false); }
    })();
  }, []);

  const login = useCallback(async (username, password) => {
    const r = await fetch(`${API}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) {
      const err = await r.json();
      throw new Error(err.detail || "Erreur de connexion");
    }
    const data = await r.json();
    // Stocker le token en mémoire pour les requêtes API
    localStorage.setItem("soc_token", data.access_token);
    setUser(data.user);
    return data;
  }, []);

  const logout = useCallback(async () => {
    await fetch(`${API}/logout`, { method: "POST", credentials: "include" });
    localStorage.removeItem("soc_token");
    setUser(null);
  }, []);

  const refreshToken = useCallback(async () => {
    try {
      const r = await fetch(`${API}/refresh`, { method: "POST", credentials: "include" });
      if (r.ok) {
        const data = await r.json();
        localStorage.setItem("soc_token", data.access_token);
        return data.access_token;
      }
      await logout();
    } catch { await logout(); }
    return null;
  }, [logout]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans AuthProvider");
  return ctx;
};

export function hasPermission(user, action) {
  const perms = {
    admin:   ["read", "write", "delete", "admin"],
    analyst: ["read", "write"],
    viewer:  ["read"],
  };
  return perms[user?.role]?.includes(action) ?? false;
}
