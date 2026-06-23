/** @type {import('tailwindcss').Config} */
// Argus Design System — "Obsidian Signal"
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        bg:            "#0A0B0D",
        surface:       "#101216",
        "surface-alt": "#16181D",
        "surface-2":   "#1B1E24", // hover / raised
        border:        "#23262E",
        "border-soft": "#1A1D23", // chart gridlines, zebra divider
        text:          "#F2F4F7",
        muted:         "#9AA0AC", // ~5.6:1 on bg
        "muted-2":     "#6B7280", // decorative only
        accent:        "#4F8DFF",
        "accent-700":  "#3B6FE0",
        "accent-300":  "#8FB4FF",
        accent2:       "#5EE6D3", // AI / autonomous ONLY
        success:       "#3FB984", // benign
        warning:       "#E0A93C", // inconclusive / medium
        danger:        "#E5564B", // malicious / critical
        high:          "#E07B3C", // severity high
        info:          "#4F8DFF", // severity low === accent
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        eyebrow: ["0.75rem",  { lineHeight: "1rem",    letterSpacing: "0.08em" }],
        meta:    ["0.75rem",  { lineHeight: "1rem" }],
        body:    ["0.875rem", { lineHeight: "1.5rem" }],
        h2:      ["1.125rem", { lineHeight: "1.5rem",  fontWeight: "600" }],
        h1:      ["1.5rem",   { lineHeight: "2rem",    letterSpacing: "-0.01em", fontWeight: "600" }],
        stat:    ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.02em", fontWeight: "600" }],
        display: ["clamp(2.75rem, 6vw, 5rem)", { lineHeight: "1.05", letterSpacing: "-0.03em", fontWeight: "700" }],
      },
      borderRadius: { sm: "6px", DEFAULT: "8px", lg: "10px", xl: "12px", "2xl": "16px" },
      boxShadow: {
        card:         "0 1px 2px 0 rgba(0,0,0,0.30)",
        "card-hover": "0 4px 16px -4px rgba(0,0,0,0.45)",
        pop:          "0 8px 28px -8px rgba(0,0,0,0.55)",
        glow:         "0 0 0 1px rgba(79,141,255,0.25), 0 0 24px -6px rgba(79,141,255,0.35)",
        "glow-ai":    "0 0 0 1px rgba(94,230,211,0.30), 0 0 24px -4px rgba(94,230,211,0.35)",
        halo:         "0 0 40px -8px rgba(79,141,255,0.45)",
        "halo-ai":    "0 0 40px -8px rgba(94,230,211,0.45)",
        "focus-ring": "0 0 0 2px #0A0B0D, 0 0 0 4px #4F8DFF",
      },
      backgroundImage: {
        "hero-glow": "radial-gradient(60% 50% at 50% 0%, rgba(79,141,255,0.18) 0%, rgba(79,141,255,0) 70%)",
        "ai-glow":   "radial-gradient(50% 50% at 50% 0%, rgba(94,230,211,0.16) 0%, rgba(94,230,211,0) 70%)",
        grain:       "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
      },
      keyframes: {
        pulseRing: {
          "0%":   { boxShadow: "0 0 0 0 rgba(94,230,211,0.45)" },
          "70%":  { boxShadow: "0 0 0 7px rgba(94,230,211,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(94,230,211,0)" },
        },
        shimmer:    { "100%": { transform: "translateX(100%)" } },
        "fade-up":  { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        "toast-in": { "0%": { opacity: "0", transform: "translateY(8px) scale(0.98)" }, "100%": { opacity: "1", transform: "translateY(0) scale(1)" } },
        spin:       { to: { transform: "rotate(360deg)" } },
      },
      animation: {
        "pulse-ring": "pulseRing 1.6s ease-out infinite",
        shimmer:      "shimmer 1.6s infinite",
        "fade-up":    "fade-up 0.4s ease-out both",
        "toast-in":   "toast-in 0.2s ease-out both",
        "spin-slow":  "spin 0.8s linear infinite",
      },
      maxWidth: { content: "1200px", landing: "1120px" },
      transitionTimingFunction: { "out-soft": "cubic-bezier(0.16,1,0.3,1)" },
    },
  },
  plugins: [],
};
