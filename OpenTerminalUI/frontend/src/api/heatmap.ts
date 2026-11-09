import { api } from "./base";
import type { HeatmapMarket, HeatmapGroupBy, HeatmapPeriod, HeatmapSizeBy, HeatmapTreemapResponse } from "./types";

export async function fetchMarketHeatmap(params: {
  market: HeatmapMarket;
  group: HeatmapGroupBy;
  period: HeatmapPeriod;
  sizeBy: HeatmapSizeBy;
}): Promise<HeatmapTreemapResponse> {
  const { data } = await api.get<HeatmapTreemapResponse>("/heatmap/treemap", {
    params: {
      market: params.market,
      group: params.group,
      period: params.period,
      size_by: params.sizeBy,
    },
  });
  return data;
}
