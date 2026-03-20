"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { formatMonto, formatPct, formatNumber, scoreColor, scoreBgColor, signalBadge, cn } from "@/lib/utils";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Cell,
} from "recharts";

/* ──────────────────────────────────────────────
   Helpers
   ────────────────────────────────────────────── */

const MONTH_NAMES = [
  "Ene", "Feb", "Mar", "Abr", "May", "Jun",
  "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
];

function computeSMA(data: { close: number }[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += data[j].close;
      result.push(sum / period);
    }
  }
  return result;
}

function StatCard({ label, value, suffix, color }: { label: string; value: string | number | null | undefined; suffix?: string; color?: string }) {
  return (
    <div className="bg-[#0d1117] border border-[#1a2233] rounded-xl p-4">
      <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-2">{label}</p>
      <p className={cn("text-2xl font-bold num", color || "text-gray-200")}>
        {value != null ? value : "—"}
        {suffix && <span className="text-sm text-gray-500 ml-1">{suffix}</span>}
      </p>
    </div>
  );
}

/* ──────────────────────────────────────────────
   Main Page
   ────────────────────────────────────────────── */

export default function TickerPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <MacroBar />
          <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden bg-[#0b0e14]">
            <TickerContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function TickerContent() {
  const params = useParams<{ ticker: string }>();
  const ticker = decodeURIComponent(params.ticker ?? "");

  const [scoreData, setScoreData] = useState<any>(null);
  const [priceHistory, setPriceHistory] = useState<any[]>([]);
  const [scoringHistory, setScoringHistory] = useState<any[]>([]);
  const [tickerHistory, setTickerHistory] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  /* ── Load all data ── */
  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const [score, prices, scoring, history] = await Promise.all([
          api.getScore(ticker).catch(() => null),
          api.getPriceHistory(ticker, 365).catch(() => []),
          api.getScoringHistory(ticker, 180).catch(() => []),
          api.getTickerHistory(ticker).catch(() => null),
        ]);
        if (cancelled) return;
        setScoreData(score);
        setPriceHistory(prices);
        setScoringHistory(scoring);
        setTickerHistory(history);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [ticker]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 space-y-4">
        <div className="w-8 h-8 border-2 border-blue-600/40 border-t-blue-400 rounded-full animate-spin" />
        <p className="text-[10px] text-gray-600 tracking-widest uppercase">Cargando análisis de {ticker}...</p>
      </div>
    );
  }

  const price = scoreData?.price ?? priceHistory[priceHistory.length - 1]?.close;
  const changePct = scoreData?.change_pct ?? null;
  const score = scoreData?.score ?? 0;
  const signal = scoreData?.signal ?? "neutral";
  const assetType = scoreData?.asset_type ?? "";
  const badge = signalBadge(signal);

  /* Stats from tickerHistory */
  const stats = tickerHistory ?? {};

  /* Return distribution */
  const returnDist: { bin: string; count: number; positive: boolean }[] = stats.return_distribution ?? [];

  /* Monthly seasonality */
  const seasonality: { month: number; avg_return: number; win_rate: number }[] = stats.seasonality ?? [];

  /* Supports & resistances */
  const supports: { price: number; strength: number; distance_pct: number }[] = stats.supports ?? [];
  const resistances: { price: number; strength: number; distance_pct: number }[] = stats.resistances ?? [];

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto">
      {/* ════════════════════ HEADER ════════════════════ */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/scanner"
            className="flex items-center justify-center w-9 h-9 rounded-lg bg-[#0d1117] border border-[#1a2233] text-gray-500 hover:text-white hover:border-gray-600 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-white tracking-tight">{ticker}</h1>
              {assetType && (
                <span className="px-2.5 py-0.5 rounded-md text-[10px] font-semibold tracking-widest uppercase bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {assetType}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1">
              {price != null && (
                <span className="text-lg font-semibold text-gray-200 num">{formatMonto(price)}</span>
              )}
              {changePct != null && (
                <span className={cn("text-sm font-semibold num", changePct >= 0 ? "text-green-400" : "text-red-400")}>
                  {formatPct(changePct)}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Score circle + signal */}
        <div className="flex items-center gap-4">
          <div className={cn("w-20 h-20 rounded-full flex flex-col items-center justify-center border-2", scoreBgColor(score))}>
            <span className={cn("text-2xl font-bold num", scoreColor(score))}>{score.toFixed(0)}</span>
            <span className="text-[8px] text-gray-500 uppercase tracking-widest">Score</span>
          </div>
          <span className={cn("px-3 py-1.5 rounded-lg text-[10px] font-semibold tracking-widest border uppercase", badge.color)}>
            {badge.text}
          </span>
        </div>
      </div>

      {/* ════════════════════ CANDLESTICK CHART ════════════════════ */}
      <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4">
        <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">Gráfico de Precios</p>
        <CandlestickChart priceHistory={priceHistory} />
      </div>

      {/* ════════════════════ SCORE HISTORY ════════════════════ */}
      {scoringHistory.length > 0 && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4">
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">Historial de Score (180 días)</p>
          <ScoreHistoryChart data={scoringHistory} />
        </div>
      )}

      {/* ════════════════════ STATISTICS CARDS ════════════════════ */}
      <div>
        <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">Estadísticas</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <StatCard
            label="Retorno Anualizado"
            value={stats.annualized_return != null ? formatNumber(stats.annualized_return, 2) : null}
            suffix="%"
            color={stats.annualized_return >= 0 ? "text-green-400" : "text-red-400"}
          />
          <StatCard
            label="Volatilidad Anual"
            value={stats.annual_volatility != null ? formatNumber(stats.annual_volatility, 2) : null}
            suffix="%"
            color="text-yellow-400"
          />
          <StatCard
            label="Sharpe Ratio"
            value={stats.sharpe_ratio != null ? formatNumber(stats.sharpe_ratio, 2) : null}
            color={stats.sharpe_ratio >= 1 ? "text-green-400" : stats.sharpe_ratio >= 0 ? "text-yellow-400" : "text-red-400"}
          />
          <StatCard
            label="Max Drawdown"
            value={stats.max_drawdown != null ? formatNumber(stats.max_drawdown, 2) : null}
            suffix="%"
            color="text-red-400"
          />
          <StatCard
            label="Win Rate"
            value={stats.win_rate != null ? formatNumber(stats.win_rate, 1) : null}
            suffix="%"
            color={stats.win_rate >= 50 ? "text-green-400" : "text-red-400"}
          />
          <StatCard
            label="Beta vs Mercado"
            value={stats.beta != null ? formatNumber(stats.beta, 2) : null}
            color="text-blue-400"
          />
          <StatCard
            label="Racha Actual"
            value={stats.current_streak != null ? `${stats.current_streak > 0 ? "+" : ""}${stats.current_streak} días` : null}
            color={stats.current_streak > 0 ? "text-green-400" : stats.current_streak < 0 ? "text-red-400" : "text-gray-400"}
          />
          <StatCard
            label="Volumen Promedio 30d"
            value={stats.avg_volume_30d != null ? formatNumber(stats.avg_volume_30d, 0) : null}
            color="text-gray-300"
          />
          <StatCard
            label="Días de Datos"
            value={stats.data_days != null ? formatNumber(stats.data_days, 0) : null}
            color="text-gray-300"
          />
        </div>
      </div>

      {/* ════════════════════ RETURN DISTRIBUTION ════════════════════ */}
      {returnDist.length > 0 && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4">
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">Distribución de Retornos Diarios</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={returnDist} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <XAxis
                  dataKey="bin"
                  tick={{ fill: "#6b7280", fontSize: 10 }}
                  axisLine={{ stroke: "#1a2233" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#6b7280", fontSize: 10 }}
                  axisLine={{ stroke: "#1a2233" }}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{ background: "#0d1117", border: "1px solid #1a2233", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#9ca3af" }}
                  itemStyle={{ color: "#e5e7eb" }}
                />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {returnDist.map((entry, idx) => (
                    <Cell key={idx} fill={entry.positive ? "#22c55e" : "#ef4444"} fillOpacity={0.7} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {(stats.skewness != null || stats.kurtosis != null) && (
            <div className="flex gap-6 mt-3">
              {stats.skewness != null && (
                <p className="text-xs text-gray-500">
                  <span className="tracking-widest uppercase text-[10px] text-gray-600">Asimetría:</span>{" "}
                  <span className="num text-gray-300">{formatNumber(stats.skewness, 3)}</span>
                </p>
              )}
              {stats.kurtosis != null && (
                <p className="text-xs text-gray-500">
                  <span className="tracking-widest uppercase text-[10px] text-gray-600">Curtosis:</span>{" "}
                  <span className="num text-gray-300">{formatNumber(stats.kurtosis, 3)}</span>
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ════════════════════ MONTHLY SEASONALITY ════════════════════ */}
      {seasonality.length > 0 && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4">
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">Estacionalidad Mensual</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={seasonality.map((s) => ({
                  ...s,
                  name: MONTH_NAMES[s.month - 1] || `M${s.month}`,
                }))}
                margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
              >
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#6b7280", fontSize: 10 }}
                  axisLine={{ stroke: "#1a2233" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#6b7280", fontSize: 10 }}
                  axisLine={{ stroke: "#1a2233" }}
                  tickLine={false}
                  tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                />
                <Tooltip
                  contentStyle={{ background: "#0d1117", border: "1px solid #1a2233", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#9ca3af" }}
                  formatter={(value: any, name: any) => {
                    if (name === "avg_return") return [`${formatNumber(Number(value), 2)}%`, "Retorno prom."];
                    return [value, name];
                  }}
                />
                <ReferenceLine y={0} stroke="#1a2233" />
                <Bar dataKey="avg_return" radius={[3, 3, 0, 0]}>
                  {seasonality.map((entry, idx) => (
                    <Cell key={idx} fill={entry.avg_return >= 0 ? "#22c55e" : "#ef4444"} fillOpacity={0.7} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {/* Win rate labels */}
          <div className="flex justify-between mt-2 px-2">
            {seasonality.map((s) => (
              <div key={s.month} className="text-center flex-1">
                <p className="text-[9px] text-gray-600 num">{s.win_rate != null ? `${formatNumber(s.win_rate, 0)}%` : ""}</p>
              </div>
            ))}
          </div>
          <p className="text-[9px] text-gray-700 text-center mt-0.5 tracking-widest uppercase">Win rate por mes</p>
        </div>
      )}

      {/* ════════════════════ SUPPORT & RESISTANCE ════════════════════ */}
      {(supports.length > 0 || resistances.length > 0) && (
        <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-4">
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">Soportes y Resistencias</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Supports */}
            <div>
              <p className="text-[10px] tracking-widest text-green-500/70 uppercase mb-2">Soportes</p>
              <div className="space-y-1.5">
                {supports.slice(0, 5).map((s, idx) => (
                  <div key={idx} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-green-500/5 border border-green-500/10">
                    <span className="text-sm font-semibold text-green-400 num">{formatMonto(s.price)}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] text-gray-500">
                        Fuerza: <span className="num text-gray-400">{s.strength}</span>
                      </span>
                      <span className="text-[10px] num text-green-500">{formatPct(s.distance_pct)}</span>
                    </div>
                  </div>
                ))}
                {supports.length === 0 && <p className="text-xs text-gray-700">Sin datos</p>}
              </div>
            </div>
            {/* Resistances */}
            <div>
              <p className="text-[10px] tracking-widest text-red-500/70 uppercase mb-2">Resistencias</p>
              <div className="space-y-1.5">
                {resistances.slice(0, 5).map((r, idx) => (
                  <div key={idx} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-red-500/5 border border-red-500/10">
                    <span className="text-sm font-semibold text-red-400 num">{formatMonto(r.price)}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] text-gray-500">
                        Fuerza: <span className="num text-gray-400">{r.strength}</span>
                      </span>
                      <span className="text-[10px] num text-red-500">{formatPct(r.distance_pct)}</span>
                    </div>
                  </div>
                ))}
                {resistances.length === 0 && <p className="text-xs text-gray-700">Sin datos</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────
   Candlestick Chart (lightweight-charts)
   ────────────────────────────────────────────── */

function CandlestickChart({ priceHistory }: { priceHistory: any[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || priceHistory.length === 0) return;

    let disposed = false;

    async function init() {
      const lc = await import("lightweight-charts") as any;
      const createChart = lc.createChart;
      if (disposed || !containerRef.current) return;

      const chart = createChart(containerRef.current, {
        height: 400,
        layout: {
          background: { color: "#0d1117" },
          textColor: "#8b949e",
        },
        grid: {
          vertLines: { color: "#1a2233" },
          horzLines: { color: "#1a2233" },
        },
        crosshair: {
          mode: 0,
        },
        rightPriceScale: {
          borderColor: "#1a2233",
        },
        timeScale: {
          borderColor: "#1a2233",
          timeVisible: false,
        },
      });

      chartRef.current = chart;

      /* Candlestick series (v5 API) */
      const CandlestickSeries = lc.CandlestickSeries || lc.CandlestickSeriesType;
      const candleSeries = CandlestickSeries
        ? chart.addSeries(CandlestickSeries, {
            upColor: "#22c55e", downColor: "#ef4444",
            borderUpColor: "#22c55e", borderDownColor: "#ef4444",
            wickUpColor: "#22c55e", wickDownColor: "#ef4444",
          })
        : chart.addCandlestickSeries({
            upColor: "#22c55e", downColor: "#ef4444",
            borderUpColor: "#22c55e", borderDownColor: "#ef4444",
            wickUpColor: "#22c55e", wickDownColor: "#ef4444",
          });

      const candleData = priceHistory.map((d: any) => ({
        time: d.date || d.time,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));
      candleSeries.setData(candleData);

      /* Volume histogram (v5 API) */
      const HistogramSeries = lc.HistogramSeries || lc.HistogramSeriesType;
      const volumeSeries = HistogramSeries
        ? chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume" })
        : chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "volume" });

      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.7, bottom: 0 },
      });

      const volumeData = priceHistory.map((d: any) => ({
        time: d.date || d.time,
        value: d.volume || 0,
        color: d.close >= d.open ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)",
      }));
      volumeSeries.setData(volumeData);

      /* SMA 20 */
      const sma20 = computeSMA(priceHistory, 20);
      const LineSeries = lc.LineSeries || lc.LineSeriesType;
      const addLine = (opts: any) => LineSeries ? chart.addSeries(LineSeries, opts) : chart.addLineSeries(opts);
      const sma20Series = addLine({
        color: "#06b6d4",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      const sma20Data = priceHistory
        .map((d: any, i: number) => ({
          time: d.date || d.time,
          value: sma20[i],
        }))
        .filter((d: any) => d.value !== null);
      sma20Series.setData(sma20Data);

      /* SMA 50 */
      const sma50 = computeSMA(priceHistory, 50);
      const sma50Series = addLine({
        color: "#f97316",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      const sma50Data = priceHistory
        .map((d: any, i: number) => ({
          time: d.date || d.time,
          value: sma50[i],
        }))
        .filter((d: any) => d.value !== null);
      sma50Series.setData(sma50Data);

      /* Visible range: last 90 days */
      if (candleData.length > 90) {
        const from = candleData[candleData.length - 90].time;
        const to = candleData[candleData.length - 1].time;
        chart.timeScale().setVisibleRange({ from, to });
      }

      /* Responsive */
      const handleResize = () => {
        if (containerRef.current && !disposed) {
          chart.applyOptions({ width: containerRef.current.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);
      handleResize();

      /* Store cleanup */
      (chartRef as any)._cleanup = () => {
        window.removeEventListener("resize", handleResize);
      };
    }

    init();

    return () => {
      disposed = true;
      if ((chartRef as any)._cleanup) (chartRef as any)._cleanup();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [priceHistory]);

  if (priceHistory.length === 0) {
    return <p className="text-gray-700 text-sm text-center py-12">Sin datos de precios disponibles.</p>;
  }

  return (
    <div>
      <div ref={containerRef} style={{ height: 400 }} />
      <div className="flex gap-4 mt-2 justify-end">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-cyan-500 rounded" />
          <span className="text-[10px] text-gray-600">SMA 20</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-orange-500 rounded" />
          <span className="text-[10px] text-gray-600">SMA 50</span>
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────
   Score History Chart (recharts)
   ────────────────────────────────────────────── */

function ScoreHistoryChart({ data }: { data: any[] }) {
  /* Split data into green (>=65) and red (<=35) zones */
  const chartData = data.map((d: any) => ({
    date: d.date,
    score: d.score,
    greenZone: d.score >= 65 ? d.score : null,
    redZone: d.score <= 35 ? d.score : null,
  }));

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="scoreGreenGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="scoreRedGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.02} />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0.3} />
            </linearGradient>
            <linearGradient id="scoreMainGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fill: "#6b7280", fontSize: 10 }}
            axisLine={{ stroke: "#1a2233" }}
            tickLine={false}
            tickFormatter={(v: string) => {
              if (!v) return "";
              const parts = v.split("-");
              return parts.length >= 2 ? `${parts[2]}/${parts[1]}` : v;
            }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: "#6b7280", fontSize: 10 }}
            axisLine={{ stroke: "#1a2233" }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{ background: "#0d1117", border: "1px solid #1a2233", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#9ca3af" }}
            formatter={(value: any) => [Number(value)?.toFixed(1), "Score"]}
          />
          <ReferenceLine y={65} stroke="#22c55e" strokeDasharray="6 4" strokeOpacity={0.5} />
          <ReferenceLine y={35} stroke="#ef4444" strokeDasharray="6 4" strokeOpacity={0.5} />
          <Area
            type="monotone"
            dataKey="score"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#scoreMainGrad)"
            dot={false}
            activeDot={{ r: 3, fill: "#3b82f6", stroke: "#0d1117", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
