// Tiny fetch client — backbone (F01).
// TODO F02/F18: replace these hand-written calls with the generated OpenAPI TS client.
import type { PipelineEvent } from "@/features/activity/pipeline";
import type { Household, Recommendation } from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function getHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}

export async function postRecommend(
  body: Household,
  opts?: { fixture?: string },
): Promise<Recommendation> {
  const qs = opts?.fixture ? `?fixture=${opts.fixture}` : "";
  const res = await fetch(`${BASE}/api/v1/advisor/recommend${qs}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`recommend ${res.status}`);
  return res.json();
}

/**
 * Stream the recommendation as live PipelineEvents (SSE over a POST body).
 * Calls `onEvent` for each event; the terminal `run_completed` event carries the
 * full Recommendation in `payload.recommendation`. Throws on transport failure so
 * the caller can fall back to the simulated stream (DEV / backend offline).
 */
export async function postRecommendStream(
  body: Household,
  onEvent: (ev: PipelineEvent) => void,
  opts?: { fixture?: string },
): Promise<void> {
  const qs = opts?.fixture ? `?fixture=${opts.fixture}` : "";
  const res = await fetch(`${BASE}/api/v1/advisor/recommend/stream${qs}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`recommend/stream ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep: number;
    // SSE frames are separated by a blank line ("\n\n").
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)) as PipelineEvent);
      } catch {
        // ignore malformed frame
      }
    }
  }
}
