"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { formatMonto, formatPct, scoreColor, scoreBgColor, signalBadge, cn } from "@/lib/utils";

export default function ScannerPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <MacroBar />
          <main className="flex-1 p-6 overflow-auto">
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Scanner de Mercado</h2>
          <p className="text-sm text-gray-500 mt-1">
            {total} activos analizados — ordenados por probabilidad de suba
          </p>
        </div>
        <button
          onClick={loadScanner}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? "Escaneando..." : "Actualizar"}
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Score mínimo</label>
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
          >
            <option value={0}>Todos</option>
            <option value={50}>50+</option>
            <option value={60}>60+</option>
            <option value={65}>65+ (umbral)</option>
            <option value={70}>70+</option>
            <option value={80}>80+</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Tipo de activo</label>
          <select
            value={assetType}
            onChange={(e) => setAssetType(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
          >
            <option value="">Todos</option>
            <option value="accion">Acciones</option>
            <option value="cedear">CEDEARs</option>
            <option value="bono_soberano">Bonos</option>
            <option value="letra">Letras</option>
            <option value="obligacion_negociable">ONs</option>
          </select>
        </div>
        <div className="self-end">
          <button
            onClick={loadScanner}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-sm rounded-lg transition-colors"
          >
            Filtrar
          </button>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Scanner Table */}
        <div className={cn("bg-[#111827] rounded-xl border border-gray-800 flex-1", selectedTicker ? "w-2/3" : "w-full")}>
          {loading ? (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent mx-auto" />
              <p className="text-gray-500 mt-3">Analizando mercado...</p>
            </div>
          ) : results.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              Sin resultados. Verificá que haya datos cargados y ejecutá el sync.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500 border-b border-gray-800">
                    <th className="text-left p-3 font-medium">#</th>
                    <th className="text-left p-3 font-medium">Ticker</th>
                    <th className="text-left p-3 font-medium">Tipo</th>
                    <th className="text-right p-3 font-medium">Precio</th>
                    <th className="text-right p-3 font-medium">Var %</th>
                    <th className="text-right p-3 font-medium">Score</th>
                    <th className="text-center p-3 font-medium">Señal</th>
                    <th className="text-right p-3 font-medium">Confianza</th>
                    <th className="text-right p-3 font-medium">Alcistas</th>
                    <th className="text-right p-3 font-medium">Bajistas</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((item, idx) => {
                    const badge = signalBadge(item.signal);
                    const isSelected = selectedTicker === item.ticker;
                    return (
                      <tr
                        key={item.ticker}
                        onClick={() => loadDetail(item.ticker)}
                        className={cn(
                          "border-b border-gray-800/50 cursor-pointer transition-colors",
                          isSelected ? "bg-blue-500/10" : "hover:bg-gray-800/30"
                        )}
                      >
                        <td className="p-3 text-gray-600">{idx + 1}</td>
                        <td className="p-3 font-medium text-white">{item.ticker}</td>
                        <td className="p-3 text-gray-400 text-xs">{item.asset_type}</td>
                        <td className="p-3 text-right text-white">
                          {item.price ? formatMonto(item.price) : "—"}
                        </td>
                        <td className={cn("p-3 text-right font-medium", item.change_pct >= 0 ? "text-green-400" : "text-red-400")}>
                          {item.change_pct != null ? formatPct(item.change_pct) : "—"}
                        </td>
                        <td className="p-3 text-right">
                          <span className={cn("font-bold", scoreColor(item.score))}>
                            {item.score.toFixed(1)}
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <span className={cn("px-2 py-0.5 rounded text-xs font-medium border", badge.color)}>
                            {badge.text}
                          </span>
                        </td>
                        <td className="p-3 text-right text-gray-400">{item.confidence?.toFixed(0)}%</td>
                        <td className="p-3 text-right text-green-400">{item.bullish}</td>
                        <td className="p-3 text-right text-red-400">{item.bearish}</td>
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
          <div className="w-1/3 bg-[#111827] rounded-xl border border-gray-800 p-4 space-y-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">{selectedTicker}</h3>
              <button
                onClick={() => setSelectedTicker(null)}
                className="text-gray-500 hover:text-white"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {detailLoading ? (
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent mx-auto" />
            ) : tickerDetail ? (
              <>
                {/* Score Summary */}
                <div className={cn("rounded-lg border p-4 text-center", scoreBgColor(tickerDetail.score))}>
                  <p className="text-3xl font-bold text-white">{tickerDetail.score.toFixed(1)}</p>
                  <p className="text-sm text-gray-400">Probabilidad de suba</p>
                  <div className="mt-2">
                    {(() => {
                      const badge = signalBadge(tickerDetail.signal);
                      return (
                        <span className={cn("px-3 py-1 rounded text-sm font-medium border", badge.color)}>
                          {badge.text}
                        </span>
                      );
                    })()}
                  </div>
                </div>

                {/* Indicator Breakdown */}
                <div>
                  <h4 className="text-sm font-medium text-gray-400 mb-2">Desglose de señales</h4>
                  <div className="space-y-2">
                    {tickerDetail.signals?.map((sig: any) => (
                      <div
                        key={sig.name}
                        className="flex items-center justify-between p-2 bg-gray-900/50 rounded-lg"
                      >
                        <div className="flex items-center gap-2">
                          <div
                            className={cn(
                              "w-2 h-2 rounded-full",
                              sig.signal > 0 ? "bg-green-400" : sig.signal < 0 ? "bg-red-400" : "bg-gray-500"
                            )}
                          />
                          <span className="text-sm text-white">{sig.name}</span>
                        </div>
                        <span className="text-xs text-gray-500">{sig.description}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Counts */}
                <div className="flex gap-3 text-center">
                  <div className="flex-1 bg-green-500/10 rounded-lg p-2">
                    <p className="text-lg font-bold text-green-400">{tickerDetail.bullish_count}</p>
                    <p className="text-xs text-gray-500">Alcistas</p>
                  </div>
                  <div className="flex-1 bg-gray-500/10 rounded-lg p-2">
                    <p className="text-lg font-bold text-gray-400">{tickerDetail.neutral_count}</p>
                    <p className="text-xs text-gray-500">Neutral</p>
                  </div>
                  <div className="flex-1 bg-red-500/10 rounded-lg p-2">
                    <p className="text-lg font-bold text-red-400">{tickerDetail.bearish_count}</p>
                    <p className="text-xs text-gray-500">Bajistas</p>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-gray-500 text-center">Error cargando datos</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
