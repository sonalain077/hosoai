import type {
  AgentReply,
  FormDetail,
  FormSummary,
  LearnResult,
  MatchResult,
  OfficialForm,
  Procedure,
  ProcedureSummary,
  Profile,
} from "./types";

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

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function agentStart(query: string): Promise<AgentReply> {
  return request("/agent", json({ query }));
}

export function agentAnswer(sessionId: string, answer: string): Promise<AgentReply> {
  return request(`/agent/${encodeURIComponent(sessionId)}`, json({ answer }));
}

export function getProfile(): Promise<Profile> {
  return request("/profile");
}

export function saveProfile(profile: Profile): Promise<Profile> {
  return request("/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
}

export function listForms(): Promise<FormSummary[]> {
  return request("/forms");
}

export async function getForm(id: string, procedure?: string): Promise<FormDetail | null> {
  const q = procedure ? `?procedure=${encodeURIComponent(procedure)}` : "";
  try {
    return await request<FormDetail>(`/forms/${encodeURIComponent(id)}${q}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export const blankPageUrl = (id: string, page: number) =>
  `${API_URL}/forms/${encodeURIComponent(id)}/pages/${page}.png`;

/** Image of one filled page, for review on screen. */
export async function previewPage(
  id: string,
  page: number,
  values: Record<string, string>,
): Promise<Blob> {
  const resp = await fetch(`${API_URL}/forms/${encodeURIComponent(id)}/preview/${page}.png`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ values }),
  });
  if (!resp.ok) throw new ApiError(`preview → ${resp.status}`, resp.status);
  return resp.blob();
}

/** Builds the filled PDF locally on our server. Nothing is submitted to any authority. */
export async function fillForm(id: string, values: Record<string, string>): Promise<Blob> {
  const resp = await fetch(`${API_URL}/forms/${encodeURIComponent(id)}/fill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ values, reviewed: true }),
  });
  if (!resp.ok) throw new ApiError(`fill → ${resp.status}`, resp.status);
  return resp.blob();
}

export const formHref = (id: string, procedure: string) =>
  `/forms/${encodeURIComponent(id)}?procedure=${encodeURIComponent(procedure)}`;

export function officialForms(slug: string): Promise<OfficialForm[]> {
  return request(`/procedures/${encodeURIComponent(slug)}/official-forms`);
}

/** Ask the form-learning agent to read an official form (20-90 s with a local model). */
export async function learnForm(procedure: string, formIndex: number): Promise<LearnResult> {
  const resp = await fetch(`${API_URL}/forms/learn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ procedure, form_index: formIndex }),
  });
  if (!resp.ok) {
    const body = (await resp.json().catch(() => null)) as { detail?: { message?: string } } | null;
    throw new ApiError(body?.detail?.message ?? `learn → ${resp.status}`, resp.status);
  }
  return (await resp.json()) as LearnResult;
}
