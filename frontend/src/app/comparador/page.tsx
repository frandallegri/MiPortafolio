"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { cn, formatMonto, formatPct, formatNumber, scoreColor } from "@/lib/utils";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";

/* ──────────────────────────────────────────────
   Constantes
   ────────────────────────────────────────────── */

const LINE_COLORS = ["#3b82f6", "#f97316", "#22c55e"]; // azul, naranja, verde
const METRIC_LABELS: Record<string, string> = {
  retorno: "Retorno",
  volatilidad: "Volatilidad",
  sharpe: "Sharpe",
  drawdown: "Drawdown",
  win_rate: "Win Rate",
  beta: "Beta",
};

/* ──────────────────────────────────────────────
   Tipos
   ────────────────────────────────────────────── */

interface TickerData {
  ticker: string;
  history: any;
  score: any;
  error?: string;
}

/* ──────────────────────────────────────────────
   Main Page
   ────────────────────────────────────────────── */

export default function ComparadorPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <MacroBar />
          <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden bg-[#0b0e14]">
            <ComparadorContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function ComparadorContent() {
  const [inputs, setInputs] = useState(["", "", ""]);
  const [results, setResults] = useState<TickerData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateInput(idx: number, val: string) {
    const next = [...inputs];
    next[idx] = val.toUpperCase();
    setInputs(next);
  }

  async function handleComparar() {
    const tickers = inputs.map((t) => t.trim()).filter(Boolean);
    if (tickers.length === 0) return;

    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const promises = tickers.map(async (ticker) => {
        try {
          const [history, score] = await Promise.all([
            api.getTickerHistory(ticker),
            api.getScore(ticker),
          ]);
          return { ticker, history, score } as TickerData;
        } catch (e: any) {
          return { ticker, history: null, score: null, error: e.message } as TickerData;
        }
      });

      const data = await Promise.all(promises);
      setResults(data);
    } catch (e: any) {
      setError(e.message || "Error cargando datos");
    } finally {
      setLoading(false);
    }
  }

  // Construir datos normalizados para el gráfico
  const chartData = buildChartData(results);

  // Extraer métricas para tabla comparativa
  const metrics = buildMetrics(results);

  // Solo tickers válidos (sin error)
  const validResults = results.filter((r) => !r.error && r.score);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-1">Análisis comparativo</p>
        <h2 className="text-2xl font-semibold text-white tracking-tight">Comparador de Tickers</h2>
      </div>

      {/* Inputs */}
      <div className="bg-[#0d1117] border border-[#1a2233] rounded-xl p-5">
        <div className="flex items-end gap-3 flex-wrap">
          {inputs.map((val, idx) => (
            <div key={idx}>
              <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">
                Ticker {idx + 1}
              </label>
              <input
                type="text"
                value={val}
                onChange={(e) => updateInput(idx, e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleComparar()}
                placeholder={idx === 0 ? "Ej: GGAL" : idx === 1 ? "Ej: YPF" : "Ej: PAMP"}
                className="bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-sm text-white uppercase placeholder-gray-700 focus:outline-none focus:border-blue-600/40 w-32"
              />
            </div>
          ))}
          <button
            onClick={handleComparar}
            disabled={loading || inputs.every((t) => !t.trim())}
            className="flex items-center gap-2 px-5 py-2 bg-blue-600/20 hover:bg-blue-600/30 disabled:opacity-40 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all"
          >
            {loading ? (
              <>
                <div className="w-3.5 h-3.5 border border-blue-400/40 border-t-blue-400 rounded-full animate-spin" />
                Cargando
              </>
            ) : (
              "Comparar"
            )}
          </button>
        </div>
      </div>

      {/* Error global */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Errores individuales */}
      {results.some((r) => r.error) && (
        <div className="space-y-2">
          {results
            .filter((r) => r.error)
            .map((r) => (
              <div key={r.ticker} className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
                <p className="text-red-400 text-sm">
                  <span className="font-bold">{r.ticker}:</span> {r.error}
                </p>
              </div>
            ))}
        </div>
      )}

      {/* Resultados */}
      {validResults.length > 0 && (
        <>
          {/* Score cards */}
          <div>
            <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">Scores</p>
            <div className="grid grid-cols-3 gap-4">
              {validResults.map((r, idx) => (
                <div
                  key={r.ticker}
                  className="bg-[#0d1117] border border-[#1a2233] rounded-xl p-5 text-center"
                >
                  <p className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: LINE_COLORS[idx] }}>
                    {r.ticker}
                  </p>
                  {/* Círculo de score */}
                  <div className="relative w-20 h-20 mx-auto">
                    <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                      <circle
                        cx="40"
                        cy="40"
                        r="34"
                        fill="none"
                        stroke="#1a2233"
                        strokeWidth="6"
                      />
                      <circle
                        cx="40"
                        cy="40"
                        r="34"
                        fill="none"
                        stroke={LINE_COLORS[idx]}
                        strokeWidth="6"
                        strokeLinecap="round"
                        strokeDasharray={`${(r.score.score / 100) * 213.6} 213.6`}
                        className="transition-all duration-700"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className={cn("text-xl font-bold num", scoreColor(r.score.score))}>
                        {r.score.score?.toFixed(0)}
                      </span>
                    </div>
                  </div>
                  <p className="text-[10px] text-gray-600 uppercase tracking-widest mt-2">
                    {r.score.signal === "compra" ? "Compra" : r.score.signal === "venta" ? "Venta" : "Neutral"}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Tabla comparativa */}
          {metrics.length > 0 && (
            <div>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">Estadísticas</p>
              <div className="bg-[#0d1117] border border-[#1a2233] rounded-xl overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#1a2233]">
                      <th className="text-left text-[10px] tracking-widest text-gray-600 uppercase px-4 py-3">
                        Métrica
                      </th>
                      {validResults.map((r, idx) => (
                        <th
                          key={r.ticker}
                          className="text-right text-[10px] tracking-widest uppercase px-4 py-3 font-bold"
                          style={{ color: LINE_COLORS[idx] }}
                        >
                          {r.ticker}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.map((metric) => (
                      <tr key={metric.key} className="border-b border-[#1a2233]/50">
                        <td className="px-4 py-3 text-sm text-gray-400">{metric.label}</td>
                        {validResults.map((r) => {
                          const val = metric.getValue(r);
                          return (
                            <td key={r.ticker} className="px-4 py-3 text-right text-sm text-gray-300 num">
                              {val}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Gráfico de precios normalizados */}
          {chartData.length > 0 && (
            <div>
              <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-3">
                Rendimiento normalizado (base 100)
              </p>
              <div className="bg-[#0d1117] border border-[#1a2233] rounded-xl p-4">
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={chartData}>
                    <XAxis
                      dataKey="date"
                      tick={{ fill: "#4b5563", fontSize: 10 }}
                      axisLine={{ stroke: "#1a2233" }}
                      tickLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fill: "#4b5563", fontSize: 10 }}
                      axisLine={{ stroke: "#1a2233" }}
                      tickLine={false}
                      domain={["auto", "auto"]}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0d1117",
                        border: "1px solid #1a2233",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                      labelStyle={{ color: "#9ca3af" }}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: "12px", color: "#9ca3af" }}
                    />
                    {validResults.map((r, idx) => (
                      <Line
                        key={r.ticker}
                        type="monotone"
                        dataKey={r.ticker}
                        stroke={LINE_COLORS[idx]}
                        strokeWidth={2}
                        dot={false}
                        name={r.ticker}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────
   Helpers para datos
   ────────────────────────────────────────────── */

function buildChartData(results: TickerData[]): any[] {
  const valid = results.filter((r) => !r.error && r.history);
  if (valid.length === 0) return [];

  // Cada history puede tener .prices o ser un array directamente
  const seriesMap: Record<string, { date: string; close: number }[]> = {};
  for (const r of valid) {
    const prices = r.history?.prices || r.history?.data || r.history;
    if (!Array.isArray(prices)) continue;
    seriesMap[r.ticker] = prices.map((p: any) => ({
      date: p.date || p.fecha,
      close: p.close ?? p.precio ?? p.price,
    }));
  }

  // Recopilar todas las fechas únicas y ordenar
  const allDates = new Set<string>();
  for (const s of Object.values(seriesMap)) {
    for (const p of s) {
      if (p.date) allDates.add(p.date);
    }
  }
  const sortedDates = Array.from(allDates).sort();

  // Para cada ticker, crear mapa fecha -> close
  const tickerMaps: Record<string, Record<string, number>> = {};
  const firstPrice: Record<string, number | null> = {};

  for (const [ticker, series] of Object.entries(seriesMap)) {
    const map: Record<string, number> = {};
    for (const p of series) {
      if (p.date && p.close != null) map[p.date] = p.close;
    }
    tickerMaps[ticker] = map;

    // Encontrar primer precio válido
    for (const d of sortedDates) {
      if (map[d] != null) {
        firstPrice[ticker] = map[d];
        break;
      }
    }
  }

  // Construir datos normalizados (base 100)
  return sortedDates.map((date) => {
    const row: any = { date };
    for (const [ticker, map] of Object.entries(tickerMaps)) {
      const base = firstPrice[ticker];
      const val = map[date];
      if (base != null && val != null) {
        row[ticker] = Number(((val / base) * 100).toFixed(2));
      }
    }
    return row;
  });
}

interface MetricDef {
  key: string;
  label: string;
  getValue: (r: TickerData) => string;
}

function buildMetrics(results: TickerData[]): MetricDef[] {
  const valid = results.filter((r) => !r.error && r.score);
  if (valid.length === 0) return [];

  // Buscar stats en score o history
  const hasStats = valid.some(
    (r) => r.history?.stats || r.score?.stats || r.history?.return_pct != null
  );

  const metrics: MetricDef[] = [
    {
      key: "retorno",
      label: "Retorno",
      getValue: (r) => {
        const stats = r.history?.stats || r.score?.stats;
        const val = stats?.return_pct ?? stats?.retorno ?? r.history?.return_pct;
        return val != null ? formatPct(val) : "—";
      },
    },
    {
      key: "volatilidad",
      label: "Volatilidad",
      getValue: (r) => {
        const stats = r.history?.stats || r.score?.stats;
        const val = stats?.volatility ?? stats?.volatilidad;
        return val != null ? formatPct(val) : "—";
      },
    },
    {
      key: "sharpe",
      label: "Sharpe",
      getValue: (r) => {
        const stats = r.history?.stats || r.score?.stats;
        const val = stats?.sharpe ?? stats?.sharpe_ratio;
        return val != null ? formatNumber(val) : "—";
      },
    },
    {
      key: "drawdown",
      label: "Drawdown",
      getValue: (r) => {
        const stats = r.history?.stats || r.score?.stats;
        const val = stats?.max_drawdown ?? stats?.drawdown;
        return val != null ? formatPct(val) : "—";
      },
    },
    {
      key: "win_rate",
      label: "Win Rate",
      getValue: (r) => {
        const stats = r.history?.stats || r.score?.stats;
        const val = stats?.win_rate;
        return val != null ? formatPct(val) : "—";
      },
    },
    {
      key: "beta",
      label: "Beta",
      getValue: (r) => {
        const stats = r.history?.stats || r.score?.stats;
        const val = stats?.beta;
        return val != null ? formatNumber(val) : "—";
      },
    },
  ];

  return metrics;
}
