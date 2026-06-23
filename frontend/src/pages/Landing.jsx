/**
 * Argus — Landing publique (présentation du SOC).
 * Inspirée de neuralk.ai : near-black, glow radial, grain léger, value props nettes.
 */
import { Link } from "react-router-dom";
import {
  ScanEye, ArrowRight, BellOff, ShieldX, Radar, Crosshair,
  Bot, KeyRound, EyeOff, Bug, GitBranch, Github,
} from "lucide-react";

const VALUES = [
  { Icon: BellOff,   t: "Éliminer la surcharge d'alerte",
    d: "Chaque alerte est auto-investiguée jusqu'à un verdict — les analystes examinent des conclusions, pas des files." },
  { Icon: ShieldX,   t: "Minimiser les dégâts et les arrêts",
    d: "Un temps-jusqu'au-verdict réduit signifie des menaces contenues avant qu'elles ne se propagent." },
  { Icon: Radar, t: "La visibilité et le contexte",
    d: "Preuves corrélées, cartographie MITRE et contexte des assets sur une seule timeline." },
  { Icon: Crosshair, t: "Cibler les menaces critiques",
    d: "Des verdicts notés en confiance font remonter ce qui compte vraiment, classé par sévérité." },
];

const PILLARS = [
  { Icon: Bot,      kicker: "IA autonome",      t: "Des investigations qui se referment seules",
    d: "Un agent raisonne sur la télémétrie, le threat-intel et le contexte des assets pour rendre un verdict malveillant / bénin / indéterminé avec un rapport de preuves — et apprend de vos corrections." },
  { Icon: KeyRound, kicker: "Post-quantique",   t: "Une crypto qui survit à la menace quantique",
    d: "TLS hybride ML-KEM et CBOM en direct donnent une posture cryptographique notée en continu sur chaque asset." },
  { Icon: EyeOff,   kicker: "OSINT anonymisé",  t: "Enquêter sans s'exposer",
    d: "L'enrichissement threat-intel sort par un égress anonymisé : investiguer un adversaire ne le prévient jamais." },
  { Icon: Bug,      kicker: "VDP / Bug-Bounty", t: "Une porte d'entrée pour les chercheurs",
    d: "Divulgation de vulnérabilités et bug bounty intégrés routent les rapports directement dans votre pipeline d'incidents." },
];

function MiniMock() {
  return (
    <div className="rounded-2xl border border-border bg-surface shadow-glow overflow-hidden">
      <div className="h-9 flex items-center gap-1.5 px-4 border-b border-border bg-surface-alt">
        <span className="h-2.5 w-2.5 rounded-full bg-danger/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-warning/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-success/70" />
        <span className="ml-3 text-meta text-muted">argus — AI Console</span>
      </div>
      <div className="p-5 grid grid-cols-3 gap-3">
        {["Malveillant 96%", "Bénin 88%", "Indéterminé 41%"].map((v, i) => (
          <div key={i} className="bg-surface-alt rounded-lg p-3 border border-border">
            <div className="h-2 w-12 rounded bg-accent/40 mb-2" />
            <p className="text-body text-text font-semibold">{v}</p>
            <div className="meter mt-2"><i style={{ width: ["96%","88%","41%"][i], background: ["#E5564B","#3FB984","#E0A93C"][i] }} /></div>
          </div>
        ))}
        <div className="col-span-3 h-24 rounded-lg bg-surface-alt border border-border bg-ai-glow" />
      </div>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-bg text-text">
      {/* Nav */}
      <header className="sticky top-0 z-40 bg-bg/70 backdrop-blur border-b border-border/60">
        <nav className="mx-auto max-w-landing px-6 h-16 flex items-center">
          <Link to="/welcome" className="flex items-center gap-2.5 font-semibold tracking-[-0.02em]">
            <span className="h-8 w-8 grid place-items-center rounded-lg bg-accent/10 ring-1 ring-accent/20">
              <ScanEye className="h-[18px] w-[18px] text-accent" />
            </span> Argus
          </Link>
          <div className="ml-auto hidden md:flex items-center gap-7 text-body text-muted">
            <a href="#platform" className="hover:text-text">Plateforme</a>
            <a href="#pillars" className="hover:text-text">Capacités</a>
            <a href="#oss" className="hover:text-text">Open Source</a>
          </div>
          <Link to="/login" className="btn-primary btn-sm ml-7">
            Ouvrir la console <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </nav>
      </header>

      {/* Hero */}
      <section className="grain relative overflow-hidden">
        <div className="absolute inset-0 bg-hero-glow pointer-events-none" />
        <div className="relative mx-auto max-w-landing px-6 pt-24 pb-28 text-center">
          <span className="badge-neutral mx-auto"><span className="pulse-ai" /> SOC autonome · Post-quantique</span>
          <h1 className="text-display text-balance mt-6 mx-auto max-w-4xl">
            Le SOC qui<br />s'investigue lui-même.
          </h1>
          <p className="text-[1.125rem] leading-7 text-muted mt-6 mx-auto max-w-xl text-balance">
            Argus trie chaque alerte de façon autonome — verdict, preuves et rapport en quelques secondes.
            Confiance post-quantique intégrée. <span className="text-text">Plus de swivel-chair. Plus de fatigue d'alerte.</span>
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Link to="/login" className="btn-primary btn-lg">Ouvrir la console <ArrowRight className="h-4 w-4" /></Link>
            <a href="#platform" className="btn-ghost btn-lg">Voir comment ça marche</a>
          </div>
          <div className="mt-16 mx-auto max-w-3xl"><MiniMock /></div>
        </div>
      </section>

      {/* Trust strip */}
      <section className="border-y border-border/60">
        <div className="mx-auto max-w-landing px-6 py-10">
          <p className="eyebrow text-center mb-6">Bâti sur des standards ouverts · NIST PQC · MITRE ATT&amp;CK</p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6 opacity-60">
            {["MITRE ATT&CK", "NIST ML-KEM", "Wazuh", "Suricata", "Sigma", "MISP"].map((n) => (
              <span key={n} className="text-muted font-medium tracking-wide">{n}</span>
            ))}
          </div>
        </div>
      </section>

      {/* Value props */}
      <section id="platform" className="mx-auto max-w-landing px-6 py-24">
        <div className="text-center mb-14">
          <p className="eyebrow">Pourquoi Argus</p>
          <h2 className="text-h1 mt-2 text-balance">Des résultats, pas plus de dashboards.</h2>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {VALUES.map(({ Icon, t, d }) => (
            <div key={t} className="card-glass p-6">
              <div className="h-10 w-10 grid place-items-center rounded-lg bg-accent/10 ring-1 ring-accent/20 mb-4">
                <Icon className="h-5 w-5 text-accent" />
              </div>
              <h3 className="text-text font-semibold">{t}</h3>
              <p className="text-body text-muted mt-2 leading-6">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pillars */}
      <section id="pillars" className="mx-auto max-w-landing px-6 py-24 space-y-20">
        {PILLARS.map(({ Icon, kicker, t, d }, i) => (
          <div key={t} className={`grid lg:grid-cols-2 gap-10 items-center ${i % 2 ? "lg:[&>*:first-child]:order-2" : ""}`}>
            <div>
              <span className="badge-neutral"><Icon className="h-3.5 w-3.5 text-accent" /> {kicker}</span>
              <h2 className="text-h1 mt-4 text-balance">{t}</h2>
              <p className="text-body text-muted mt-3 leading-7 max-w-md">{d}</p>
            </div>
            <div className="card-glass aspect-[4/3] grid place-items-center">
              <Icon className="h-12 w-12 text-accent/30" />
            </div>
          </div>
        ))}
      </section>

      {/* Benchmarks */}
      <section className="border-y border-border/60 bg-surface/40">
        <div className="mx-auto max-w-landing px-6 py-20 grid sm:grid-cols-3 gap-10 text-center">
          {[["<30s", "Temps jusqu'au verdict"], ["3 états", "Verdict + confiance"], ["100%", "TLS hybride ML-KEM"]].map(([n, l]) => (
            <div key={l}>
              <p className="stat text-[2.75rem] tabnum drop-shadow-[0_0_24px_rgba(79,141,255,0.45)]">{n}</p>
              <p className="text-body text-muted mt-1">{l}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Open source */}
      <section id="oss" className="mx-auto max-w-landing px-6 py-24 text-center">
        <div className="card-glass max-w-2xl mx-auto p-8">
          <span className="badge-neutral mx-auto"><GitBranch className="h-3.5 w-3.5" /> Source-available</span>
          <h2 className="text-h1 mt-4">Open source. Non-commercial.</h2>
          <p className="text-body text-muted mt-3 max-w-lg mx-auto leading-7">
            Auto-hébergez toute la plateforme et auditez chaque ligne. Gratuit pour un usage non-commercial —
            contactez-nous pour un déploiement commercial.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <a href="https://github.com/" className="btn-ghost"><Github className="h-4 w-4" /> Voir le code</a>
            <Link to="/login" className="btn-primary">Ouvrir la console <ArrowRight className="h-4 w-4" /></Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto max-w-landing px-6 py-12 grid md:grid-cols-[1.5fr_repeat(3,1fr)] gap-8">
          <div>
            <div className="flex items-center gap-2.5 font-semibold tracking-[-0.02em]">
              <ScanEye className="h-5 w-5 text-accent" /> Argus
            </div>
            <p className="text-meta text-muted mt-3 max-w-xs">SOC autonome et post-quantique. Auto-hébergé.</p>
          </div>
          {[["Produit", ["Plateforme", "AI Console", "Post-Quantum"]],
            ["Sécurité", ["VDP", "Bug Bounty", "CBOM"]],
            ["Projet", ["Licence", "GitHub", "Contact"]]].map(([h, links]) => (
            <div key={h}>
              <p className="eyebrow mb-3">{h}</p>
              <ul className="space-y-2 text-body text-muted">
                {links.map((l) => <li key={l}><a href="#oss" className="hover:text-text">{l}</a></li>)}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-border py-5 text-center text-meta text-muted">
          © 2026 Argus · Licence source-available, non-commerciale
        </div>
      </footer>
    </div>
  );
}
