"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";
import MacroBar from "@/components/MacroBar";
import { api } from "@/lib/api";
import { formatMonto, formatPct, cn } from "@/lib/utils";

export default function PortfolioPage() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <MacroBar />
          <main className="flex-1 p-6 overflow-auto">
            <PortfolioContent />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}

function PortfolioContent() {
  const [positions, setPositions] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    ticker: "",
    quantity: "",
    entry_price: "",
    entry_date: "",
    commission: "0",
    notes: "",
  });

  async function load() {
    try {
      const [posData, summData] = await Promise.all([
        api.getPositions(true),
        api.getPortfolioSummary(),
      ]);
      setPositions(posData);
      setSummary(summData);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await api.createPosition({
      ticker: form.ticker.toUpperCase(),
      quantity: parseFloat(form.quantity),
      entry_price: parseFloat(form.entry_price),
      entry_date: form.entry_date,
      commission: parseFloat(form.commission || "0"),
      notes: form.notes || null,
    });
    setShowForm(false);
    setForm({ ticker: "", quantity: "", entry_price: "", entry_date: "", commission: "0", notes: "" });
    load();
  }

  async function handleDelete(id: number) {
    await api.deletePosition(id);
    load();
  }

  if (loading) {
    return <div className="animate-pulse h-96 bg-gray-800 rounded-xl" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Mi Portafolio</h2>
          <p className="text-sm text-gray-500 mt-1">Gestión de posiciones y rendimiento</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {showForm ? "Cancelar" : "+ Nueva posición"}
        </button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-4">
            <p className="text-xs text-gray-500">Invertido</p>
            <p className="text-xl font-bold text-white">{formatMonto(summary.total_invested)}</p>
          </div>
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-4">
            <p className="text-xs text-gray-500">Valor actual</p>
            <p className="text-xl font-bold text-white">{formatMonto(summary.total_current_value)}</p>
          </div>
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-4">
            <p className="text-xs text-gray-500">P&L Total</p>
            <p className={cn("text-xl font-bold", summary.total_pnl >= 0 ? "text-green-400" : "text-red-400")}>
              {formatMonto(summary.total_pnl)}
            </p>
            <p className={cn("text-sm", summary.total_pnl_pct >= 0 ? "text-green-400" : "text-red-400")}>
              {formatPct(summary.total_pnl_pct)}
            </p>
          </div>
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-4">
            <p className="text-xs text-gray-500">Posiciones</p>
            <p className="text-xl font-bold text-white">{summary.open_positions}</p>
          </div>
        </div>
      )}

      {/* Add Position Form */}
      {showForm && (
        <form onSubmit={handleCreate} className="bg-[#111827] rounded-xl border border-gray-800 p-4 grid grid-cols-2 md:grid-cols-6 gap-3">
          <input
            placeholder="Ticker"
            value={form.ticker}
            onChange={(e) => setForm({ ...form, ticker: e.target.value })}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            required
          />
          <input
            placeholder="Cantidad"
            type="number"
            step="any"
            value={form.quantity}
            onChange={(e) => setForm({ ...form, quantity: e.target.value })}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            required
          />
          <input
            placeholder="Precio entrada"
            type="number"
            step="any"
            value={form.entry_price}
            onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            required
          />
          <input
            placeholder="Fecha (yyyy-mm-dd)"
            type="date"
            value={form.entry_date}
            onChange={(e) => setForm({ ...form, entry_date: e.target.value })}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
            required
          />
          <input
            placeholder="Comisión"
            type="number"
            step="any"
            value={form.commission}
            onChange={(e) => setForm({ ...form, commission: e.target.value })}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
          />
          <button
            type="submit"
            className="bg-green-600 hover:bg-green-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Agregar
          </button>
        </form>
      )}

      {/* Positions Table */}
      <div className="bg-[#111827] rounded-xl border border-gray-800">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-800">
                <th className="text-left p-3">Ticker</th>
                <th className="text-right p-3">Cantidad</th>
                <th className="text-right p-3">Precio entrada</th>
                <th className="text-right p-3">Precio actual</th>
                <th className="text-right p-3">Invertido</th>
                <th className="text-right p-3">Valor actual</th>
                <th className="text-right p-3">P&L</th>
                <th className="text-right p-3">P&L %</th>
                <th className="text-right p-3">Fecha</th>
                <th className="text-center p-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={10} className="p-8 text-center text-gray-500">
                    No tenés posiciones abiertas. Agregá una con el botón de arriba.
                  </td>
                </tr>
              ) : (
                positions.map((pos) => (
                  <tr key={pos.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="p-3 font-medium text-white">{pos.ticker}</td>
                    <td className="p-3 text-right text-gray-300">{pos.quantity}</td>
                    <td className="p-3 text-right text-gray-300">{formatMonto(pos.entry_price)}</td>
                    <td className="p-3 text-right text-white">{pos.current_price ? formatMonto(pos.current_price) : "—"}</td>
                    <td className="p-3 text-right text-gray-300">{formatMonto(pos.invested)}</td>
                    <td className="p-3 text-right text-white">{pos.current_value ? formatMonto(pos.current_value) : "—"}</td>
                    <td className={cn("p-3 text-right font-medium", (pos.pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400")}>
                      {pos.pnl != null ? formatMonto(pos.pnl) : "—"}
                    </td>
                    <td className={cn("p-3 text-right font-medium", (pos.pnl_pct ?? 0) >= 0 ? "text-green-400" : "text-red-400")}>
                      {pos.pnl_pct != null ? formatPct(pos.pnl_pct) : "—"}
                    </td>
                    <td className="p-3 text-right text-gray-400 text-xs">{pos.entry_date}</td>
                    <td className="p-3 text-center">
                      <button
                        onClick={() => handleDelete(pos.id)}
                        className="text-red-400 hover:text-red-300 text-xs"
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
