import { api } from "./base";
import type {
  OmsOrder,
} from "../types";

export async function createOmsOrder(payload: {
  symbol: string;
  side: "buy" | "sell" | "long" | "short";
  quantity: number;
  order_type?: string;
  limit_price?: number;
  max_position_notional?: number;
  max_adv_pct?: number;
  simulate_fill?: boolean;
}): Promise<{ order: OmsOrder; fill?: Record<string, unknown> | null }> {
  const { data } = await api.post<{ order: OmsOrder; fill?: Record<string, unknown> | null }>("/oms/order", payload);
  return data;
}

export async function fetchOmsOrders(status?: string): Promise<OmsOrder[]> {
  const { data } = await api.get<{ items: OmsOrder[] }>("/oms/orders", { params: status ? { status } : undefined });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function setRestrictedSymbol(payload: { symbol: string; reason?: string; active?: boolean }): Promise<Record<string, unknown>> {
  const { data } = await api.post<Record<string, unknown>>("/oms/restricted", payload);
  return data;
}
