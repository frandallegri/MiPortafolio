import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMonto(value: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
  }).format(value);
}

export function formatPct(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function scoreColor(score: number): string {
  if (score >= 70) return "text-green-400";
  if (score >= 60) return "text-yellow-400";
  if (score >= 40) return "text-gray-400";
  return "text-red-400";
}

export function scoreBgColor(score: number): string {
  if (score >= 70) return "bg-green-500/20 border-green-500/30";
  if (score >= 60) return "bg-yellow-500/20 border-yellow-500/30";
  if (score >= 40) return "bg-gray-500/20 border-gray-500/30";
  return "bg-red-500/20 border-red-500/30";
}

export function signalBadge(signal: string): { text: string; color: string } {
  switch (signal) {
    case "compra":
      return { text: "COMPRA", color: "bg-green-500/20 text-green-400 border-green-500/40" };
    case "venta":
      return { text: "VENTA", color: "bg-red-500/20 text-red-400 border-red-500/40" };
    default:
      return { text: "NEUTRAL", color: "bg-gray-500/20 text-gray-400 border-gray-500/40" };
  }
}
