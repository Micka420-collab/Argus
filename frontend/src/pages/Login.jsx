import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Eye, EyeOff, AlertCircle, Lock, User } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();

  const [form, setForm]     = useState({ username: "", password: "" });
  const [show, setShow]     = useState(false);
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);
  const [shake, setShake]   = useState(false);

  useEffect(() => { if (user) navigate("/"); }, [user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form.username, form.password);
      navigate("/");
    } catch (err) {
      setError(err.message);
      setShake(true);
      setTimeout(() => setShake(false), 600);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">

      {/* Fond animé avec particules */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-blue-900/5 rounded-full blur-3xl" />

        {/* Grille de fond */}
        <div className="absolute inset-0 opacity-[0.02]"
          style={{ backgroundImage: "linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)", backgroundSize: "50px 50px" }}
        />
      </div>

      {/* Card login */}
      <div className={`relative w-full max-w-md transition-transform duration-100 ${shake ? "animate-shake" : ""}`}>

        {/* Bordure lumineuse */}
        <div className="absolute -inset-px bg-gradient-to-r from-blue-500/50 via-indigo-500/50 to-blue-500/50 rounded-2xl blur-sm opacity-60" />

        <div className="relative bg-slate-900/95 backdrop-blur-xl rounded-2xl border border-slate-700/50 shadow-2xl p-8">

          {/* Logo + titre */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600/20 rounded-2xl border border-blue-500/30 mb-4">
              <Shield size={32} className="text-blue-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">SOC Platform</h1>
            <p className="text-slate-400 text-sm mt-1">Security Operations Center</p>
          </div>

          {/* Bannière erreur */}
          {error && (
            <div className="flex items-center gap-3 bg-red-900/30 border border-red-700/50 rounded-xl px-4 py-3 mb-6">
              <AlertCircle size={16} className="text-red-400 flex-shrink-0" />
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username */}
            <div className="space-y-1.5">
              <label className="text-slate-400 text-sm font-medium">Identifiant</label>
              <div className="relative">
                <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  autoComplete="username"
                  value={form.username}
                  onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
                  placeholder="admin"
                  required
                  className="w-full pl-10 pr-4 py-3 bg-slate-800/60 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-colors"
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label className="text-slate-400 text-sm font-medium">Mot de passe</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type={show ? "text" : "password"}
                  autoComplete="current-password"
                  value={form.password}
                  onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                  placeholder="••••••••"
                  required
                  className="w-full pl-10 pr-10 py-3 bg-slate-800/60 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShow(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white font-semibold rounded-xl transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 mt-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Connexion...
                </>
              ) : (
                <>
                  <Shield size={16} />
                  Se connecter
                </>
              )}
            </button>
          </form>

          {/* Footer sécurité */}
          <div className="mt-6 pt-5 border-t border-slate-800 text-center">
            <p className="text-slate-600 text-xs">
              🔒 Connexion chiffrée TLS · Accès réservé au personnel autorisé
            </p>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-8px); }
          40% { transform: translateX(8px); }
          60% { transform: translateX(-5px); }
          80% { transform: translateX(5px); }
        }
        .animate-shake { animation: shake 0.5s ease-in-out; }
      `}</style>
    </div>
  );
}
