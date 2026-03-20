"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { formatMonto, formatPct, scoreColor, signalBadge, cn } from "@/lib/utils";

export default function DashboardPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <MacroBar />
          <main className="flex-1 p-6 overflow-auto">
            <DashboardContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function DashboardContent() {
  const [summary, setSummary] = useState<any>(null);
  const [topOpps, setTopOpps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [summaryData, scannerData] = await Promise.all([
          api.getPortfolioSummary().catch(() => null),
          api.getScanner(60).catch(() => ({ results: [] })),
        ]);
        setSummary(summaryData);
        setTopOpps(scannerData?.results?.slice(0, 10) || []);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <LoadingSkeleton />;
  }

  const today = new Date().toLocaleDateString("es-AR", {
    weekday: "long", day: "numeric", month: "long"
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-1">{today}</p>
          <h2 className="text-2xl font-semibold text-white tracking-tight">Dashboard</h2>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-gray-600 tracking-widest uppercase">Mercado</p>
          <div className="flex items-center gap-1.5 mt-1 justify-end">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse-green" />
            <span className="text-xs text-green-400">BYMA Abierto</span>
          </div>
        </div>
      </div>

      {/* Portfolio Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            label="Invertido"
            value={formatMonto(summary.total_invested)}
          />
          <StatCard
            label="Valor actual"
            value={formatMonto(summary.total_current_value)}
          />
          <StatCard
            label="P&L Total"
            value={formatMonto(summary.total_pnl)}
            subValue={formatPct(summary.total_pnl_pct)}
            positive={summary.total_pnl >= 0}
          />
          <StatCard
            label="Posiciones abiertas"
            value={String(summary.open_positions)}
          />
        </div>
      )}

      {/* Top Opportunities */}
      <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] card-glow overflow-hidden">
        <div className="p-4 border-b border-[#1a2233] flex items-center justify-between scanlines relative">
          <div>
            <h3 className="text-sm font-semibold text-white tracking-wide">TOP OPORTUNIDADES</h3>
            <p className="text-[10px] text-gray-600 mt-0.5 tracking-widest uppercase">Score ≥ 60 · Ordenado por probabilidad</p>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse-green" />
            <span className="text-[10px] text-gray-600 tracking-widest uppercase">Live</span>
          </div>
        </div>

        {topOpps.length === 0 ? (
          <div className="p-10 text-center">
            <p className="text-gray-600 text-sm">Sin oportunidades detectadas.</p>
            <p className="text-gray-700 text-xs mt-1">El sync histórico puede estar en progreso.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-gray-600 border-b border-[#1a2233] tracking-widest uppercase">
                  <th className="text-left px-4 py-3 font-medium">Ticker</th>
                  <th className="text-left px-4 py-3 font-medium">Tipo</th>
                  <th className="text-right px-4 py-3 font-medium">Precio</th>
                  <th className="text-right px-4 py-3 font-medium">Var</th>
                  <th className="px-4 py-3 font-medium">Score</th>
                  <th className="text-center px-4 py-3 font-medium">Señal</th>
                  <th className="text-right px-4 py-3 font-medium">RSI</th>
                </tr>
              </thead>
              <tbody>
                {topOpps.map((opp) => {
                  const badge = signalBadge(opp.signal);
                  const isBuy = opp.score >= 65;
                  return (
                    <tr
                      key={opp.ticker}
                      className={cn(
                        "border-b border-[#1a2233]/60 transition-colors cursor-pointer",
                        isBuy ? "row-buy" : "hover:bg-gray-900/30"
                      )}
                    >
                      <td className="px-4 py-3 font-semibold text-white tracking-wide">{opp.ticker}</td>
                      <td className="px-4 py-3 text-gray-600 text-[10px] tracking-widest uppercase">{opp.asset_type}</td>
                      <td className="px-4 py-3 text-right text-gray-300 num text-xs">
                        {opp.price ? formatMonto(opp.price) : "—"}
                      </td>
                      <td className={cn("px-4 py-3 text-right num text-xs font-medium", opp.change_pct >= 0 ? "text-green-400" : "text-red-400")}>
                        {opp.change_pct != null ? formatPct(opp.change_pct) : "—"}
                      </td>
                      <td className="px-4 py-3 w-36">
                        <ScoreBar score={opp.score} />
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={cn("px-2 py-0.5 rounded text-[10px] font-semibold tracking-widest border", badge.color)}>
                          {badge.text}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-500 num text-xs">{opp.rsi?.toFixed(1) ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  subValue,
  positive,
  icon,
}: {
  label: string;
  value: string;
  subValue?: string;
  positive?: boolean;
  icon?: React.ReactNode;
}) {
  const colorClass =
    positive === undefined ? "stat-neutral" : positive ? "stat-positive" : "stat-negative";
  return (
    <div className={`${colorClass} rounded-xl border border-[#1a2233] p-4 card-glow relative overflow-hidden`}>
      <div className="absolute top-0 right-0 w-16 h-16 opacity-5">
        {icon}
      </div>
      <p className="text-[10px] font-medium tracking-widest text-gray-600 uppercase mb-2">{label}</p>
      <p className="text-xl font-semibold text-white num">{value}</p>
      {subValue && (
        <p className={cn("text-sm font-medium mt-1 num", positive ? "text-green-400" : "text-red-400")}>
          {subValue}
        </p>
      )}
    </div>
  );
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score));
  const color =
    pct >= 70 ? "bg-green-500" : pct >= 60 ? "bg-yellow-500" : pct >= 40 ? "bg-gray-500" : "bg-red-500";
  const textColor =
    pct >= 70 ? "text-green-400 score-glow-green" : pct >= 60 ? "text-yellow-400 score-glow-yellow" : pct >= 40 ? "text-gray-400" : "text-red-400 score-glow-red";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full score-bar-fill ${color}`}
          style={{ "--bar-w": `${pct}%`, width: `${pct}%` } as React.CSSProperties}
        />
      </div>
      <span className={`text-xs num font-semibold w-8 text-right ${textColor}`}>{pct.toFixed(0)}</span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-gray-800/50 rounded" />
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 bg-gray-800/50 rounded-xl" />
        ))}
      </div>
      <div className="h-96 bg-gray-800/50 rounded-xl" />
    </div>
  );
}
