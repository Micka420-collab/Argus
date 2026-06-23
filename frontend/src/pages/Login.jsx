import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  ScanEye, Eye, EyeOff, AlertCircle, ArrowRight, Check, ShieldCheck, User, Lock,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const HIGHLIGHTS = [
  "Chaque alerte auto-triée jusqu'à un verdict",
  "Posture cryptographique post-quantique, en direct",
  "Enrichissement OSINT anonymisé",
];

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();

  const [form, setForm]       = useState({ username: "", password: "" });
  const [show, setShow]       = useState(false);
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);

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
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-bg">
      {/* Formulaire */}
      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <Link to="/welcome" className="flex items-center gap-2.5 font-semibold tracking-[-0.02em] text-lg mb-8">
            <span className="h-8 w-8 grid place-items-center rounded-lg bg-accent/10 ring-1 ring-accent/20">
              <ScanEye className="h-[18px] w-[18px] text-accent" />
            </span> Argus
          </Link>

          <h1>Connexion</h1>
          <p className="text-body text-muted mt-1">Bon retour sur votre console.</p>

          {error && (
            <div className="flex items-center gap-2.5 badge-malicious !rounded-lg !py-2.5 !px-3 mt-5 w-full">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span className="text-body">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="label">Identifiant</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted pointer-events-none" />
                <input
                  type="text" autoComplete="username" required
                  value={form.username}
                  onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
                  placeholder="admin"
                  className="input !pl-9"
                />
              </div>
            </div>

            <div>
              <label className="label">Mot de passe</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted pointer-events-none" />
                <input
                  type={show ? "text" : "password"} autoComplete="current-password" required
                  value={form.password}
                  onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
                  placeholder="••••••••"
                  className="input !pl-9 !pr-9"
                />
                <button type="button" onClick={() => setShow((s) => !s)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-text" aria-label="Afficher le mot de passe">
                  {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn-primary btn-lg w-full mt-2">
              {loading ? "Connexion…" : <>Se connecter <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>

          <p className="text-meta text-muted mt-6 flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-accent2" /> Protégé par TLS hybride ML-KEM
          </p>
        </div>
      </div>

      {/* Panneau marque (grain + glow) */}
      <div className="hidden lg:block relative grain bg-surface border-l border-border overflow-hidden">
        <div className="absolute inset-0 bg-hero-glow" />
        <div className="relative h-full flex flex-col justify-center px-14">
          <p className="eyebrow">SOC autonome · Post-quantique</p>
          <p className="text-[2rem] leading-[1.15] font-semibold tracking-[-0.02em] mt-3 max-w-md text-balance text-text">
            Le SOC qui s'investigue lui-même.
          </p>
          <ul className="mt-8 space-y-3 text-body text-muted">
            {HIGHLIGHTS.map((t) => (
              <li key={t} className="flex items-center gap-2.5">
                <Check className="h-4 w-4 text-accent" /> {t}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
