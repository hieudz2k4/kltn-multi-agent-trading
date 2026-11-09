import { api } from "./base";

export interface BondAnalyticsRequest {
  coupon_rate: number;
  years_to_maturity: number;
  frequency: number;
  face_value: number;
  ytm?: number | null;
  price?: number | null;
}

export interface BondAnalyticsResult {
  face_value: number;
  coupon_rate: number;
  years_to_maturity: number;
  frequency: number;
  ytm: number;
  price: number;
  macaulay_duration: number;
  modified_duration: number;
  convexity: number;
  dv01: number;
  current_yield: number;
}

export async function postBondAnalytics(req: BondAnalyticsRequest): Promise<BondAnalyticsResult> {
  const { data } = await api.post<BondAnalyticsResult>("/fixed-income/bond-analytics", req);
  return data;
}

export interface GreeksRequest {
  spot: number;
  strike: number;
  time_to_expiry: number;
  rate: number;
  volatility: number;
  dividend_yield: number;
  option_type: "call" | "put";
}

export interface GreeksResult {
  price: number;
  delta: number;
  gamma: number;
  vega: number;
  theta: number;
  rho: number;
  d1: number;
  d2: number;
}

export async function postGreeks(req: GreeksRequest): Promise<GreeksResult> {
  const { data } = await api.post<GreeksResult>("/options/greeks", req);
  return data;
}

export async function postImpliedVol(
  req: Omit<GreeksRequest, "volatility"> & { market_price: number },
): Promise<{ implied_volatility: number }> {
  const { data } = await api.post<{ implied_volatility: number }>("/options/implied-vol", req);
  return data;
}
