"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { cn, formatMonto, formatPct, formatNumber, scoreColor, signalBadge } from "@/lib/utils";

interface ScannerItem {
  ticker: string;
  asset_type: string;
  price: number;
  change_pct: number;
  score: number;
  signal: string;
  rsi?: number;
  relative_volume?: number;
  bullish?: number;
  bearish?: number;
}

interface Filters {
  scoreMin: number;
  scoreMax: number;
  rsiMin: string;
  rsiMax: string;
  volRelMin: string;
  tipo: string;
  senal: string;
  varMin: string;
}

const DEFAULT_FILTERS: Filters = {
  scoreMin: 0,
  scoreMax: 100,
  rsiMin: "",
  rsiMax: "",
  volRelMin: "",
  tipo: "todos",
  senal: "todas",
  varMin: "",
};

function matchesTipo(assetType: string, filtro: string): boolean {
  if (filtro === "todos") return true;
  const t = (assetType || "").toLowerCase();
  switch (filtro) {
    case "acciones":
      return t.includes("accion") || t === "accion" || t === "acciones" || t === "equity";
    case "cedears":
      return t.includes("cedear");
    case "bonos":
      return t.includes("bono") || t.includes("bond") || t.includes("letra") || t.includes("on");
    default:
      return true;
  }
}

function matchesSenal(signal: string, filtro: string): boolean {
  if (filtro === "todas") return true;
  switch (filtro) {
    case "compra":
      return signal === "compra";
    case "venta":
      return signal === "venta";
    case "neutral":
      return signal === "neutral";
    default:
      return true;
  }
}

export default function ScreenerPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <MacroBar />
          <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden">
            <ScreenerContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function ScreenerContent() {
  const router = useRouter();
  const [allData, setAllData] = useState<ScannerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [sortField, setSortField] = useState<string>("score");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const data = await api.getScanner(0);
      setAllData(data.results || []);
    } catch {
      setAllData([]);
    } finally {
      setLoading(false);
    }
  }

  function applyFilters() {
    setAppliedFilters({ ...filters });
  }

  function resetFilters() {
    setFilters(DEFAULT_FILTERS);
    setAppliedFilters(DEFAULT_FILTERS);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      applyFilters();
    }
  }

  function handleSort(field: string) {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  }

  const filteredData = useMemo(() => {
    const f = appliedFilters;
    let results = allData.filter((item) => {
      // Score
      if (item.score < f.scoreMin || item.score > f.scoreMax) return false;

      // RSI
      if (f.rsiMin !== "" && item.rsi != null && item.rsi < Number(f.rsiMin)) return false;
      if (f.rsiMax !== "" && item.rsi != null && item.rsi > Number(f.rsiMax)) return false;

      // Volumen relativo
      if (f.volRelMin !== "" && (item.relative_volume == null || item.relative_volume < Number(f.volRelMin))) return false;

      // Tipo
      if (!matchesTipo(item.asset_type, f.tipo)) return false;

      // Senal
      if (!matchesSenal(item.signal, f.senal)) return false;

      // Variacion minima
      if (f.varMin !== "" && (item.change_pct == null || Math.abs(item.change_pct) < Number(f.varMin))) return false;

      return true;
    });

    // Sort
    results.sort((a, b) => {
      let va: any = (a as any)[sortField];
      let vb: any = (b as any)[sortField];
      if (va == null) va = -Infinity;
      if (vb == null) vb = -Infinity;
      if (typeof va === "string") {
        return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      }
      return sortAsc ? va - vb : vb - va;
    });

    return results;
  }, [allData, appliedFilters, sortField, sortAsc]);

  const SortIcon = ({ field }: { field: string }) => {
    if (sortField !== field) return <span className="text-gray-700 ml-0.5">&#8597;</span>;
    return <span className="text-blue-400 ml-0.5">{sortAsc ? "&#9650;" : "&#9660;"}</span>;
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-1">Filtros avanzados</p>
          <h2 className="text-2xl font-semibold text-white tracking-tight">Screener Personalizable</h2>
          <p className="text-xs text-gray-500 mt-1">
            Filtra activos por score, RSI, volumen, tipo y senal. Encontra oportunidades a tu medida.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 disabled:opacity-40 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all"
        >
          <svg className={cn("w-3.5 h-3.5", loading && "animate-spin")} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {loading ? "Cargando" : "Recargar datos"}
        </button>
      </div>

      {/* Filters */}
      <div className="bg-[#0d1117] rounded-xl border border-[#1a2233] p-5">
        <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-4">Criterios de busqueda</p>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3" onKeyDown={handleKeyDown}>
          {/* Score min */}
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">Score min</label>
            <input
              type="number"
              min={0}
              max={100}
              value={filters.scoreMin}
              onChange={(e) => setFilters({ ...filters, scoreMin: Number(e.target.value) })}
              className="w-full bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40 num"
              placeholder="0"
            />
          </div>

          {/* Score max */}
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">Score max</label>
            <input
              type="number"
              min={0}
              max={100}
              value={filters.scoreMax}
              onChange={(e) => setFilters({ ...filters, scoreMax: Number(e.target.value) })}
              className="w-full bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40 num"
              placeholder="100"
            />
          </div>

          {/* RSI min */}
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">RSI min</label>
            <input
              type="number"
              min={0}
              max={100}
              value={filters.rsiMin}
              onChange={(e) => setFilters({ ...filters, rsiMin: e.target.value })}
              className="w-full bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40 num"
              placeholder="0"
            />
          </div>

          {/* RSI max */}
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">RSI max</label>
            <input
              type="number"
              min={0}
              max={100}
              value={filters.rsiMax}
              onChange={(e) => setFilters({ ...filters, rsiMax: e.target.value })}
              className="w-full bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40 num"
              placeholder="100"
            />
          </div>

          {/* Vol. relativo min */}
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">Vol. rel. min</label>
            <input
              type="number"
              min={0}
              step={0.1}
              value={filters.volRelMin}
              onChange={(e) => setFilters({ ...filters, volRelMin: e.target.value })}
              className="w-full bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40 num"
              placeholder="1.5"
            />
          </div>

          {/* Tipo */}
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">Tipo</label>
            <select
              value={filters.tipo}
              onChange={(e) => setFilters({ ...filters, tipo: e.target.value })}
              className="w-full bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40"
            >
              <option value="todos">Todos</option>
              <option value="acciones">Acciones</option>
              <option value="cedears">CEDEARs</option>
              <option value="bonos">Bonos</option>
            </select>
          </div>

          {/* Senal */}
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">Senal</label>
            <select
              value={filters.senal}
              onChange={(e) => setFilters({ ...filters, senal: e.target.value })}
              className="w-full bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40"
            >
              <option value="todas">Todas</option>
              <option value="compra">Compra</option>
              <option value="venta">Venta</option>
              <option value="neutral">Neutral</option>
            </select>
          </div>

          {/* Variacion minima */}
          <div>
            <label className="text-[10px] tracking-widest text-gray-600 uppercase mb-1.5 block">Var. min %</label>
            <input
              type="number"
              min={0}
              step={0.5}
              value={filters.varMin}
              onChange={(e) => setFilters({ ...filters, varMin: e.target.value })}
              className="w-full bg-[#0b0e14] border border-[#1a2233] rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-600/40 num"
              placeholder="0"
            />
          </div>
        </div>

        {/* Filter actions */}
        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={applyFilters}
            className="px-5 py-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all"
          >
            Filtrar
          </button>
          <button
            onClick={resetFilters}
            className="px-4 py-2 bg-[#0b0e14] hover:bg-[#1a2233] text-gray-500 text-xs tracking-widest uppercase rounded-lg border border-[#1a2233] transition-all"
          >
            Limpiar
          </button>
          <span className="text-[10px] text-gray-600 tracking-widest uppercase ml-auto">
            {filteredData.length} de {allData.length} activos cumplen los filtros
          </span>
        </div>
      </div>

      {/* Results Table */}
      <div className="bg-[#0d1117] rounded-xl border border-[#1a2233]" style={{ overflow: "hidden" }}>
        {loading ? (
          <div className="p-12 text-center space-y-3">
            <div className="w-6 h-6 border border-blue-600/40 border-t-blue-400 rounded-full animate-spin mx-auto" />
            <p className="text-[10px] text-gray-600 tracking-widest uppercase">Cargando datos del mercado...</p>
          </div>
        ) : filteredData.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <svg className="w-10 h-10 mx-auto text-gray-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <p className="text-gray-500 text-sm">Ningun activo cumple los filtros seleccionados.</p>
            <p className="text-gray-600 text-xs">Proba ajustando los criterios de busqueda.</p>
          </div>
        ) : (
          <div style={{ width: "100%", overflowX: "auto" }}>
            {/* Table Header */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "80px 100px 130px 80px minmax(60px,1fr) 100px 80px 80px",
                minWidth: "720px",
              }}
              className="text-[10px] text-gray-600 border-b border-[#1a2233] tracking-widest uppercase"
            >
              <div className="px-3 py-3 cursor-pointer hover:text-gray-400 select-none" onClick={() => handleSort("ticker")}>
                Ticker <SortIcon field="ticker" />
              </div>
              <div className="px-3 py-3 cursor-pointer hover:text-gray-400 select-none" onClick={() => handleSort("asset_type")}>
                Tipo <SortIcon field="asset_type" />
              </div>
              <div className="px-3 py-3 text-right cursor-pointer hover:text-gray-400 select-none" onClick={() => handleSort("price")}>
                Precio <SortIcon field="price" />
              </div>
              <div className="px-3 py-3 text-right cursor-pointer hover:text-gray-400 select-none" onClick={() => handleSort("change_pct")}>
                Var% <SortIcon field="change_pct" />
              </div>
              <div className="px-3 py-3 text-right cursor-pointer hover:text-gray-400 select-none" onClick={() => handleSort("score")}>
                Score <SortIcon field="score" />
              </div>
              <div className="px-3 py-3 text-center cursor-pointer hover:text-gray-400 select-none" onClick={() => handleSort("signal")}>
                Senal <SortIcon field="signal" />
              </div>
              <div className="px-3 py-3 text-right cursor-pointer hover:text-gray-400 select-none" onClick={() => handleSort("rsi")}>
                RSI <SortIcon field="rsi" />
              </div>
              <div className="px-3 py-3 text-right cursor-pointer hover:text-gray-400 select-none" onClick={() => handleSort("relative_volume")}>
                Vol.Rel <SortIcon field="relative_volume" />
              </div>
            </div>

            {/* Table Rows */}
            {filteredData.map((item) => {
              const badge = signalBadge(item.signal);
              return (
                <div
                  key={item.ticker}
                  onClick={() => router.push(`/ticker/${item.ticker}`)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "80px 100px 130px 80px minmax(60px,1fr) 100px 80px 80px",
                    minWidth: "720px",
                    alignItems: "center",
                  }}
                  className="border-b border-[#1a2233]/60 cursor-pointer hover:bg-gray-900/30 transition-colors"
                >
                  <div className="px-3 py-2.5 font-semibold text-blue-400 hover:text-blue-300 tracking-wide text-sm truncate">
                    {item.ticker}
                  </div>
                  <div className="px-3 py-2.5 text-gray-600 text-[10px] tracking-widest uppercase truncate">
                    {item.asset_type}
                  </div>
                  <div className="px-3 py-2.5 text-right text-gray-300 num text-xs truncate">
                    {item.price ? formatMonto(item.price) : "\u2014"}
                  </div>
                  <div className={cn(
                    "px-3 py-2.5 text-right num text-xs font-medium",
                    item.change_pct >= 0 ? "text-green-400" : "text-red-400"
                  )}>
                    {item.change_pct != null ? formatPct(item.change_pct) : "\u2014"}
                  </div>
                  <div className="px-3 py-2.5 text-right">
                    <span className={cn("num text-sm font-bold", scoreColor(item.score))}>
                      {item.score.toFixed(0)}
                    </span>
                  </div>
                  <div className="px-3 py-2.5 text-center">
                    <span className={cn("px-2 py-0.5 rounded text-[10px] font-semibold tracking-widest border whitespace-nowrap", badge.color)}>
                      {badge.text}
                    </span>
                  </div>
                  <div className="px-3 py-2.5 text-right num text-xs text-gray-400">
                    {item.rsi != null ? formatNumber(item.rsi, 1) : "\u2014"}
                  </div>
                  <div className="px-3 py-2.5 text-right num text-xs text-gray-400">
                    {item.relative_volume != null ? formatNumber(item.relative_volume, 2) : "\u2014"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
