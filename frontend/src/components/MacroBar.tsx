"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

interface DollarRate { compra: number; venta: number; }

const SEPARATORS = ["◆", "◆", "◆", "◆", "◆", "◆"];

export default function MacroBar() {
  const [rates, setRates] = useState<Record<string, DollarRate>>({});
  const [macro, setMacro] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [dollarData, macroData] = await Promise.all([
          api.getDollarRates().catch(() => ({})),
          api.getMacroLatest().catch(() => ({})),
        ]);
        setRates(dollarData);
        setMacro(macroData);
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 60_000);
    return () => clearInterval(interval);
  }, []);

  const items = [
    {
      label: "MEP",
      value: rates.dolar_mep?.venta,
      color: "text-sky-400",
      dot: "bg-sky-500",
    },
    {
      label: "CCL",
      value: rates.dolar_ccl?.venta,
      color: "text-violet-400",
      dot: "bg-violet-500",
    },
    {
      label: "BLUE",
      value: rates.dolar_blue?.venta,
      color: "text-amber-400",
      dot: "bg-amber-500",
    },
    {
      label: "OFICIAL",
      value: rates.dolar_oficial?.venta,
      color: "text-emerald-400",
      dot: "bg-emerald-500",
    },
    {
      label: "MAYORISTA",
      value: rates.dolar_mayorista?.venta,
      color: "text-teal-400",
      dot: "bg-teal-500",
    },
    {
      label: "TARJETA",
      value: rates.dolar_tarjeta?.venta,
      color: "text-orange-400",
      dot: "bg-orange-500",
    },
    {
      label: "RIESGO PAÍS",
      value: macro.riesgo_pais?.value,
      color: "text-red-400",
      dot: "bg-red-500",
      prefix: "",
      decimals: 0,
    },
    {
      label: "MERVAL",
      value: macro.merval?.value,
      color: "text-blue-400",
      dot: "bg-blue-500",
      prefix: "",
      decimals: 0,
    },
  ];

  if (loading) {
    return (
      <div className="h-9 border-b border-[#1a2233] bg-[#080b10]">
        <div className="h-full flex items-center px-4 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-3 w-24 bg-gray-800 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  // Duplicate for seamless loop
  const tickerItems = [...items, ...items];

  return (
    <div className="h-9 border-b border-[#1a2233] bg-[#080b10] overflow-hidden relative">
      {/* Left fade */}
      <div className="absolute left-0 top-0 bottom-0 w-8 z-10 bg-gradient-to-r from-[#080b10] to-transparent pointer-events-none" />
      {/* Right fade */}
      <div className="absolute right-0 top-0 bottom-0 w-8 z-10 bg-gradient-to-l from-[#080b10] to-transparent pointer-events-none" />

      <div className="ticker-track h-full items-center flex">
        {tickerItems.map((item, idx) => (
          <div key={idx} className="flex items-center gap-4 px-5 h-full">
            <div className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${item.dot} opacity-70`} />
              <span className="text-[10px] font-medium tracking-widest text-gray-600 uppercase">
                {item.label}
              </span>
              <span className={`text-xs num font-semibold ${item.color} ml-1`}>
                {item.value != null
                  ? `${item.prefix ?? "$"}${formatNumber(item.value, item.decimals ?? 0)}`
                  : "—"}
              </span>
            </div>
            <span className="text-gray-800 text-xs select-none">◆</span>
          </div>
        ))}
      </div>
    </div>
  );
}
