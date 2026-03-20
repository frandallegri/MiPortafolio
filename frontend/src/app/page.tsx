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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">Dashboard</h2>
        <p className="text-sm text-gray-500 mt-1">
          Resumen del mercado y oportunidades del día
        </p>
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
      <div className="bg-[#111827] rounded-xl border border-gray-800">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">
            Top Oportunidades del Día
          </h3>
          <span className="text-xs text-gray-500">Score &ge; 60%</span>
        </div>

        {topOpps.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No hay oportunidades detectadas. Ejecutá el scoring primero.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b border-gray-800">
                  <th className="text-left p-3 font-medium">Ticker</th>
                  <th className="text-left p-3 font-medium">Tipo</th>
                  <th className="text-right p-3 font-medium">Precio</th>
                  <th className="text-right p-3 font-medium">Var %</th>
                  <th className="text-right p-3 font-medium">Score</th>
                  <th className="text-center p-3 font-medium">Señal</th>
                  <th className="text-right p-3 font-medium">Confianza</th>
                  <th className="text-right p-3 font-medium">RSI</th>
                  <th className="text-right p-3 font-medium">Vol Rel</th>
                </tr>
              </thead>
              <tbody>
                {topOpps.map((opp) => {
                  const badge = signalBadge(opp.signal);
                  return (
                    <tr
                      key={opp.ticker}
                      className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors cursor-pointer"
                    >
                      <td className="p-3 font-medium text-white">{opp.ticker}</td>
                      <td className="p-3 text-gray-400 text-xs">{opp.asset_type}</td>
                      <td className="p-3 text-right text-white">
                        {opp.price ? formatMonto(opp.price) : "—"}
                      </td>
                      <td className={cn("p-3 text-right font-medium", opp.change_pct >= 0 ? "text-green-400" : "text-red-400")}>
                        {opp.change_pct != null ? formatPct(opp.change_pct) : "—"}
                      </td>
                      <td className={cn("p-3 text-right font-bold", scoreColor(opp.score))}>
                        {opp.score.toFixed(1)}
                      </td>
                      <td className="p-3 text-center">
                        <span className={cn("px-2 py-0.5 rounded text-xs font-medium border", badge.color)}>
                          {badge.text}
                        </span>
                      </td>
                      <td className="p-3 text-right text-gray-400">{opp.confidence?.toFixed(0)}%</td>
                      <td className="p-3 text-right text-gray-400">{opp.rsi?.toFixed(1) ?? "—"}</td>
                      <td className="p-3 text-right text-gray-400">{opp.volume_rel?.toFixed(1) ?? "—"}x</td>
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
}: {
  label: string;
  value: string;
  subValue?: string;
  positive?: boolean;
}) {
  return (
    <div className="bg-[#111827] rounded-xl border border-gray-800 p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-white">{value}</p>
      {subValue && (
        <p className={cn("text-sm font-medium mt-0.5", positive ? "text-green-400" : "text-red-400")}>
          {subValue}
        </p>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-gray-800 rounded" />
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 bg-gray-800 rounded-xl" />
        ))}
      </div>
      <div className="h-96 bg-gray-800 rounded-xl" />
    </div>
  );
}
