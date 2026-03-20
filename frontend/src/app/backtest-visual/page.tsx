"use client";

import { useEffect, useState, useMemo } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { cn, formatMonto, formatPct, formatNumber } from "@/lib/utils";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

const TICKERS = ["GGAL", "TECO2", "BMA", "PAMP", "BBAR", "TXAR", "ALUA", "YPFD", "RICH", "CAPX"];

interface ScoringEntry {
  date: string;
  score: number;
  signal?: string;
}

interface PriceEntry {
  date: string;
  close: number;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
}

interface EquityPoint {
  date: string;
  sistema: number;
  buyhold: number;
  signal?: string;
  score?: number;
}

interface BacktestStats {
  retornoSistema: number;
  retornoBuyHold: number;
  maxDDSistema: number;
  maxDDBuyHold: number;
  operaciones: number;
  compras: number;
  ventas: number;
}

function simulateStrategy(
  scoringHistory: ScoringEntry[],
  priceHistory: PriceEntry[]
): { equity: EquityPoint[]; stats: BacktestStats } {
  // Merge data by date
  const priceMap = new Map<string, number>();
  for (const p of priceHistory) {
    priceMap.set(p.date, p.close);
  }

  const scoreMap = new Map<string, ScoringEntry>();
  for (const s of scoringHistory) {
    scoreMap.set(s.date, s);
  }

  // Get sorted dates that exist in both datasets
  const allDates = [...new Set([...priceMap.keys()])].sort();
  const dates = allDates.filter((d) => priceMap.has(d));

  if (dates.length < 2) return { equity: [], stats: { retornoSistema: 0, retornoBuyHold: 0, maxDDSistema: 0, maxDDBuyHold: 0, operaciones: 0, compras: 0, ventas: 0 } };

  const CAPITAL_INICIAL = 1_000_000;
  let cash = CAPITAL_INICIAL;
  let shares = 0;
  let inPosition = false;
  let operaciones = 0;
  let compras = 0;
  let ventas = 0;

  const firstPrice = priceMap.get(dates[0])!;
  const bhShares = CAPITAL_INICIAL / firstPrice;

  const equity: EquityPoint[] = [];
  let peakSistema = CAPITAL_INICIAL;
  let peakBH = CAPITAL_INICIAL;
  let maxDDSistema = 0;
  let maxDDBuyHold = 0;

  for (const date of dates) {
    const price = priceMap.get(date)!;
    const scoring = scoreMap.get(date);
    const score = scoring?.score ?? null;

    // Strategy logic: check score and act
    if (score !== null) {
      if (score >= 65 && !inPosition) {
        // Compra: invest 100%
        shares = cash / price;
        cash = 0;
        inPosition = true;
        operaciones++;
        compras++;
      } else if (score <= 35 && inPosition) {
        // Venta: go to cash
        cash = shares * price;
        shares = 0;
        inPosition = false;
        operaciones++;
        ventas++;
      }
    }

    const sistemaEquity = inPosition ? shares * price : cash;
    const bhEquity = bhShares * price;

    // Drawdown calculation
    if (sistemaEquity > peakSistema) peakSistema = sistemaEquity;
    if (bhEquity > peakBH) peakBH = bhEquity;
    const ddSistema = ((peakSistema - sistemaEquity) / peakSistema) * 100;
    const ddBH = ((peakBH - bhEquity) / peakBH) * 100;
    if (ddSistema > maxDDSistema) maxDDSistema = ddSistema;
    if (ddBH > maxDDBuyHold) maxDDBuyHold = ddBH;

    equity.push({
      date,
      sistema: Math.round(sistemaEquity),
      buyhold: Math.round(bhEquity),
      signal: score !== null ? (score >= 65 ? "compra" : score <= 35 ? "venta" : "neutral") : undefined,
      score: score ?? undefined,
    });
  }

  const lastSistema = equity[equity.length - 1].sistema;
  const lastBH = equity[equity.length - 1].buyhold;

  return {
    equity,
    stats: {
      retornoSistema: ((lastSistema - CAPITAL_INICIAL) / CAPITAL_INICIAL) * 100,
      retornoBuyHold: ((lastBH - CAPITAL_INICIAL) / CAPITAL_INICIAL) * 100,
      maxDDSistema,
      maxDDBuyHold,
      operaciones,
      compras,
      ventas,
    },
  };
}

export default function BacktestVisualPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <MacroBar />
          <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden">
            <BacktestVisualContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function BacktestVisualContent() {
  const [ticker, setTicker] = useState(TICKERS[0]);
  const [scoringHistory, setScoringHistory] = useState<ScoringEntry[]>([]);
  const [priceHistory, setPriceHistory] = useState<PriceEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasBacktest, setHasBacktest] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Check if backtest data exists
  useEffect(() => {
    api.getAccuracy().then((data) => {
      setHasBacktest(data && data.total_predictions > 0);
    }).catch(() => {
      setHasBacktest(false);
    });
  }, []);

  // Load data when ticker changes
  useEffect(() => {
    loadData();
  }, [ticker]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [scoring, prices] = await Promise.all([
        api.getScoringHistory(ticker, 365).catch(() => []),
        api.getPriceHistory(ticker, 365).catch(() => []),
      ]);
      setScoringHistory(scoring || []);
      setPriceHistory(prices || []);
      if ((!scoring || scoring.length === 0) && hasBacktest === false) {
        setError("no_backtest");
      } else if (!scoring || scoring.length === 0) {
        setError("no_scoring");
      } else if (!prices || prices.length === 0) {
        setError("no_prices");
      }
    } catch {
      setError("load_error");
    } finally {
      setLoading(false);
    }
  }

  const { equity, stats } = useMemo(() => {
    if (scoringHistory.length === 0 || priceHistory.length === 0) {
      return { equity: [], stats: null };
    }
    return simulateStrategy(scoringHistory, priceHistory);
  }, [scoringHistory, priceHistory]);

  const formatDateLabel = (date: any) => {
    if (!date) return "";
    const parts = date.split("-");
    if (parts.length >= 3) return `${parts[2]}/${parts[1]}`;
    return date;
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-1">Simulacion de estrategia</p>
          <h2 className="text-2xl font-semibold text-white tracking-tight">Backtesting Visual</h2>
          <p className="text-xs text-gray-500 mt-1">
            Curva de equity: si hubieras seguido las senales del sistema, cuanto habrias ganado?
          </p>
        </div>

        {/* Ticker Selector */}
        <div className="flex items-center gap-3">
          <label className="text-[10px] tracking-widest text-gray-600 uppercase">Ticker</label>
          <select
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="bg-[#0d1117] border border-[#1a2233] rounded-lg px-4 py-2.5 text-sm text-white font-semibold focus:outline-none focus:border-blue-600/40 min-w-[140px]"
          >
            {TICKERS.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600/20 hover:bg-blue-600/30 disabled:opacity-40 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all"
          >
            <svg className={cn("w-3.5 h-3.5", loading && "animate-spin")} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {loading ? "Cargando" : "Actualizar"}
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-16 text-center space-y-3">
          <div className="w-6 h-6 border border-blue-600/40 border-t-blue-400 rounded-full animate-spin mx-auto" />
          <p className="text-[10px] text-gray-600 tracking-widest uppercase">Cargando datos de {ticker}...</p>
        </div>
      )}

      {/* No backtest data message */}
      {!loading && (error === "no_backtest" || (hasBacktest === false && scoringHistory.length === 0)) && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-12 text-center space-y-4">
          <div className="w-16 h-16 mx-auto rounded-full bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <h3 className="text-white font-semibold text-lg">Sin datos de scoring historico</h3>
          <p className="text-gray-500 text-sm max-w-md mx-auto">
            Ejecuta el backtest primero desde la pagina de Precision para que el sistema genere el historial de scores necesario para la simulacion.
          </p>
          <a
            href="/accuracy"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
            Ir a Precision
          </a>
        </div>
      )}

      {/* No scoring for this specific ticker */}
      {!loading && error === "no_scoring" && hasBacktest !== false && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-12 text-center space-y-3">
          <h3 className="text-white font-semibold">Sin historial de scoring para {ticker}</h3>
          <p className="text-gray-500 text-sm">
            No hay datos de scoring historico disponibles para este ticker. Proba con otro o ejecuta el backtest nuevamente.
          </p>
        </div>
      )}

      {/* No price data */}
      {!loading && error === "no_prices" && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-12 text-center space-y-3">
          <h3 className="text-white font-semibold">Sin datos de precios para {ticker}</h3>
          <p className="text-gray-500 text-sm">
            No se encontraron precios historicos. Verifica que el ticker tenga datos cargados.
          </p>
        </div>
      )}

      {/* Chart + Stats */}
      {!loading && !error && equity.length > 0 && stats && (
        <>
          {/* Strategy config info */}
          <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4">
            <div className="flex flex-wrap items-center gap-6 text-xs text-gray-500">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-400" />
                <span>Capital inicial: <span className="text-white font-semibold">{formatMonto(1_000_000)}</span></span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-400" />
                <span>Compra: score &ge; 65</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-400" />
                <span>Venta: score &le; 35</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-gray-600" />
                <span>Neutral: mantener posicion actual</span>
              </div>
              <span className="ml-auto text-gray-600">{equity.length} dias analizados</span>
            </div>
          </div>

          {/* Equity Curve Chart */}
          <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-5">
            <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-4">
              Curva de Equity &mdash; {ticker}
            </p>
            <div className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={equity} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2233" />
                  <XAxis
                    dataKey="date"
                    stroke="#4b5563"
                    tick={{ fill: "#6b7280", fontSize: 10 }}
                    tickFormatter={formatDateLabel}
                    interval="preserveStartEnd"
                    minTickGap={50}
                  />
                  <YAxis
                    stroke="#4b5563"
                    tick={{ fill: "#6b7280", fontSize: 10 }}
                    tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(2)}M`}
                    width={80}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#0d1117",
                      border: "1px solid #1a2233",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "#9ca3af" }}
                    labelFormatter={formatDateLabel}
                    formatter={(value: any, name: any) => [
                      formatMonto(Number(value)),
                      String(name) === "sistema" ? "Estrategia Sistema" : "Buy & Hold",
                    ]}
                  />
                  <Legend
                    formatter={(value: string) => (
                      <span className="text-xs text-gray-400">
                        {value === "sistema" ? "Estrategia Sistema" : "Buy & Hold"}
                      </span>
                    )}
                  />
                  <ReferenceLine
                    y={1_000_000}
                    stroke="#374151"
                    strokeDasharray="3 3"
                    label={{ value: "Capital Inicial", fill: "#4b5563", fontSize: 10, position: "right" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="sistema"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, fill: "#3b82f6" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="buyhold"
                    stroke="#6b7280"
                    strokeWidth={1.5}
                    dot={false}
                    strokeDasharray="5 5"
                    activeDot={{ r: 3, fill: "#6b7280" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {/* Retorno Sistema */}
            <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4 text-center">
              <p className={cn(
                "text-2xl font-bold num",
                stats.retornoSistema >= 0 ? "text-green-400" : "text-red-400"
              )}>
                {formatPct(stats.retornoSistema)}
              </p>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-1">Retorno Sistema</p>
            </div>

            {/* Retorno Buy & Hold */}
            <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4 text-center">
              <p className={cn(
                "text-2xl font-bold num",
                stats.retornoBuyHold >= 0 ? "text-green-400" : "text-red-400"
              )}>
                {formatPct(stats.retornoBuyHold)}
              </p>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-1">Retorno Buy &amp; Hold</p>
            </div>

            {/* Max DD Sistema */}
            <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4 text-center">
              <p className="text-2xl font-bold num text-red-400">
                -{formatNumber(stats.maxDDSistema)}%
              </p>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-1">Max DD Sistema</p>
            </div>

            {/* Max DD Buy & Hold */}
            <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4 text-center">
              <p className="text-2xl font-bold num text-red-400">
                -{formatNumber(stats.maxDDBuyHold)}%
              </p>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-1">Max DD Buy &amp; Hold</p>
            </div>

            {/* Operaciones */}
            <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4 text-center">
              <p className="text-2xl font-bold num text-white">{stats.operaciones}</p>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-1">Operaciones</p>
              <p className="text-[10px] text-gray-600 mt-0.5">
                <span className="text-green-500">{stats.compras}C</span>
                {" / "}
                <span className="text-red-500">{stats.ventas}V</span>
              </p>
            </div>

            {/* Diferencia */}
            <div className={cn(
              "rounded-xl border p-4 text-center",
              stats.retornoSistema > stats.retornoBuyHold
                ? "bg-green-500/5 border-green-500/20"
                : "bg-red-500/5 border-red-500/20"
            )}>
              <p className={cn(
                "text-2xl font-bold num",
                stats.retornoSistema > stats.retornoBuyHold ? "text-green-400" : "text-red-400"
              )}>
                {formatPct(stats.retornoSistema - stats.retornoBuyHold)}
              </p>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mt-1">Diferencia</p>
              <p className="text-[10px] text-gray-600 mt-0.5">
                {stats.retornoSistema > stats.retornoBuyHold ? "Sistema gana" : "Buy & Hold gana"}
              </p>
            </div>
          </div>

          {/* Disclaimer */}
          <div className="bg-[#0d1117]/50 rounded-xl border border-[#1a2233]/50 p-4">
            <p className="text-[10px] text-gray-600 leading-relaxed">
              <span className="text-gray-500 font-semibold uppercase tracking-widest">Nota:</span>{" "}
              Esta simulacion es puramente ilustrativa. No incluye comisiones, spreads, slippage ni impuestos.
              La estrategia invierte 100% del capital en cada senal de compra (score &ge; 65) y vende todo en senal de venta (score &le; 35).
              Resultados pasados no garantizan rendimientos futuros.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
