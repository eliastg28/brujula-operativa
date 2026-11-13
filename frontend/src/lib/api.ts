// Cliente HTTP del Orquestador (FastAPI). Vite hace proxy de /api → :8000.

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, data: any) {
    super(data?.detail || `Error ${status}`);
    this.status = status;
    this.data = data;
  }
}

async function req<T = any>(method: string, url: string, body?: any): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

export const api = {
  get: <T = any>(url: string) => req<T>("GET", url),
  post: <T = any>(url: string, body: any = {}) => req<T>("POST", url, body),
  patch: <T = any>(url: string, body: any) => req<T>("PATCH", url, body),
  del: <T = any>(url: string) => req<T>("DELETE", url),
};

/** Lanza la Brújula Inteligente y entrega los eventos SSE de los agentes en vivo. */
export async function streamAnalyze(
  body: { squad: string; title: string; epic_key: string; assignee?: string | null },
  onEvent: (e: any) => void,
  signal?: AbortSignal
) {
  const res = await fetch("/api/brujula/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const t = await res.text();
    throw new Error(t || `Error ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}
