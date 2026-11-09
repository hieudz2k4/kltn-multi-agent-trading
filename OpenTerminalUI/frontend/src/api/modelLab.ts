import { api } from "./base";
import type { ExperimentCreate, ExperimentSummary, ExperimentDetail, ModelRunStatus, ModelRunReport, ModelCompareResponse } from "./types";

export async function createModelExperiment(payload: ExperimentCreate): Promise<ExperimentSummary> {
  const { data } = await api.post<ExperimentSummary>("/model-lab/experiments", payload);
  return data;
}

export async function listModelExperiments(params?: {
  tag?: string;
  model?: string;
  start_date?: string;
  end_date?: string;
}): Promise<ExperimentSummary[]> {
  const { data } = await api.get<{ items: ExperimentSummary[] }>("/model-lab/experiments", { params });
  return Array.isArray(data?.items) ? data.items : [];
}

export async function getModelExperiment(experimentId: string): Promise<ExperimentDetail> {
  const { data } = await api.get<ExperimentDetail>(`/model-lab/experiments/${encodeURIComponent(experimentId)}`);
  return data;
}

export async function runModelExperiment(experimentId: string, forceRefresh = false): Promise<{ run_id: string; status: string }> {
  const { data } = await api.post<{ run_id: string; status: string }>(`/model-lab/experiments/${encodeURIComponent(experimentId)}/run`, { force_refresh: forceRefresh });
  return data;
}

export async function getModelRunStatus(runId: string): Promise<ModelRunStatus> {
  const { data } = await api.get<ModelRunStatus>(`/model-lab/runs/${encodeURIComponent(runId)}`);
  return data;
}

export async function getModelRunReport(runId: string, forceRefresh = false): Promise<ModelRunReport> {
  const { data } = await api.get<ModelRunReport>(`/model-lab/runs/${encodeURIComponent(runId)}/report`, {
    params: { force_refresh: forceRefresh },
    timeout: 60000,
  });
  return data;
}

export async function compareModelRuns(runIds: string[]): Promise<ModelCompareResponse> {
  const { data } = await api.post<ModelCompareResponse>("/model-lab/compare", { run_ids: runIds.slice(0, 6) });
  return data;
}

export async function runModelWalkForward(experimentId: string, payload: { train_window_days: number; test_window_days: number }): Promise<Record<string, unknown>> {
  const { data } = await api.post<Record<string, unknown>>(`/model-lab/experiments/${encodeURIComponent(experimentId)}/walk-forward`, payload);
  return data;
}

export async function runModelParamSweep(experimentId: string, payload: { grid: Record<string, Array<number | string | boolean>>; max_combinations: number }): Promise<Record<string, unknown>> {
  const { data } = await api.post<Record<string, unknown>>(`/model-lab/experiments/${encodeURIComponent(experimentId)}/param-sweep`, payload);
  return data;
}
