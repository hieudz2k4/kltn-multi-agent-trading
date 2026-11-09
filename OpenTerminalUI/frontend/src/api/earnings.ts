import { api } from "./base";
import type {
  EarningsDate,
  QuarterlyFinancial,
  EarningsAnalysis,
} from "../types";

export async function fetchEarningsCalendar(
  params?: { from_date?: string; to_date?: string; symbols?: string[] },
): Promise<EarningsDate[]> {
  const query = {
    from_date: params?.from_date,
    to_date: params?.to_date,
    symbols: params?.symbols?.length ? params.symbols.join(",") : undefined,
  };
  const { data } = await api.get<{ items: EarningsDate[] }>("/earnings/calendar", { params: query });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchNextEarnings(symbol: string): Promise<EarningsDate | null> {
  const { data } = await api.get<{ item: EarningsDate | null }>(`/earnings/${encodeURIComponent(symbol)}/next`);
  return data?.item ?? null;
}

export async function fetchQuarterlyEarningsFinancials(symbol: string, quarters = 12): Promise<QuarterlyFinancial[]> {
  const { data } = await api.get<{ items: QuarterlyFinancial[] }>(`/earnings/${encodeURIComponent(symbol)}/financials`, { params: { quarters } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchEarningsAnalysis(symbol: string): Promise<EarningsAnalysis> {
  const { data } = await api.get<EarningsAnalysis>(`/earnings/${encodeURIComponent(symbol)}/analysis`);
  return data;
}

export async function fetchPortfolioEarnings(symbols: string[], days = 30): Promise<EarningsDate[]> {
  if (!symbols.length) return [];
  const { data } = await api.get<{ items: EarningsDate[] }>("/earnings/portfolio", {
    params: { symbols: symbols.join(","), days },
  });
  return Array.isArray(data?.items) ? data.items : [];
}
