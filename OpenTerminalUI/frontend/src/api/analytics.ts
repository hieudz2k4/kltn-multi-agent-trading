import { api } from "./base";
import type {
  SectorRotationData,
  ChartComparisonResponse,
} from "./types";

export async function fetchSectorRotation(benchmark: string = "SPY"): Promise<SectorRotationData> {
  const { data } = await api.get<SectorRotationData>("/analytics/sector-rotation", { params: { benchmark } });
  return data;
}

export async function fetchChartComparison(symbols: string[], period = "1y", interval = "1d"): Promise<ChartComparisonResponse> {
  const { data } = await api.get<ChartComparisonResponse>("/charts/compare", {
    params: { symbols: symbols.join(","), period, interval },
  });
  return data;
}
