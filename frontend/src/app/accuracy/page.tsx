"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { cn, formatNumber } from "@/lib/utils";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
  PieChart, Pie, Legend,
} from "recharts";

export default function AccuracyPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <MacroBar />
          <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden">
            <AccuracyContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function AccuracyContent() {
  const [accuracy, setAccuracy] = useState<any>(null);
  const [btStatus, setBtStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [acc, bt] = await Promise.all([
        api.getAccuracy().catch(() => null),
        api.getBacktestResults().catch(() => null),
      ]);
      setAccuracy(acc);
      setBtStatus(bt);
    } finally {
      setLoading(false);
    }
  }

  async function runBacktest() {
    setRunning(true);
    try {
      await api.triggerBacktest();
      // Poll status
      const interval = setInterval(async () => {
        const status = await api.getBacktestResults().catch(() => null);
        setBtStatus(status);
        if (status && !status.running) {
          clearInterval(interval);
          setRunning(false);
          loadData();
        }
      }, 10000);
    } catch {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border border-blue-600/40 border-t-blue-400 rounded-full animate-spin" />
      </div>
    );
  }

  const hasData = accuracy && accuracy.total_predictions > 0;
  const results = btStatus?.results;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-1">Validacion del modelo</p>
          <h2 className="text-2xl font-semibold text-white tracking-tight">Precision de Predicciones</h2>
          <p className="text-xs text-gray-500 mt-1">
            Compara predicciones historicas del scoring vs realidad del mercado
          </p>
        </div>
        <button
          onClick={runBacktest}
          disabled={running}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600/20 hover:bg-blue-600/30 disabled:opacity-40 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all"
        >
          {running ? (
            <>
              <div className="w-3.5 h-3.5 border border-blue-400/40 border-t-blue-400 rounded-full animate-spin" />
              Ejecutando... {btStatus?.progress || 0}%
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Ejecutar Backtest
            </>
          )}
        </button>
      </div>

      {/* Pipeline results if just ran */}
      {results && !results.error && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {results.pass_1 && (
            <StatCard label="Pase 1" value={`${results.pass_1.accuracy}%`} sub={`${results.pass_1.scores} predicciones`} />
          )}
          {results.pass_2 && (
            <StatCard label="Pase 2 (calibrado)" value={`${results.pass_2.accuracy}%`} sub={`Mejora: ${results.improvement > 0 ? "+" : ""}${results.improvement}%`} color={results.improvement > 0 ? "green" : "red"} />
          )}
          {results.ml && (
            <StatCard label="ML Accuracy" value={results.ml.accuracy ? `${results.ml.accuracy}%` : results.ml.status} sub={results.ml.records ? `${results.ml.records} registros` : ""} />
          )}
          {results.disabled_indicators && (
            <StatCard label="Indicadores desactivados" value={String(results.disabled_indicators.length)} sub={results.disabled_indicators.slice(0, 3).join(", ")} />
          )}
        </div>
      )}

      {!hasData ? (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-12 text-center space-y-4">
          <div className="text-4xl">📊</div>
          <h3 className="text-white font-semibold text-lg">Sin datos de backtest</h3>
          <p className="text-gray-500 text-sm max-w-md mx-auto">
            Necesitas ejecutar el backtest para que el sistema analice toda la historia de cada ticker,
            compare predicciones vs realidad, y calcule la precision real de cada indicador.
          </p>
          <p className="text-gray-600 text-xs">
            El proceso tarda ~2-3 minutos. Analiza ~5000 dias por ticker.
          </p>
        </div>
      ) : (
        <>
          {/* Overall accuracy */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-6 text-center">
              <p className={cn(
                "text-5xl font-bold num",
                accuracy.overall_accuracy >= 55 ? "text-green-400" : accuracy.overall_accuracy >= 50 ? "text-yellow-400" : "text-red-400"
              )}>
                {accuracy.overall_accuracy}%
              </p>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-2">Precision general</p>
              <p className="text-xs text-gray-500 mt-1">{accuracy.total_predictions} predicciones</p>
            </div>

            {/* Signal accuracy */}
            {accuracy.signal_accuracy && (
              <>
                {Object.entries(accuracy.signal_accuracy).map(([sig, data]: [string, any]) => (
                  <div key={sig} className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-6 text-center">
                    <p className={cn(
                      "text-3xl font-bold num",
                      data.accuracy >= 55 ? "text-green-400" : data.accuracy >= 50 ? "text-yellow-400" : "text-red-400"
                    )}>
                      {data.accuracy}%
                    </p>
                    <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-2">
                      Senal &quot;{sig}&quot;
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {data.correct}/{data.total} acertadas
                    </p>
                  </div>
                ))}
              </>
            )}
          </div>

          {/* Score bucket accuracy */}
          {accuracy.score_buckets && (
            <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-5">
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-4">
                Probabilidad real de suba segun rango de score
              </p>
              <p className="text-xs text-gray-500 mb-4">
                Si el sistema dice score 80-100, que % de las veces realmente subio al dia siguiente?
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={Object.entries(accuracy.score_buckets).map(([range, data]: [string, any]) => ({
                    range,
                    pct_up: data.pct_up,
                    count: data.count,
                  }))}>
                    <XAxis dataKey="range" stroke="#4b5563" tick={{ fill: "#6b7280", fontSize: 11 }} />
                    <YAxis stroke="#4b5563" tick={{ fill: "#6b7280", fontSize: 11 }} tickFormatter={(v: number) => `${v}%`} domain={[0, 100]} />
                    <Tooltip
                      contentStyle={{ background: "#0d1117", border: "1px solid #1a2233", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "#9ca3af" }}
                      formatter={(value: any) => [`${Number(value).toFixed(1)}%`, "Subio al dia sgte."]}
                    />
                    <Bar dataKey="pct_up" radius={[4, 4, 0, 0]}>
                      {Object.entries(accuracy.score_buckets).map(([range, data]: [string, any], idx: number) => (
                        <Cell key={idx} fill={data.pct_up >= 55 ? "#22c55e" : data.pct_up >= 45 ? "#eab308" : "#ef4444"} fillOpacity={0.7} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-[10px] text-gray-600 mt-2 text-center">
                Ideal: score 80-100 deberia tener &gt;70% de suba real. Score 0-20 deberia tener &lt;30%.
              </p>
            </div>
          )}

          {/* Indicator ranking */}
          {accuracy.indicator_ranking && (
            <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-5">
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-4">
                Ranking de indicadores por precision
              </p>
              <div className="space-y-2">
                {accuracy.indicator_ranking.map((ind: any, idx: number) => {
                  const isGood = ind.accuracy >= 55;
                  const isBad = ind.accuracy < 50;
                  return (
                    <div key={ind.name} className="flex items-center gap-3">
                      <span className="text-gray-700 num text-xs w-6 text-right">{idx + 1}</span>
                      <span className="text-sm text-gray-300 w-40 truncate">{ind.name}</span>
                      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className={cn("h-full rounded-full", isGood ? "bg-green-500" : isBad ? "bg-red-500" : "bg-yellow-500")}
                          style={{ width: `${Math.min(100, ind.accuracy)}%` }}
                        />
                      </div>
                      <span className={cn("num text-xs font-semibold w-12 text-right", isGood ? "text-green-400" : isBad ? "text-red-400" : "text-yellow-400")}>
                        {ind.accuracy}%
                      </span>
                      <span className="text-gray-600 text-[10px] w-16 text-right">{ind.correct}/{ind.total}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4 text-center">
      <p className={cn(
        "text-xl font-bold num",
        color === "green" ? "text-green-400" : color === "red" ? "text-red-400" : "text-white"
      )}>
        {value}
      </p>
      <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-1">{label}</p>
      {sub && <p className="text-[10px] text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}
