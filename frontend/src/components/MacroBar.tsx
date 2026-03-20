"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

interface DollarRate {
  compra: number;
  venta: number;
}

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
    const interval = setInterval(load, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="h-10 bg-[#0d1117] border-b border-gray-800 animate-pulse" />
    );
  }

  const items = [
    { label: "Dólar MEP", value: rates.dolar_mep?.venta },
    { label: "Dólar CCL", value: rates.dolar_ccl?.venta },
    { label: "Dólar Blue", value: rates.dolar_blue?.venta },
    { label: "Dólar Oficial", value: rates.dolar_oficial?.venta },
    { label: "Riesgo País", value: macro.riesgo_pais?.value, prefix: "", decimals: 0 },
    { label: "Merval", value: macro.merval?.value, prefix: "", decimals: 0 },
  ];

  return (
    <div className="h-10 bg-[#0d1117] border-b border-gray-800 flex items-center px-4 gap-6 overflow-x-auto text-xs">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5 whitespace-nowrap">
          <span className="text-gray-500">{item.label}</span>
          <span className="text-white font-medium">
            {item.value
              ? `${item.prefix ?? "$"}${formatNumber(item.value, item.decimals ?? 2)}`
              : "—"}
          </span>
        </div>
      ))}
    </div>
  );
}
