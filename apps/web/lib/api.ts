import type { MatchResult, Procedure, ProcedureSummary } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!resp.ok) throw new ApiError(`${path} → ${resp.status}`, resp.status);
  return (await resp.json()) as T;
}

export function listProcedures(): Promise<ProcedureSummary[]> {
  return request("/procedures");
}

/** Returns null when the backend has no official source for this slug (404). */
export async function getProcedure(slug: string): Promise<Procedure | null> {
  try {
    return await request<Procedure>(`/procedures/${encodeURIComponent(slug)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export function ask(query: string): Promise<MatchResult> {
  return request("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}
