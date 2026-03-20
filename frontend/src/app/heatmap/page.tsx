"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { cn, formatMonto } from "@/lib/utils";

/* ──────────────────────────────────────────────
   Helpers
   ────────────────────────────────────────────── */

/** Interpola de rojo (0) a amarillo (50) a verde (100) */
function heatColor(score: number): string {
  const s = Math.min(100, Math.max(0, score));
  let r: number, g: number, b: number;
  if (s <= 50) {
    // rojo -> amarillo
    const t = s / 50;
    r = 220;
    g = Math.round(50 + 170 * t);
    b = 50;
  } else {
    // amarillo -> verde
    const t = (s - 50) / 50;
    r = Math.round(220 - 180 * t);
    g = 220;
    b = Math.round(50 + 30 * t);
  }
  return `rgba(${r}, ${g}, ${b}, ${0.15 + 0.55 * (s / 100)})`;
}

function heatBorder(score: number): string {
  const s = Math.min(100, Math.max(0, score));
  let r: number, g: number, b: number;
  if (s <= 50) {
    const t = s / 50;
    r = 220;
    g = Math.round(50 + 170 * t);
    b = 50;
  } else {
    const t = (s - 50) / 50;
    r = Math.round(220 - 180 * t);
    g = 220;
    b = Math.round(50 + 30 * t);
  }
  return `rgba(${r}, ${g}, ${b}, 0.35)`;
}

function scoreTextColor(score: number): string {
  if (score >= 70) return "text-green-400";
  if (score >= 50) return "text-yellow-400";
  return "text-red-400";
}

/* ──────────────────────────────────────────────
   Main Page
   ────────────────────────────────────────────── */

export default function HeatmapPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <MacroBar />
          <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden bg-[#0b0e14]">
            <HeatmapContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function HeatmapContent() {
  const [items, setItems] = useState<any[]>([]);
  const [regime, setRegime] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getScanner(0);
      setItems(data.results || []);
      if (data.regime) setRegime(data.regime);
    } catch (e: any) {
      setError(e.message || "Error cargando datos");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] tracking-widest text-gray-600 uppercase mb-1">Visualización</p>
          <h2 className="text-2xl font-semibold text-white tracking-tight">Heatmap del Mercado</h2>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 disabled:opacity-40 text-blue-400 text-xs font-semibold tracking-widest uppercase rounded-lg border border-blue-600/30 transition-all"
        >
          <svg className={cn("w-3.5 h-3.5", loading && "animate-spin")} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {loading ? "Cargando" : "Actualizar"}
        </button>
      </div>

      {/* Régimen */}
      {regime && (
        <div className="bg-[#0d1117] border border-[#1a2233] rounded-xl px-5 py-3 flex items-center gap-4">
          <p className="text-[10px] tracking-widest text-gray-600 uppercase">Régimen actual</p>
          <span className={cn(
            "px-3 py-1 rounded-lg text-xs font-bold tracking-widest uppercase border",
            regime.label === "bull" || regime.regime === "bull"
              ? "bg-green-500/15 text-green-400 border-green-500/30"
              : regime.label === "bear" || regime.regime === "bear"
              ? "bg-red-500/15 text-red-400 border-red-500/30"
              : "bg-yellow-500/15 text-yellow-400 border-yellow-500/30"
          )}>
            {regime.label || regime.regime || "Desconocido"}
          </span>
          {regime.description && (
            <span className="text-xs text-gray-500">{regime.description}</span>
          )}
        </div>
      )}

      {/* Leyenda */}
      <div className="flex items-center gap-4">
        <p className="text-[10px] tracking-widest text-gray-600 uppercase">Score</p>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 rounded-sm" style={{ background: heatColor(0) }} />
          <span className="text-[10px] text-gray-600">0</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 rounded-sm" style={{ background: heatColor(25) }} />
          <span className="text-[10px] text-gray-600">25</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 rounded-sm" style={{ background: heatColor(50) }} />
          <span className="text-[10px] text-gray-600">50</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 rounded-sm" style={{ background: heatColor(75) }} />
          <span className="text-[10px] text-gray-600">75</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-3 rounded-sm" style={{ background: heatColor(100) }} />
          <span className="text-[10px] text-gray-600">100</span>
        </div>
        {items.length > 0 && (
          <span className="text-[10px] text-gray-600 tracking-widest uppercase ml-auto">
            {items.length} activos
          </span>
        )}
      </div>

      {/* Contenido */}
      {loading ? (
        <div className="p-12 text-center space-y-3">
          <div className="w-6 h-6 border border-blue-600/40 border-t-blue-400 rounded-full animate-spin mx-auto" />
          <p className="text-[10px] text-gray-600 tracking-widest uppercase">Cargando heatmap...</p>
        </div>
      ) : error ? (
        <div className="p-12 text-center">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      ) : items.length === 0 ? (
        <div className="p-12 text-center">
          <p className="text-gray-600 text-sm">Sin datos disponibles.</p>
        </div>
      ) : (
        <div
          className="grid gap-2"
          style={{
            gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
          }}
        >
          {items.map((item) => (
            <div
              key={item.ticker}
              onClick={() => router.push(`/ticker/${item.ticker}`)}
              className="rounded-lg p-3 cursor-pointer transition-all hover:scale-[1.03] hover:shadow-lg border"
              style={{
                background: heatColor(item.score),
                borderColor: heatBorder(item.score),
              }}
            >
              <p className="text-sm font-bold text-white truncate">{item.ticker}</p>
              <p className="text-[10px] text-gray-400 num mt-0.5">
                {item.price != null ? formatMonto(item.price) : "—"}
              </p>
              <p className={cn("text-lg font-bold num mt-1", scoreTextColor(item.score))}>
                {item.score != null ? item.score.toFixed(0) : "—"}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
