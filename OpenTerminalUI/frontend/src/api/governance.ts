import { api } from "./base";
import type {
  AuditEvent,
} from "../types";

export async function fetchAuditEvents(eventType?: string): Promise<AuditEvent[]> {
  const { data } = await api.get<{ items: AuditEvent[] }>("/audit", { params: eventType ? { event_type: eventType } : undefined });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function registerGovernanceRun(payload: {
  run_id: string;
  data_version_id?: string;
  code_hash?: string;
  execution_profile?: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  const { data } = await api.post<Record<string, unknown>>("/governance/runs/register", payload);
  return data;
}

export async function compareGovernanceRuns(runIds: string[]): Promise<Array<Record<string, unknown>>> {
  const { data } = await api.get<{ items: Array<Record<string, unknown>> }>("/governance/runs/compare", {
    params: { run_ids: runIds.join(",") },
  });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function promoteGovernanceModel(payload: {
  registry_name: string;
  run_id: string;
  stage?: "staging" | "prod";
  metadata?: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  const { data } = await api.post<Record<string, unknown>>("/governance/model-registry/promote", payload);
  return data;
}
