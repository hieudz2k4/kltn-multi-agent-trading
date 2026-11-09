import { api } from "./base";
import type {
  FuturesChainContract,
} from "./types";

export async function fetchFuturesUnderlyings(q: string, limit = 25): Promise<string[]> {
  const { data } = await api.get<{ count: number; items: string[] }>("/futures/underlyings", { params: { q, limit } });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function fetchFuturesChain(underlying: string): Promise<{
  underlying: string;
  count: number;
  ws_symbols: string[];
  token_to_ws_symbol: Record<string, string>;
  contracts: FuturesChainContract[];
}> {
  const { data } = await api.get<{
    underlying: string;
    count: number;
    ws_symbols: string[];
    token_to_ws_symbol: Record<string, string>;
    contracts: FuturesChainContract[];
  }>(`/futures/chain/${encodeURIComponent(underlying)}`);
  return data;
}
