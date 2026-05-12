"use client";

import type { UsageReport } from "@/lib/usage-types";

const COLORS = ["#8ab4f8", "#7ab87a", "#e07964", "#a8a39a", "#c8a2c8"];

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
function fmtDollars(c: number): string {
  return `$${(c / 100).toFixed(2)}`;
}

export function UsageCharts({ report }: { report: UsageReport }) {
  const days = report.weeklyDays;
  const maxTokens = Math.max(1, ...days.map((d) => d.tokens));
  const W = 720, H = 180, padL = 32, padR = 8, padT = 12, padB = 28;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const barW = innerW / Math.max(1, days.length) - 4;

  const totalTokens = report.modelBreakdown.reduce((a, m) => a + m.tokens, 0) || 1;
  let acc = 0;
  const arcs = report.modelBreakdown.map((m, i) => {
    const start = acc;
    acc += (m.tokens / totalTokens) * Math.PI * 2;
    return { model: m.model, start, end: acc, color: COLORS[i % COLORS.length], cost: m.cost };
  });

  const cx = 80, cy = 80, r = 70;

  return (
    <div className="space-y-6">
      <section className="border border-border-dim rounded bg-bg-elev p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
            Daily tokens · last {days.length} days
          </div>
          <div className="mono text-[10px] text-text-muted">
            avg {fmt(report.forecast.avgPerDay)}/day · projected week {fmt(report.forecast.projectedWeek)}
          </div>
        </div>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
          <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#2e2e2e" />
          <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="#2e2e2e" />
          {days.map((d, i) => {
            const h = (d.tokens / maxTokens) * innerH;
            const x = padL + i * (innerW / days.length) + 2;
            return (
              <g key={d.date}>
                <rect x={x} y={H - padB - h} width={barW} height={h} fill="#8ab4f8" opacity="0.85">
                  <title>{`${d.date}: ${fmt(d.tokens)} tokens · ${fmtDollars(d.cost)}`}</title>
                </rect>
                <text x={x + barW / 2} y={H - padB + 14} textAnchor="middle" fill="#7a756d" fontSize="9" className="mono">
                  {d.date.slice(5)}
                </text>
              </g>
            );
          })}
          <text x={padL - 4} y={padT + 8} textAnchor="end" fill="#7a756d" fontSize="9" className="mono">{fmt(maxTokens)}</text>
          <text x={padL - 4} y={H - padB} textAnchor="end" fill="#7a756d" fontSize="9" className="mono">0</text>
        </svg>
      </section>

      <section className="border border-border-dim rounded bg-bg-elev p-4 grid grid-cols-[160px_minmax(0,1fr)] gap-4 items-center">
        <div>
          <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted mb-2">By model</div>
          <svg width={160} height={160} viewBox="0 0 160 160">
            {arcs.length === 0 ? (
              <circle cx={cx} cy={cy} r={r} fill="none" stroke="#2e2e2e" />
            ) : arcs.map((a) => {
              const x1 = cx + r * Math.sin(a.start);
              const y1 = cy - r * Math.cos(a.start);
              const x2 = cx + r * Math.sin(a.end);
              const y2 = cy - r * Math.cos(a.end);
              const large = a.end - a.start > Math.PI ? 1 : 0;
              const d = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
              return <path key={a.model} d={d} fill={a.color} opacity="0.85" />;
            })}
          </svg>
        </div>
        <ul className="space-y-1.5">
          {arcs.length === 0
            ? <li className="mono text-xs text-text-muted">No usage data yet.</li>
            : arcs.map((a) => (
                <li key={a.model} className="flex items-center gap-2 text-xs text-text-dim">
                  <span style={{ background: a.color }} className="inline-block w-3 h-3 rounded-sm" />
                  <span className="text-text">{a.model}</span>
                  <span className="text-text-muted mono ml-auto">
                    {fmt(report.modelBreakdown.find((m) => m.model === a.model)?.tokens ?? 0)} tok · {fmtDollars(a.cost)}
                  </span>
                </li>
              ))}
        </ul>
      </section>
    </div>
  );
}
