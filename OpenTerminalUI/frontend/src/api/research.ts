import { api } from "./base";

export type ResearchItem = {
  id: string;
  source: string;
  external_id: string;
  title: string;
  authors: string[];
  abstract: string;
  url: string;
  categories: string[];
  published_at: string;
  text_chars?: number;
  score?: number;
};

export async function ingestResearch(
  query: string,
  max_results = 25,
): Promise<{ ingested: number; fetched: number; query: string }> {
  const { data } = await api.post<{ ingested: number; fetched: number; query: string }>("/research/ingest", {
    query,
    max_results,
  });
  return data;
}

export async function ingestUrlResearch(
  url: string,
): Promise<{ ingested: number; url: string; title: string; text_chars: number }> {
  const { data } = await api.post<{ ingested: number; url: string; title: string; text_chars: number }>(
    "/research/ingest_url",
    { url },
  );
  return data;
}

export async function searchResearch(q: string, k = 10): Promise<{ query: string; results: ResearchItem[] }> {
  const { data } = await api.get<{ query: string; results: ResearchItem[] }>("/research/search", {
    params: { q, k },
  });
  return data;
}

export async function listResearch(limit = 50): Promise<{ items: ResearchItem[] }> {
  const { data } = await api.get<{ items: ResearchItem[] }>("/research/items", {
    params: { limit },
  });
  return data;
}
