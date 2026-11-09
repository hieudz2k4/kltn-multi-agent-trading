import { api, extractApiErrorMessage } from "./base";
import type {
  AlertRule,
  AlertCondition,
  AlertTriggerEvent,
  AlertDeliveryOptions,
} from "../types";

export async function fetchAlerts(): Promise<AlertRule[]> {
  try {
    const { data } = await api.get<{ alerts: AlertRule[] }>("/alerts");
    return Array.isArray(data?.alerts) ? data.alerts : [];
  } catch (e) {
    console.error("fetchAlerts failed", e);
    return [];
  }
}

export async function fetchAlertsFiltered(opts?: { status?: string; symbol?: string }): Promise<AlertRule[]> {
  const { data } = await api.get<{ alerts: AlertRule[] }>("/alerts", {
    params: opts,
  });
  return data.alerts;
}

export async function createAlert(payload: {
  symbol?: string;
  condition_type?: string;
  parameters?: Record<string, unknown>;
  cooldown_seconds?: number;
  conditions?: AlertCondition[];
  logic?: string;
  delivery_channels?: string[];
  delivery_config?: Record<string, unknown>;
  cooldown_minutes?: number;
  expiry_date?: string | null;
  max_triggers?: number;
  ticker?: string;
  alert_type?: string;
  condition?: string;
  threshold?: number;
  note?: string;
  channels?: string[];
}): Promise<{ status: string; alert: AlertRule }> {
  try {
    const { data } = await api.post<{ status: string; alert: AlertRule }>("/alerts", payload);
    return data;
  } catch (error) {
    throw new Error(extractApiErrorMessage(error, "Failed to create alert"));
  }
}

export async function updateAlert(alertId: string, payload: {
  status?: string;
  cooldown_seconds?: number;
  parameters?: Record<string, unknown>;
  channels?: string[];
  conditions?: AlertCondition[];
  logic?: string;
  delivery_channels?: string[];
  delivery_config?: Record<string, unknown>;
  cooldown_minutes?: number;
  expiry_date?: string | null;
  max_triggers?: number;
}): Promise<{ status: string; id: string; alert: AlertRule }> {
  const { data } = await api.patch<{ status: string; id: string; alert: AlertRule }>(`/alerts/${alertId}`, payload);
  return data;
}

export async function fetchAlertHistory(page = 1, pageSize = 25): Promise<{ page: number; page_size: number; total: number; history: AlertTriggerEvent[] }> {
  const { data } = await api.get<{ page: number; page_size: number; total: number; history: AlertTriggerEvent[] }>("/alerts/history", {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function deleteAlert(alertId: string): Promise<void> {
  await api.delete(`/alerts/${alertId}`);
}

export async function testAlertDelivery(alertId: string): Promise<{ status: string; id: string; channels: string[] }> {
  const { data } = await api.post<{ status: string; id: string; channels: string[] }>(`/alerts/${alertId}/test`);
  return data;
}

export async function fetchAlertDeliveryOptions(): Promise<AlertDeliveryOptions> {
  const { data } = await api.get<AlertDeliveryOptions>("/alerts/delivery-options");
  return data;
}

export async function createScannerAlertRule(payload: {
  preset_id?: string;
  symbol: string;
  setup_type: string;
  trigger_level: number;
  invalidation_level?: number;
  near_trigger_pct?: number;
  dedupe_minutes?: number;
  enabled?: boolean;
  meta_json?: Record<string, unknown>;
}): Promise<void> {
  await api.post("/v1/alerts/scanner-rules", payload);
}
