// Live-run pipeline event model — mirrors the backend SSE contract
// (apps/backend/src/app/api/schemas/pipeline.py) and connection.md.
//
// The stream (POST /api/v1/advisor/recommend/stream) emits PipelineEvents; this module
// reduces them into a PipelineRunState and maps them onto the ActivityFeed's flat rows.
import type { ActivityEvent, ActivityStatus } from "@/features/activity/ActivityFeed";
import type { Recommendation } from "@/lib/types";

export type LayerId =
  | "parent"
  | "solar"
  | "battery"
  | "heat_pump"
  | "ev_charger"
  | "subsidy"
  | "permit"
  | "financing";

export type RunStatus =
  | "queued"
  | "running"
  | "accepted"
  | "rejected"
  | "skipped"
  | "error"
  | "ok"
  | "warn";

export type PipelineEventType =
  | "run_started"
  | "layer_started"
  | "worker_started"
  | "worker_heartbeat"
  | "worker_completed"
  | "step_started"
  | "step_progress"
  | "step_completed"
  | "dependency_waiting"
  | "dependency_resolved"
  | "monitor_notice"
  | "fallback_used"
  | "layer_completed"
  | "layer_error"
  | "run_completed"
  | "run_error";

export type PipelineSource =
  | "database"
  | "internet"
  | "pdf"
  | "google_solar"
  | "supabase"
  | "engine"
  | "crawler"
  | "llm";

export interface PipelineEvent {
  id: string;
  runId: string;
  timestamp: string;
  layerId: LayerId;
  type: PipelineEventType;
  status: RunStatus;
  title: string;
  parentLayerId?: LayerId;
  stepId?: string;
  workerId?: string;
  detail?: string;
  source?: PipelineSource;
  payload?: Record<string, unknown>;
}

export interface WorkerRow {
  id: string;
  layerId: LayerId;
  title: string;
  status: RunStatus;
  source?: PipelineSource;
}

export interface PipelineRunState {
  runId: string | null;
  status: "idle" | "running" | "completed" | "error";
  events: PipelineEvent[];
  layers: Partial<Record<LayerId, RunStatus>>;
  workers: Record<string, WorkerRow>;
  result?: Recommendation;
}

export function initialRunState(): PipelineRunState {
  return { runId: null, status: "idle", events: [], layers: {}, workers: {} };
}

const LAYER_RESOLVED: ReadonlySet<PipelineEventType> = new Set([
  "layer_completed",
  "layer_error",
]);

/** Pure reducer: fold one event into the run state (drives feed + graph). */
export function applyEvent(state: PipelineRunState, ev: PipelineEvent): PipelineRunState {
  const next: PipelineRunState = {
    ...state,
    runId: state.runId ?? ev.runId,
    events: [...state.events, ev],
    layers: { ...state.layers },
    workers: { ...state.workers },
  };

  // Layer status
  if (ev.type === "layer_started") next.layers[ev.layerId] = "running";
  else if (LAYER_RESOLVED.has(ev.type)) next.layers[ev.layerId] = ev.status;
  else if (!next.layers[ev.layerId] && ev.status === "running")
    next.layers[ev.layerId] = "running";

  // Worker lanes (parallel work)
  if (ev.workerId) {
    if (ev.type === "worker_completed" || ev.type === "fallback_used") {
      next.workers[ev.workerId] = {
        id: ev.workerId,
        layerId: ev.layerId,
        title: ev.title,
        status: ev.status,
        source: ev.source,
      };
    } else if (ev.type === "worker_started") {
      next.workers[ev.workerId] = {
        id: ev.workerId,
        layerId: ev.layerId,
        title: ev.title,
        status: "running",
        source: ev.source,
      };
    }
  }

  // Run lifecycle + terminal payload
  if (ev.type === "run_started") next.status = "running";
  else if (ev.type === "run_completed") {
    next.status = "completed";
    next.layers.parent = "accepted"; // resolve the orchestrator node → rail hits 100%
    const rec = ev.payload?.recommendation as Recommendation | undefined;
    if (rec) next.result = rec;
  } else if (ev.type === "run_error") {
    next.status = "error";
    next.layers.parent = "error";
  }

  return next;
}

/** Count of workers currently running (for the "N checks running in parallel" pill). */
export function activeWorkerCount(state: PipelineRunState): number {
  return Object.values(state.workers).filter((w) => w.status === "running").length;
}

// ── ActivityFeed mapping ───────────────────────────────────────────────────────
const SOURCE_LABEL: Record<PipelineSource, string> = {
  database: "Database",
  internet: "Internet",
  pdf: "PDF",
  google_solar: "Google Solar",
  supabase: "Supabase",
  engine: "Engine",
  crawler: "Crawler",
  llm: "LLM",
};

const LAYER_LABEL: Record<LayerId, string> = {
  parent: "Orchestrator",
  solar: "Solar",
  battery: "Battery",
  heat_pump: "Heat pump",
  ev_charger: "EV charger",
  subsidy: "Subsidy",
  permit: "Permits",
  financing: "Financing",
};

function clockOf(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

function statusOf(ev: PipelineEvent): ActivityStatus {
  if (
    ev.type === "fallback_used" ||
    ev.type === "layer_error" ||
    ev.type === "run_error" ||
    ev.status === "error" ||
    ev.status === "rejected" ||
    ev.status === "warn"
  )
    return "warn";
  if (ev.status === "running" || ev.type.endsWith("_started")) return "loading";
  if (ev.status === "accepted" || ev.status === "ok") return "ok";
  return "info";
}

// ── DEV / offline simulator ─────────────────────────────────────────────────────
// Plays a scripted-but-realistic event stream, then resolves to the given golden
// Recommendation — so the live UI works with no backend running. Numbers come from
// the supplied `result`, never invented.
const RUNG: Array<[LayerId, string]> = [
  ["solar", "Solar"],
  ["battery", "Battery"],
  ["heat_pump", "Heat pump"],
  ["ev_charger", "EV charger"],
];

const SIM_PERMITS: Array<[string, RunStatus]> = [
  ["Solar / verfahrensfrei (LBO)", "accepted"],
  ["Denkmalschutz / not listed", "accepted"],
  ["B-Plan / no roof restriction", "accepted"],
  ["MaStR / 47 PV neighbours", "accepted"],
  ["Heat pump / GEG compliant", "accepted"],
  ["TA-Lärm / tight plot", "warn"],
  ["EV / 554 BGB right to charge", "accepted"],
  ["Battery / indoor, no permit", "accepted"],
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function simulateRecommendStream(
  result: Recommendation,
  onEvent: (ev: PipelineEvent) => void,
  opts?: { stepMs?: number },
): Promise<void> {
  const ms = opts?.stepMs ?? 320;
  const runId = `sim-${Math.floor(Date.now() % 1e7)}`;
  let seq = 0;
  const emit = (e: Omit<PipelineEvent, "id" | "runId" | "timestamp">) => {
    onEvent({ ...e, id: `${runId}-${seq++}`, runId, timestamp: new Date().toISOString() });
  };

  emit({ type: "run_started", layerId: "parent", status: "running", title: "Starting recommendation run" });
  await sleep(ms);
  emit({ type: "step_started", layerId: "parent", status: "running", title: "Geocoding address", source: "google_solar" });
  await sleep(ms);
  emit({ type: "step_completed", layerId: "parent", status: "ok", title: "Address located", source: "google_solar" });
  emit({ type: "layer_started", layerId: "subsidy", status: "running", title: "Checking subsidy catalog", source: "supabase" });
  await sleep(ms);
  emit({ type: "layer_completed", layerId: "subsidy", status: "accepted", title: "Subsidy catalog applied", source: "supabase" });

  // Parallel branch: solar worker + permit checks
  emit({ type: "worker_started", layerId: "solar", status: "running", title: "Google Solar · fetching roof", workerId: "google_solar", source: "google_solar" });
  emit({ type: "layer_started", layerId: "permit", status: "running", title: "Running 12 permit checks", source: "internet" });
  await sleep(ms);
  emit({ type: "worker_completed", layerId: "solar", status: "accepted", title: "Roof / 18 panels / S / 980 kWh/kWp", workerId: "google_solar", source: "google_solar" });
  for (const [title, status] of SIM_PERMITS) {
    emit({ type: "worker_completed", layerId: "permit", status, title, workerId: title, source: "internet" });
    await sleep(ms / 3);
  }
  emit({ type: "layer_completed", layerId: "permit", status: "accepted", title: "Permit checks complete", source: "internet" });
  await sleep(ms);

  // Ladder rungs from the real result
  let prev = 0;
  result.alternatives.slice(0, RUNG.length).forEach((alt, idx) => {
    const [layerId, label] = RUNG[idx];
    const delta = alt.monthly_saving_eur - prev;
    prev = alt.monthly_saving_eur;
    emit({
      type: "layer_completed",
      layerId,
      status: "accepted",
      title: `${label} / +€${delta.toFixed(0)}/mo`,
      source: "engine",
    });
  });
  await sleep(ms);
  emit({ type: "layer_started", layerId: "financing", status: "running", title: "Writing the proposal", source: "llm" });
  await sleep(ms);
  emit({ type: "layer_completed", layerId: "financing", status: "accepted", title: "Proposal ready", source: "llm" });
  emit({
    type: "run_completed",
    layerId: "parent",
    status: "accepted",
    title: `Done · €${result.best.monthly_saving_eur.toFixed(0)}/mo with ${result.best.scenario_id}`,
    source: "engine",
    payload: { recommendation: result },
  });
}

// Strip emoji / pictographs / arrows so the feed stays text-clean regardless of source.
const EMOJI = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}]/gu;
const VARIATION = /️/g;
const clean = (s: string) =>
  s.replace(EMOJI, "").replace(VARIATION, "").replace(/\s{2,}/g, " ").trim();

/** Map a PipelineEvent onto a flat ActivityFeed row. */
export function toActivityEvent(ev: PipelineEvent): ActivityEvent {
  const source = ev.source ? SOURCE_LABEL[ev.source] : LAYER_LABEL[ev.layerId];
  const title = clean(ev.title);
  const detail = ev.detail ? clean(ev.detail) : "";
  return {
    id: ev.id,
    timestamp: clockOf(ev.timestamp),
    source: source.toLowerCase(),
    label: detail ? `${title} / ${detail}` : title,
    status: statusOf(ev),
  };
}
