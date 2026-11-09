import { api } from "./base";
import type {
  CorporateEvent,
} from "../types";

export async function fetchStockEvents(
  symbol: string,
  params?: { types?: string; from_date?: string; to_date?: string },
): Promise<CorporateEvent[]> {
  const { data } = await api.get<{ items: CorporateEvent[] }>(`/events/${encodeURIComponent(symbol)}`, { params });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchUpcomingEvents(symbol: string, days = 90): Promise<CorporateEvent[]> {
  const { data } = await api.get<{ items: CorporateEvent[] }>(`/events/${encodeURIComponent(symbol)}/upcoming`, { params: { days } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchDividendHistory(symbol: string): Promise<CorporateEvent[]> {
  const { data } = await api.get<{ items: CorporateEvent[] }>(`/events/${encodeURIComponent(symbol)}/dividends`);
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchPortfolioEvents(symbols: string[], days = 30): Promise<CorporateEvent[]> {
  if (!symbols.length) return [];
  const { data } = await api.get<{ items: CorporateEvent[] }>("/events/portfolio/upcoming", {
    params: { symbols: symbols.join(","), days },
  });
  return Array.isArray(data?.items) ? data.items : [];
}
