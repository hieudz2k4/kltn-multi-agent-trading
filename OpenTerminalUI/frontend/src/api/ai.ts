import { api } from "./base";
import type {
  AIQueryResult,
} from "../types";

export async function aiQuery(query: string, context: Record<string, any>): Promise<AIQueryResult> {
  const { data } = await api.post<AIQueryResult>("/ai/query", { query, context });
  return data;
}
