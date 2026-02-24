/**
 * MITRE ATT&CK Heatmap — Visualisation des techniques détectées
 */
import { useState } from "react";

const TACTICS = [
  { id: "TA0001", name: "Reconnaissance", short: "Recon" },
  { id: "TA0002", name: "Resource Development", short: "Dev" },
  { id: "TA0003", name: "Initial Access", short: "Init" },
  { id: "TA0004", name: "Execution", short: "Exec" },
  { id: "TA0005", name: "Persistence", short: "Persist" },
  { id: "TA0006", name: "Privilege Escalation", short: "PrivEsc" },
  { id: "TA0007", name: "Defense Evasion", short: "Evasion" },
  { id: "TA0008", name: "Credential Access", short: "Creds" },
  { id: "TA0009", name: "Discovery", short: "Discovery" },
  { id: "TA0010", name: "Lateral Movement", short: "Lateral" },
  { id: "TA0011", name: "Collection", short: "Collect" },
  { id: "TA0040", name: "Impact", short: "Impact" },
];

// Techniques clés à afficher par tactique (subset représentatif)
const TECHNIQUES_BY_TACTIC = {
  "TA0003": ["T1566", "T1190", "T1133", "T1200"],
  "TA0004": ["T1059.001", "T1059.003", "T1053", "T1047"],
  "TA0005": ["T1547.001", "T1053.005", "T1543.003", "T1546"],
  "TA0006": ["T1548.003", "T1068", "T1134", "T1055"],
  "TA0007": ["T1027", "T1055", "T1574", "T1070"],
  "TA0008": ["T1003.001", "T1110", "T1555", "T1550"],
  "TA0009": ["T1083", "T1082", "T1016", "T1033"],
  "TA0010": ["T1021", "T1091", "T1210", "T1534"],
  "TA0011": ["T1071", "T1071.004", "T1102", "T1573"],
  "TA0040": ["T1486", "T1490", "T1485", "T1491"],
};

function getHeatColor(count) {
  if (count === 0) return { bg: "bg-slate-800/60", text: "text-slate-600", glow: "" };
  if (count <= 2)  return { bg: "bg-blue-900/60",   text: "text-blue-300",   glow: "shadow-sm shadow-blue-500/20" };
  if (count <= 5)  return { bg: "bg-yellow-900/60", text: "text-yellow-300", glow: "shadow-sm shadow-yellow-500/30" };
  if (count <= 10) return { bg: "bg-orange-900/70", text: "text-orange-200", glow: "shadow-md shadow-orange-500/40" };
  return           { bg: "bg-red-900/80",    text: "text-red-200",    glow: "shadow-md shadow-red-500/50" };
}

export default function MitreHeatmap({ mitreCounts = {} }) {
  const [tooltip, setTooltip] = useState(null);

  // mitreCounts: { "T1059.001": 12, "T1003.001": 5, ... }
  const getCount = (tid) => mitreCounts[tid] || 0;

  return (
    <div className="bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-semibold">MITRE ATT&CK — Heatmap</h2>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-slate-700 inline-block" /> 0</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-800 inline-block" /> 1-2</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-800 inline-block" /> 3-5</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-800 inline-block" /> 6-10</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-800 inline-block" /> 10+</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="flex gap-1.5 min-w-max">
          {TACTICS.map(tactic => {
            const techniques = TECHNIQUES_BY_TACTIC[tactic.id] || [];
            const tacticTotal = techniques.reduce((s, t) => s + getCount(t), 0);
            const { bg: tacticBg } = getHeatColor(tacticTotal);

            return (
              <div key={tactic.id} className="flex flex-col gap-1 w-20">
                {/* En-tête tactique */}
                <div className={`rounded-lg px-1.5 py-2 text-center ${tacticTotal > 0 ? "bg-blue-900/40 border border-blue-700/40" : "bg-slate-800/40"}`}>
                  <div className="text-xs font-bold text-white truncate">{tactic.short}</div>
                  {tacticTotal > 0 && (
                    <div className="text-xs text-blue-300 font-mono">{tacticTotal}</div>
                  )}
                </div>

                {/* Techniques */}
                {techniques.map(tid => {
                  const count = getCount(tid);
                  const { bg, text, glow } = getHeatColor(count);
                  return (
                    <div
                      key={tid}
                      className={`rounded-md px-1.5 py-2 cursor-default transition-all ${bg} ${glow} hover:scale-105 hover:z-10 relative`}
                      onMouseEnter={() => setTooltip({ tid, count, tactic: tactic.name })}
                      onMouseLeave={() => setTooltip(null)}
                    >
                      <div className={`text-xs font-mono truncate ${text}`}>{tid}</div>
                      {count > 0 && (
                        <div className={`text-xs font-bold ${text}`}>{count}</div>
                      )}
                    </div>
                  );
                })}
                {techniques.length === 0 && (
                  <div className="rounded-md px-1.5 py-2 bg-slate-800/30 h-10 flex items-center justify-center">
                    <span className="text-slate-700 text-xs">—</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div className="mt-3 px-4 py-2 bg-slate-800 border border-slate-700 rounded-xl text-sm">
          <span className="text-blue-400 font-mono">{tooltip.tid}</span>
          <span className="text-slate-400 mx-2">·</span>
          <span className="text-slate-300">{tooltip.tactic}</span>
          <span className="text-slate-400 mx-2">·</span>
          <span className="text-white font-bold">{tooltip.count} détection{tooltip.count > 1 ? "s" : ""}</span>
        </div>
      )}
    </div>
  );
}
