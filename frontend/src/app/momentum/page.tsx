"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { cn, formatMonto, formatPct, formatNumber } from "@/lib/utils";

export default function MomentumPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <MacroBar />
          <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden">
            <MomentumContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function MomentumContent() {
  const [data, setData] = useState<any>(null);
  const [backtest, setBacktest] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [btLoading, setBtLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState("");
  const [dateData, setDateData] = useState<any>(null);
  const [dateLoading, setDateLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    loadMomentum();
  }, []);

  async function loadMomentum() {
    setLoading(true);
    setDateData(null);
    setSelectedDate("");
    try {
      const d = await api.getMomentum(30);
      setData(d);
    } catch { }
    setLoading(false);
  }

  async function loadBacktest() {
    setBtLoading(true);
    try {
      const bt = await api.getMomentumBacktest(5);
      setBacktest(bt);
    } catch { }
    setBtLoading(false);
  }

  async function loadAtDate() {
    if (!selectedDate) return;
    setDateLoading(true);
    try {
      const d = await api.getMomentumAtDate(selectedDate, 10);
      setDateData(d);
      setData(d);  // Reemplazar la tabla principal
    } catch { }
    setDateLoading(false);
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-1">Estrategia cuantitativa</p>
          <h2 className="text-2xl font-semibold text-white tracking-tight">Momentum Mensual</h2>
          <p className="text-xs text-gray-500 mt-1">
            Rankea acciones por momentum de 1-6 meses. Comprar las que mas subieron = 55-65% win rate.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadBacktest} disabled={btLoading}
            className="px-4 py-2 bg-green-600/20 hover:bg-green-600/30 disabled:opacity-40 text-green-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-green-600/30 transition-all">
            {btLoading ? "Calculando..." : "Ver Backtest"}
          </button>
          <button onClick={loadMomentum} disabled={loading}
            className="px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 disabled:opacity-40 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all">
            {loading ? "Cargando..." : "Actualizar"}
          </button>
        </div>
      </div>

      {/* Date picker - Maquina del tiempo */}
      <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase block mb-1">Viajar en el tiempo</label>
            <p className="text-[10px] text-gray-700 mb-2">Que recomendaba el sistema en una fecha pasada? Se cumplio?</p>
          </div>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            min="2024-01-01"
            max={new Date().toISOString().split("T")[0]}
            className="bg-[#080b10] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40"
          />
          <button
            onClick={loadAtDate}
            disabled={dateLoading || !selectedDate}
            className="px-4 py-2 bg-purple-600/20 hover:bg-purple-600/30 disabled:opacity-40 text-purple-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-purple-600/30 transition-all"
          >
            {dateLoading ? "Cargando..." : "Ver fecha"}
          </button>
          {dateData && (
            <button
              onClick={loadMomentum}
              className="px-4 py-2 bg-gray-700/20 hover:bg-gray-700/30 text-gray-400 text-xs tracking-widest uppercase rounded-lg border border-gray-700/30 transition-all"
            >
              Volver a hoy
            </button>
          )}
        </div>

        {/* Resultado de fecha historica */}
        {dateData?.top_stats && (
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              label={`Win Rate (top ${dateData.top_n})`}
              value={dateData.top_stats.win_rate != null ? `${dateData.top_stats.win_rate}%` : "—"}
              color={dateData.top_stats.win_rate >= 55 ? "green" : dateData.top_stats.win_rate >= 50 ? "yellow" : "red"}
            />
            <StatCard
              label="Retorno prom. top"
              value={dateData.top_stats.avg_return != null ? `${dateData.top_stats.avg_return}%` : "—"}
              color={dateData.top_stats.avg_return > 0 ? "green" : "red"}
            />
            <StatCard
              label="Ganaron"
              value={`${dateData.top_stats.winners}/${dateData.top_stats.total}`}
              color={dateData.top_stats.winners > dateData.top_stats.total / 2 ? "green" : "red"}
            />
            <StatCard
              label="Fecha consultada"
              value={dateData.as_of_date}
              color="white"
            />
          </div>
        )}
      </div>

      {/* Backtest results */}
      {backtest && !backtest.error && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-5">
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">
            Backtest: {backtest.strategy} — {backtest.period}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            <StatCard label="Win Rate" value={`${backtest.win_rate}%`} color={backtest.win_rate >= 55 ? "green" : backtest.win_rate >= 50 ? "yellow" : "red"} />
            <StatCard label="Retorno Total" value={`${backtest.total_return}%`} color={backtest.total_return > 0 ? "green" : "red"} />
            <StatCard label="Retorno Mensual Prom." value={`${backtest.avg_monthly_return}%`} color={backtest.avg_monthly_return > 0 ? "green" : "red"} />
            <StatCard label="Mejor Mes" value={`${backtest.best_month}%`} color="green" />
            <StatCard label="Peor Mes" value={`${backtest.worst_month}%`} color="red" />
          </div>
          <p className="text-xs text-gray-500">
            {backtest.total_months} meses analizados — {backtest.winning_months} ganadores
          </p>

          {/* Monthly results */}
          {backtest.monthly_results && (
            <div className="mt-4 space-y-1 max-h-48 overflow-y-auto">
              {backtest.monthly_results.map((m: any, idx: number) => (
                <div key={idx} className="flex items-center gap-3 text-xs">
                  <span className="text-gray-600 w-20">{m.date}</span>
                  <span className={cn("font-semibold num w-16 text-right", m.portfolio_return >= 0 ? "text-green-400" : "text-red-400")}>
                    {m.portfolio_return >= 0 ? "+" : ""}{m.portfolio_return}%
                  </span>
                  <span className="text-gray-600">{m.winners}/{m.total} ganaron</span>
                  <span className="text-gray-700 truncate">{m.selected?.join(", ")}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {backtest?.error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">
          {backtest.error}
        </div>
      )}

      {/* Momentum Rankings */}
      {loading ? (
        <div className="p-12 text-center">
          <div className="w-6 h-6 border border-blue-600/40 border-t-blue-400 rounded-full animate-spin mx-auto" />
          <p className="text-gray-600 text-xs mt-3">Calculando momentum...</p>
        </div>
      ) : data?.all_results ? (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] overflow-hidden">
          <div className="px-5 py-3 border-b border-[#1a2233] flex items-center justify-between">
            <p className="text-[10px] tracking-widest text-gray-600 uppercase">
              Ranking de Momentum — {data.total_assets} activos
              {data.as_of_date && <span className="text-purple-400 ml-2">(al {data.as_of_date})</span>}
            </p>
            <p className="text-[10px] text-gray-600">
              {data.date || data.as_of_date}
            </p>
          </div>

          {/* Header */}
          <div className="grid text-[10px] text-gray-600 tracking-widest uppercase border-b border-[#1a2233] px-4 py-2"
            style={{ gridTemplateColumns: dateData ? "32px 80px 80px 80px 80px 80px 80px 90px 1fr" : "32px 80px 80px 80px 80px 80px 80px 80px 1fr" }}>
            <div>#</div>
            <div>Ticker</div>
            <div className="text-right">Precio</div>
            <div className="text-right">1 Mes</div>
            <div className="text-right">3 Meses</div>
            <div className="text-right">6 Meses</div>
            <div className="text-right">Sharpe</div>
            {dateData ? <div className="text-right">Resultado Real</div> : <div className="text-center">Score</div>}
            <div>Senal</div>
          </div>

          {/* Rows */}
          {data.all_results.map((item: any) => {
            const isTop = item.rank <= 5;
            return (
              <div key={item.ticker}
                onClick={() => router.push(`/ticker/${item.ticker}`)}
                className={cn(
                  "grid items-center px-4 py-2.5 border-b border-[#1a2233]/40 cursor-pointer transition-colors",
                  isTop ? "bg-green-500/5 hover:bg-green-500/10" : "hover:bg-gray-900/30"
                )}
                style={{ gridTemplateColumns: dateData ? "32px 80px 80px 80px 80px 80px 80px 90px 1fr" : "32px 80px 80px 80px 80px 80px 80px 80px 1fr" }}>
                <div className={cn("text-xs num", isTop ? "text-green-400 font-bold" : "text-gray-700")}>{item.rank}</div>
                <div className="text-sm font-semibold text-blue-400">{item.ticker}</div>
                <div className="text-right text-xs text-gray-300 num">{formatMonto(item.price)}</div>
                <div className={cn("text-right text-xs num font-medium", (item.ret_1m || 0) >= 0 ? "text-green-400" : "text-red-400")}>
                  {item.ret_1m != null ? `${item.ret_1m >= 0 ? "+" : ""}${item.ret_1m}%` : "—"}
                </div>
                <div className={cn("text-right text-xs num font-medium", (item.ret_3m || 0) >= 0 ? "text-green-400" : "text-red-400")}>
                  {item.ret_3m != null ? `${item.ret_3m >= 0 ? "+" : ""}${item.ret_3m}%` : "—"}
                </div>
                <div className={cn("text-right text-xs num font-medium", (item.ret_6m || 0) >= 0 ? "text-green-400" : "text-red-400")}>
                  {item.ret_6m != null ? `${item.ret_6m >= 0 ? "+" : ""}${item.ret_6m}%` : "—"}
                </div>
                <div className={cn("text-right text-xs num", item.sharpe >= 1 ? "text-green-400" : item.sharpe >= 0 ? "text-gray-400" : "text-red-400")}>
                  {item.sharpe?.toFixed(2)}
                </div>
                {dateData ? (
                  <div className="text-right">
                    {item.actual_return_1m != null ? (
                      <span className={cn("text-xs num font-bold", item.actual_return_1m >= 0 ? "text-green-400" : "text-red-400")}>
                        {item.actual_return_1m >= 0 ? "+" : ""}{item.actual_return_1m}%
                        {item.actual_won ? " ✓" : " ✗"}
                      </span>
                    ) : <span className="text-gray-700 text-xs">pendiente</span>}
                  </div>
                ) : (
                  <div className="text-center">
                    <span className={cn(
                      "inline-block w-10 text-center text-xs font-bold num rounded",
                      item.score >= 65 ? "text-green-400" : item.score <= 35 ? "text-red-400" : "text-yellow-400"
                    )}>{item.score}</span>
                  </div>
                )}
                <div>
                  <span className={cn(
                    "px-2 py-0.5 rounded text-[10px] font-semibold tracking-widest border",
                    item.signal === "compra" ? "text-green-400 border-green-500/30 bg-green-500/10" :
                      item.signal === "venta" ? "text-red-400 border-red-500/30 bg-red-500/10" :
                        "text-gray-500 border-gray-700/30 bg-gray-700/10"
                  )}>
                    {item.signal === "compra" ? "COMPRA" : item.signal === "venta" ? "VENTA" : "NEUTRAL"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-12 text-center text-gray-600">Sin datos de momentum</div>
      )}

      {/* Explicacion */}
      <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-5 text-xs text-gray-500 space-y-2">
        <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-2">Como funciona</p>
        <p><strong className="text-gray-400">Momentum:</strong> Las acciones que subieron en los ultimos 3-6 meses tienden a seguir subiendo. Es la anomalia mas robusta en finanzas (Jegadeesh & Titman, 1993).</p>
        <p><strong className="text-gray-400">Score:</strong> Combina retorno 3m (40%), retorno 6m (30%), retorno 1m (15%), fuerza de tendencia (10%), fuerza relativa vs mercado (5%).</p>
        <p><strong className="text-gray-400">Estrategia:</strong> Comprar las top 5 cada mes. Mantener 1 mes. Rebalancear.</p>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-[#080b10] rounded-lg border border-[#1a2233] p-3 text-center">
      <p className={cn("text-xl font-bold num",
        color === "green" ? "text-green-400" : color === "red" ? "text-red-400" : "text-yellow-400"
      )}>{value}</p>
      <p className="text-[9px] tracking-widest text-gray-600 uppercase mt-1">{label}</p>
    </div>
  );
}
