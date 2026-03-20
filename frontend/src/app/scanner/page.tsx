"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { formatMonto, formatPct, scoreColor, scoreBgColor, signalBadge, cn } from "@/lib/utils";

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score));
  const color = pct >= 70 ? "bg-green-500" : pct >= 60 ? "bg-yellow-500" : pct >= 40 ? "bg-gray-600" : "bg-red-500";
  const textColor = pct >= 70 ? "text-green-400" : pct >= 60 ? "text-yellow-400" : pct >= 40 ? "text-gray-500" : "text-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs num font-semibold w-8 text-right tabular-nums ${textColor}`}>{pct.toFixed(0)}</span>
    </div>
  );
}

export default function ScannerPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <MacroBar />
          <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden">
            <ScannerContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function ScannerContent() {
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(0);
  const [assetType, setAssetType] = useState("");
  const [total, setTotal] = useState(0);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [tickerDetail, setTickerDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function loadScanner() {
    setLoading(true);
    try {
      const data = await api.getScanner(minScore, assetType || undefined);
      setResults(data.results || []);
      setTotal(data.total_assets || 0);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadScanner();
  }, []);

  async function loadDetail(ticker: string) {
    setSelectedTicker(ticker);
    setDetailLoading(true);
    try {
      const data = await api.getScore(ticker);
      setTickerDetail(data);
    } catch {
      setTickerDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-1">Análisis cuantitativo</p>
          <h2 className="text-2xl font-semibold text-white tracking-tight">Scanner de Mercado</h2>
        </div>
        <button
          onClick={loadScanner}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 disabled:opacity-40 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all"
        >
          <svg className={cn("w-3.5 h-3.5", loading && "animate-spin")} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {loading ? "Escaneando" : "Actualizar"}
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-end flex-wrap">
        <div>
          <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">Score mínimo</label>
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="bg-[#0d1117] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40"
          >
            <option value={0}>Todos</option>
            <option value={50}>50+</option>
            <option value={60}>60+</option>
            <option value={65}>65+ (umbral compra)</option>
            <option value={70}>70+</option>
            <option value={80}>80+</option>
          </select>
        </div>
        <div>
          <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">Tipo</label>
          <select
            value={assetType}
            onChange={(e) => setAssetType(e.target.value)}
            className="bg-[#0d1117] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40"
          >
            <option value="">Todos</option>
            <option value="accion">Acciones</option>
            <option value="cedear">CEDEARs</option>
            <option value="bono_soberano">Bonos</option>
            <option value="letra">Letras</option>
            <option value="obligacion_negociable">ONs</option>
          </select>
        </div>
        <button
          onClick={loadScanner}
          className="px-4 py-2 bg-[#0d1117] hover:bg-[#1a2233] text-gray-400 text-xs tracking-widest uppercase rounded-lg border border-[#1a2233] transition-all"
        >
          Filtrar
        </button>
        {total > 0 && (
          <span className="text-[10px] text-gray-600 self-center tracking-widest uppercase ml-auto">
            {total} activos · {results.length} resultados
          </span>
        )}
      </div>

      <div className="flex gap-4">
        {/* Scanner Table */}
        <div className={cn("bg-[#0d1117] rounded-xl border border-[#1a2233] flex-1")} style={{minWidth: 0, maxWidth: '100%', overflow: 'hidden'}}>
          {loading ? (
            <div className="p-12 text-center space-y-3">
              <div className="w-6 h-6 border border-blue-600/40 border-t-blue-400 rounded-full animate-spin mx-auto" />
              <p className="text-[10px] text-gray-600 tracking-widest uppercase">Analizando mercado...</p>
            </div>
          ) : results.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-gray-600 text-sm">Sin resultados para este filtro.</p>
              <p className="text-gray-700 text-xs mt-1">El sync histórico puede estar en progreso.</p>
            </div>
          ) : (
            <div style={{overflowX: 'hidden', width: '100%'}}>
              <table style={{ tableLayout: "fixed", width: "100%", maxWidth: "100%" }} className="text-sm">
                <colgroup>
                  <col style={{ width: "4%" }} />
                  <col style={{ width: "10%" }} />
                  <col style={{ width: "13%" }} />
                  <col style={{ width: "16%" }} />
                  <col style={{ width: "9%" }} />
                  <col style={{ width: "22%" }} />
                  <col style={{ width: "14%" }} />
                  <col style={{ width: "12%" }} />
                </colgroup>
                <thead>
                  <tr className="text-[10px] text-gray-600 border-b border-[#1a2233] tracking-widest uppercase">
                    <th className="text-left px-3 py-3 font-medium">#</th>
                    <th className="text-left px-3 py-3 font-medium">Ticker</th>
                    <th className="text-left px-3 py-3 font-medium hidden sm:table-cell">Tipo</th>
                    <th className="text-right px-3 py-3 font-medium hidden md:table-cell">Precio</th>
                    <th className="text-right px-3 py-3 font-medium hidden md:table-cell">Var</th>
                    <th className="px-3 py-3 font-medium">Score</th>
                    <th className="text-center px-3 py-3 font-medium">Señal</th>
                    <th className="text-right px-3 py-3 font-medium hidden lg:table-cell">⬆ ⬇</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((item, idx) => {
                    const badge = signalBadge(item.signal);
                    const isSelected = selectedTicker === item.ticker;
                    const isBuy = item.score >= 65;
                    return (
                      <tr
                        key={item.ticker}
                        onClick={() => loadDetail(item.ticker)}
                        className={cn(
                          "border-b border-[#1a2233]/60 cursor-pointer transition-all",
                          isSelected
                            ? "bg-blue-500/8 border-l-2 border-l-blue-500"
                            : isBuy
                            ? "row-buy"
                            : "hover:bg-gray-900/20"
                        )}
                      >
                        <td className="px-3 py-2.5 text-gray-700 num text-xs">{idx + 1}</td>
                        <td className="px-3 py-2.5 font-semibold text-white tracking-wide truncate">{item.ticker}</td>
                        <td className="px-3 py-2.5 text-gray-600 text-[10px] tracking-widest uppercase hidden sm:table-cell truncate">{item.asset_type}</td>
                        <td className="px-3 py-2.5 text-right text-gray-300 num text-xs hidden md:table-cell">
                          {item.price ? formatMonto(item.price) : "—"}
                        </td>
                        <td className={cn("px-3 py-2.5 text-right num text-xs font-medium hidden md:table-cell", item.change_pct >= 0 ? "text-green-400" : "text-red-400")}>
                          {item.change_pct != null ? formatPct(item.change_pct) : "—"}
                        </td>
                        <td className="px-3 py-2.5 w-36">
                          <ScoreBar score={item.score} />
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={cn("px-2 py-0.5 rounded text-[10px] font-semibold tracking-widest border", badge.color)}>
                            {badge.text}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right hidden lg:table-cell">
                          <span className="text-green-500 num text-xs">{item.bullish}</span>
                          <span className="text-gray-700 mx-1">/</span>
                          <span className="text-red-500 num text-xs">{item.bearish}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {selectedTicker && (
          <div className="w-72 shrink-0 bg-[#0d1117] rounded-xl border border-[#1a2233] overflow-hidden max-h-[80vh] overflow-y-auto">
            {/* Panel header */}
            <div className="px-4 py-3 border-b border-[#1a2233] flex items-center justify-between sticky top-0 bg-[#0d1117] z-10">
              <div>
                <p className="text-[10px] tracking-widest text-gray-600 uppercase">Análisis detallado</p>
                <h3 className="text-base font-bold text-white mt-0.5">{selectedTicker}</h3>
              </div>
              <button
                onClick={() => setSelectedTicker(null)}
                className="text-gray-700 hover:text-gray-400 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {detailLoading ? (
              <div className="p-8 flex justify-center">
                <div className="w-6 h-6 border border-blue-600/40 border-t-blue-400 rounded-full animate-spin" />
              </div>
            ) : tickerDetail ? (
              <div className="p-4 space-y-4">
                {/* Score hero */}
                <div className={cn("rounded-xl border p-5 text-center relative overflow-hidden", scoreBgColor(tickerDetail.score))}>
                  <div className="relative z-10">
                    <p className={cn("text-4xl font-bold num", scoreColor(tickerDetail.score),
                      tickerDetail.score >= 70 ? "score-glow-green" : tickerDetail.score >= 60 ? "score-glow-yellow" : "score-glow-red"
                    )}>
                      {tickerDetail.score.toFixed(1)}
                    </p>
                    <p className="text-[10px] text-gray-600 uppercase tracking-widest mt-1">Prob. de suba</p>
                    <div className="mt-3">
                      {(() => {
                        const badge = signalBadge(tickerDetail.signal);
                        return (
                          <span className={cn("px-3 py-1 rounded text-[10px] font-semibold tracking-widest border uppercase", badge.color)}>
                            {badge.text}
                          </span>
                        );
                      })()}
                    </div>
                  </div>
                </div>

                {/* Bullish/Neutral/Bearish counters */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-green-500/5 border border-green-500/10 rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-green-400 num">{tickerDetail.bullish_count}</p>
                    <p className="text-[9px] text-gray-600 uppercase tracking-widest">Alcistas</p>
                  </div>
                  <div className="bg-gray-500/5 border border-gray-700/20 rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-gray-500 num">{tickerDetail.neutral_count}</p>
                    <p className="text-[9px] text-gray-600 uppercase tracking-widest">Neutral</p>
                  </div>
                  <div className="bg-red-500/5 border border-red-500/10 rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-red-400 num">{tickerDetail.bearish_count}</p>
                    <p className="text-[9px] text-gray-600 uppercase tracking-widest">Bajistas</p>
                  </div>
                </div>

                {/* Signal breakdown with bars */}
                <div>
                  <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-2">Indicadores</p>
                  <div className="space-y-1.5">
                    {tickerDetail.signals?.map((sig: any) => (
                      <div key={sig.name} className="space-y-1">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <div className={cn(
                              "w-1.5 h-1.5 rounded-full",
                              sig.signal > 0 ? "bg-green-400" : sig.signal < 0 ? "bg-red-400" : "bg-gray-600"
                            )} />
                            <span className="text-xs text-gray-400">{sig.name}</span>
                          </div>
                          <span className={cn(
                            "text-[10px] font-semibold",
                            sig.signal > 0 ? "text-green-400" : sig.signal < 0 ? "text-red-400" : "text-gray-600"
                          )}>
                            {sig.signal > 0 ? "▲" : sig.signal < 0 ? "▼" : "—"}
                          </span>
                        </div>
                        {/* Weight bar */}
                        <div className="h-0.5 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all",
                              sig.signal > 0 ? "bg-green-500/60" : sig.signal < 0 ? "bg-red-500/60" : "bg-gray-700"
                            )}
                            style={{ width: `${Math.min(100, (sig.weight / 1.5) * 100)}%` }}
                          />
                        </div>
                        <p className="text-[10px] text-gray-600 pl-3">{sig.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-gray-600 text-center p-8 text-sm">Error cargando datos</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
