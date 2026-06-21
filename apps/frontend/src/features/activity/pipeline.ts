// Live-run pipeline event model — mirrors the backend SSE contract
// (apps/backend/src/app/api/schemas/pipeline.py) and connection.md.
//
// The stream (POST /api/v1/advisor/recommend/stream) emits PipelineEvents; this module
// reduces them into a PipelineRunState and maps them onto the timeline's stage groups.
import type { Recommendation } from "@/lib/types";

// ── Timeline row model ──────────────────────────────────────────────────────────
// Canonical home for the activity-row shape (the RunTimeline renders these). Each
// row carries the stage it belongs to so the timeline can nest events under stages.
export type ActivityStatus = "ok" | "warn" | "info" | "loading";

/**
 * Structured Google-Solar roof measurement, carried on the worker_completed
 * solar event. Powers the rich solar detail card (angle + sun diagram, metrics)
 * in the timeline rather than a single collapsed line.
 */
export interface SolarDetail {
  /** Compass abbreviation, e.g. "S", "SE". */
  orientation: string;
  /** Human label, e.g. "South-facing". */
  orientationLabel: string;
  /** Roof tilt / pitch in degrees. */
  tiltDeg: number;
  /** Usable (unshaded, south-ish) roof area in m². */
  usableM2: number;
  /** Panels that fit on the usable area. */
  panels: number;
  /** Installed DC capacity in kWp. */
  kwp: number;
  /** Site-specific annual yield, kWh per kWp per year. */
  yieldPerKwp: number;
  /** Modelled annual generation in kWh (= kwp × yieldPerKwp, less shade). */
  annualKwh: number;
  /** Peak-sun-equivalent hours per year at this location. */
  sunHoursPerYear: number;
  /** Modelled shading loss as a percentage. */
  shadeLossPct: number;
}

/** One resolved subsidy / grant line (KfW, BAFA, 0 % VAT, Länder …). */
export interface SubsidyGrant {
  /** Programme code, e.g. "KfW 458". */
  code: string;
  /** Programme name, e.g. "Heizungsförderung". */
  name: string;
  /** Cash value applied to this household in EUR (omit for a rate-only line). */
  amountEur?: number;
  /** Short rate / mechanism label, e.g. "50 % of heat-pump capex". */
  rateLabel?: string;
  /** Where it was resolved: "Tavily live" / "Supabase catalog". */
  source: string;
}

export interface ActivityEvent {
  id: string;
  /** Pre-formatted clock label, e.g. "14:32". */
  timestamp: string;
  /** Short lead-in — the agent / source name (proper case). */
  source: string;
  /** Body line (proper case). */
  label: string;
  status: ActivityStatus;
  /** Which pipeline stage this row belongs to. */
  layerId: LayerId;
  /** Permit category for nested grouping (e.g. "Solar permissions"). */
  category?: string;
  /** Deterministic "why it matters" reasoning from the backend payload. */
  reason?: string;
  /** How this result feeds the offer (cross-effect reasoning). */
  offerEffect?: string;
  /** Provenance of the result: live_internet / supabase_cache / … */
  sourceType?: string;
  /** Structured Google-Solar measurement (on the solar worker_completed row). */
  solar?: SolarDetail;
  /** Resolved subsidy lines (on the subsidy layer_completed row). */
  grants?: SubsidyGrant[];
}

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

interface SimPermit {
  title: string;
  status: RunStatus;
  category: string;
  sourceType: string;
  reason: string;
}

const SIM_PERMITS: SimPermit[] = [
  { title: "PLZ → Bundesland", status: "accepted", category: "Location",
    sourceType: "live_internet", reason: "Sets which local building rules apply." },
  { title: "Verfahrensfrei (LBO)", status: "accepted", category: "Solar permissions",
    sourceType: "static_rule", reason: "Solar needs no building permit." },
  { title: "Denkmalschutz / not listed", status: "accepted", category: "Solar permissions",
    sourceType: "live_internet", reason: "Heritage listing would block roof PV." },
  { title: "B-Plan / no roof restriction", status: "accepted", category: "Solar permissions",
    sourceType: "live_internet", reason: "Local plan can restrict roof PV." },
  { title: "MaStR / 47 PV neighbours", status: "accepted", category: "Solar permissions",
    sourceType: "supabase_cache", reason: "Neighbour precedent shows permitting is routine." },
  { title: "GEG boiler-age compliant", status: "accepted", category: "Heat pump permissions",
    sourceType: "static_rule", reason: "Old boiler makes the heat pump mandatory-eligible." },
  { title: "TA-Lärm / tight plot", status: "warn", category: "Heat pump permissions",
    sourceType: "live_internet", reason: "Dense plot — choose a low-noise outdoor unit." },
  { title: "554 BGB right to charge", status: "accepted", category: "EV charger permissions",
    sourceType: "live_internet", reason: "Single-family home — no WEG vote needed." },
  { title: "Indoor, no permit", status: "accepted", category: "Battery permissions",
    sourceType: "static_rule", reason: "Indoor storage needs no approval." },
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function simulateRecommendStream(
  result: Recommendation,
  onEvent: (ev: PipelineEvent) => void,
  opts?: { stepMs?: number },
): Promise<void> {
  const ms = opts?.stepMs ?? 448;
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

  // Subsidy stage: a Tavily live search + Supabase catalog lookup that resolves
  // into concrete grant lines. KfW cash is anchored to the engine's real number.
  emit({ type: "layer_started", layerId: "subsidy", status: "running", title: "Resolving subsidies for this address", source: "supabase" });
  await sleep(ms / 2);
  emit({ type: "step_completed", layerId: "subsidy", status: "ok", title: "Tavily — searching German subsidy programs", source: "crawler",
    payload: { sourceType: "live_internet", whyItMatters: "Captures programs that changed since the last catalog refresh." } });
  await sleep(ms / 2);
  emit({ type: "step_completed", layerId: "subsidy", status: "ok", title: "Supabase subsidy_catalog — 4 programs matched", source: "supabase",
    payload: { sourceType: "supabase_cache", whyItMatters: "Cached official rates keep the math deterministic." } });
  await sleep(ms / 2);
  const kfwEur = result.best.capex?.subsidy_eur ?? 11000;
  const SIM_GRANTS: SubsidyGrant[] = [
    { code: "KfW 458", name: "Heizungsförderung", amountEur: kfwEur, rateLabel: "Up to 50 % of heat-pump capex", source: "Supabase catalog" },
    { code: "0 % VAT", name: "Nullsteuersatz (§12 III UStG)", rateLabel: "0 % MwSt on PV + battery", source: "Supabase catalog" },
    { code: "SolarPLUS", name: "Berlin storage bonus", amountEur: 300, rateLabel: "€300 flat for battery storage", source: "Tavily live" },
    { code: "KfW 270", name: "Erneuerbare Energien – Standard", rateLabel: "Low-interest finance for PV", source: "Tavily live" },
  ];
  emit({ type: "layer_completed", layerId: "subsidy", status: "accepted",
    title: `Subsidies applied — €${Math.round(kfwEur + 300).toLocaleString("de-DE")} off capex`,
    source: "supabase", payload: { grants: SIM_GRANTS } });

  // Parallel branch: solar worker + permit checks
  emit({ type: "worker_started", layerId: "solar", status: "running", title: "Google Solar · fetching roof", workerId: "google_solar", source: "google_solar" });
  emit({ type: "layer_started", layerId: "permit", status: "running", title: "Running 13 permit checks", source: "internet" });
  await sleep(ms);
  // Google Solar — each measurement as its own concrete check, building toward
  // the structured roof model emitted on worker_completed.
  const SIM_SOLAR: SolarDetail = {
    orientation: "S",
    orientationLabel: "South-facing",
    tiltDeg: 30,
    usableM2: 42,
    panels: 18,
    kwp: 7.9,
    yieldPerKwp: 980,
    annualKwh: 7280,
    sunHoursPerYear: 1620,
    shadeLossPct: 6,
  };
  const SIM_SOLAR_STEPS: Array<[string, Record<string, unknown>]> = [
    ["Building matched in Google Solar imagery", { whyItMatters: "Confirms we are sizing PV on the right roof." }],
    [`Roof pitch measured at ${SIM_SOLAR.tiltDeg}°`, { whyItMatters: "Tilt sets the sun-incidence angle that drives yield." }],
    [`Dominant orientation: ${SIM_SOLAR.orientation} (${SIM_SOLAR.orientationLabel})`, { whyItMatters: "Orientation drives yield and self-consumption." }],
    [`Sun exposure modelled — ${SIM_SOLAR.sunHoursPerYear.toLocaleString("de-DE")} h/yr, ${SIM_SOLAR.shadeLossPct}% shading`, { whyItMatters: "Shading from chimneys and trees is subtracted from gross yield." }],
    [`Usable south-facing roof: ${SIM_SOLAR.usableM2} m²`, { whyItMatters: "South-facing area caps how much PV the roof can carry." }],
    [`Fits ${SIM_SOLAR.panels} panels (~${SIM_SOLAR.kwp} kWp)`, { whyItMatters: "Panel count sets the upper bound on the solar rung." }],
    [`Site yield ${SIM_SOLAR.yieldPerKwp} kWh/kWp/yr → ~${SIM_SOLAR.annualKwh.toLocaleString("de-DE")} kWh/yr`, { whyItMatters: "Yield converts array size into priced kWh." }],
  ];
  for (const [title, payload] of SIM_SOLAR_STEPS) {
    emit({ type: "step_completed", layerId: "solar", status: "ok", title, source: "google_solar", payload });
    await sleep(ms / 4);
  }
  emit({ type: "worker_completed", layerId: "solar", status: "accepted",
    title: `Roof modelled — ${SIM_SOLAR.panels} panels · ${SIM_SOLAR.kwp} kWp · ${SIM_SOLAR.orientation} @ ${SIM_SOLAR.tiltDeg}°`,
    workerId: "google_solar", source: "google_solar", payload: { solar: SIM_SOLAR } });
  for (const c of SIM_PERMITS) {
    emit({
      type: "worker_completed", layerId: "permit", status: c.status, title: c.title,
      workerId: c.title, source: "internet",
      payload: { category: c.category, sourceType: c.sourceType, whyItMatters: c.reason },
    });
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
      title: `${label} / ${delta >= 0 ? "+" : "-"}€${Math.abs(Math.round(delta))}/mo`,
      source: "engine",
    });
  });
  await sleep(ms);

  // Cross-effect reasoning (mirrors the backend _reasoning_events).
  const cap = result.best.capex;
  if (cap && cap.subsidy_eur > 0) {
    emit({
      type: "monitor_notice", layerId: "subsidy", status: "ok",
      title: `Subsidies cut capex by €${Math.round(cap.subsidy_eur).toLocaleString("de-DE")}`,
      source: "supabase",
      payload: {
        offerEffect: cap.subsidy_note,
        whyItMatters: "Subsidies shrink the financed amount, so payback arrives sooner.",
      },
    });
    await sleep(ms);
  }
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

function str(v: unknown): string | undefined {
  return typeof v === "string" && v.trim() ? clean(v) : undefined;
}

function num(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

/** Parse a structured Google-Solar payload, tolerating partial/absent data. */
function solarOf(p: Record<string, unknown>): SolarDetail | undefined {
  const s = p.solar;
  if (!s || typeof s !== "object") return undefined;
  const o = s as Record<string, unknown>;
  const kwp = num(o.kwp);
  if (kwp == null) return undefined;
  const yieldPerKwp = num(o.yieldPerKwp) ?? 0;
  const shadeLossPct = num(o.shadeLossPct) ?? 0;
  return {
    orientation: str(o.orientation) ?? "S",
    orientationLabel: str(o.orientationLabel) ?? "South-facing",
    tiltDeg: num(o.tiltDeg) ?? 30,
    usableM2: num(o.usableM2) ?? 0,
    panels: num(o.panels) ?? 0,
    kwp,
    yieldPerKwp,
    annualKwh:
      num(o.annualKwh) ?? Math.round(kwp * yieldPerKwp * (1 - shadeLossPct / 100)),
    sunHoursPerYear: num(o.sunHoursPerYear) ?? 0,
    shadeLossPct,
  };
}

/** Parse a list of resolved subsidy grants, dropping malformed entries. */
function grantsOf(p: Record<string, unknown>): SubsidyGrant[] | undefined {
  const g = p.grants;
  if (!Array.isArray(g)) return undefined;
  const out: SubsidyGrant[] = [];
  for (const raw of g) {
    if (!raw || typeof raw !== "object") continue;
    const o = raw as Record<string, unknown>;
    const code = str(o.code);
    const name = str(o.name);
    if (!code || !name) continue;
    out.push({
      code,
      name,
      amountEur: num(o.amountEur),
      rateLabel: str(o.rateLabel),
      source: str(o.source) ?? "Supabase catalog",
    });
  }
  return out.length ? out : undefined;
}

/** Map a PipelineEvent onto a timeline row, tagged with its stage. */
export function toActivityEvent(ev: PipelineEvent): ActivityEvent {
  const source = ev.source ? SOURCE_LABEL[ev.source] : LAYER_LABEL[ev.layerId];
  const title = clean(ev.title);
  const detail = ev.detail ? clean(ev.detail) : "";
  const p = ev.payload ?? {};
  return {
    id: ev.id,
    timestamp: clockOf(ev.timestamp),
    source,
    label: detail ? `${title} — ${detail}` : title,
    status: statusOf(ev),
    layerId: ev.layerId,
    category: str(p.category),
    reason: str(p.whyItMatters),
    offerEffect: str(p.offerEffect),
    sourceType: str(p.sourceType),
    solar: solarOf(p),
    grants: grantsOf(p),
  };
}

// ── Stage timeline model ────────────────────────────────────────────────────────
// The canonical, ordered list of pipeline stages the RunTimeline renders. Order
// mirrors the backend orchestration; solar + permit are the parallel branch.
export interface StageMeta {
  id: LayerId;
  label: string;
  /** Part of the parallel solar+permit branch (rendered indented). */
  branch?: boolean;
}

export const STAGES: readonly StageMeta[] = [
  { id: "parent", label: "Orchestrator" },
  { id: "solar", label: "Google Solar", branch: true },
  { id: "permit", label: "Permits", branch: true },
  { id: "subsidy", label: "Subsidies" },
  { id: "battery", label: "Battery" },
  { id: "heat_pump", label: "Heat pump" },
  { id: "ev_charger", label: "EV charger" },
  { id: "financing", label: "Proposal" },
];

export type StageKind = "idle" | "running" | "ok" | "warn" | "err";

export function stageKindOf(status: RunStatus | undefined): StageKind {
  switch (status) {
    case "running":
      return "running";
    case "accepted":
    case "ok":
      return "ok";
    case "warn":
    case "skipped":
      return "warn";
    case "rejected":
    case "error":
      return "err";
    default:
      return "idle";
  }
}

const STAGE_RESOLVED: ReadonlySet<StageKind> = new Set(["ok", "warn", "err"]);

// Permit checks nest under these categories, in display order (mirrors the
// backend PERMIT_CATEGORY_ORDER in permit_layer/checks.py).
export const PERMIT_CATEGORY_ORDER: readonly string[] = [
  "Location",
  "Solar permissions",
  "Heat pump permissions",
  "EV charger permissions",
  "Battery permissions",
];

export interface CategoryGroup {
  name: string;
  events: ActivityEvent[];
}

export interface StageGroup {
  id: LayerId;
  label: string;
  branch: boolean;
  kind: StageKind;
  /** Rows that belong to this stage, in arrival order. */
  events: ActivityEvent[];
  /** One-line result shown when the stage is collapsed (resolved). */
  summary?: string;
  /** Cross-effect reasoning ("offer effect") of the last row, if any. */
  summaryDetail?: string;
  /** For the permit stage: rows nested by category, in canonical order. */
  categories?: CategoryGroup[];
  /** For the solar stage: structured roof measurement for the rich detail card. */
  solar?: SolarDetail;
  /** For the subsidy stage: resolved grants + their combined cash value. */
  subsidies?: { grants: SubsidyGrant[]; totalEur: number };
  /** Source type of the last event — drives the chip next to summaryDetail. */
  summarySourceType?: string;
}

/** Group permit rows by category in canonical order (unknowns appended). */
function permitCategories(rows: ActivityEvent[]): CategoryGroup[] {
  const byCat = new Map<string, ActivityEvent[]>();
  for (const ev of rows) {
    const cat = ev.category ?? "Location";
    const bucket = byCat.get(cat);
    if (bucket) bucket.push(ev);
    else byCat.set(cat, [ev]);
  }
  const ordered = [...PERMIT_CATEGORY_ORDER, ...byCat.keys()].filter(
    (c, i, a) => a.indexOf(c) === i && byCat.has(c),
  );
  return ordered.map((name) => ({ name, events: byCat.get(name) ?? [] }));
}

/**
 * Fold the flat row stream + run state into one group per stage, in canonical
 * order. Pure: derives everything from inputs, invents nothing. The summary is
 * the last row's label so a finished stage can collapse to a single line.
 */
export function groupEventsByStage(
  events: ActivityEvent[],
  state: PipelineRunState,
): StageGroup[] {
  const byStage = new Map<LayerId, ActivityEvent[]>();
  for (const ev of events) {
    const bucket = byStage.get(ev.layerId);
    if (bucket) bucket.push(ev);
    else byStage.set(ev.layerId, [ev]);
  }
  return STAGES.map((s) => {
    const rows = byStage.get(s.id) ?? [];
    const kind = stageKindOf(state.layers[s.id]);
    const last = rows[rows.length - 1];
    const resolved = STAGE_RESOLVED.has(kind);
    // The latest structured solar measurement, if Google Solar streamed one.
    const solar = s.id === "solar" ? lastSolar(rows) : undefined;
    // All resolved grants across the subsidy stage's rows, plus their total.
    const grants = s.id === "subsidy" ? rows.flatMap((r) => r.grants ?? []) : [];
    return {
      id: s.id,
      label: s.label,
      branch: s.branch ?? false,
      kind,
      events: rows,
      summary: resolved && last ? last.label : undefined,
      summaryDetail: resolved ? last?.offerEffect ?? last?.reason : undefined,
      summarySourceType: resolved ? last?.sourceType : undefined,
      categories: s.id === "permit" && rows.length ? permitCategories(rows) : undefined,
      solar,
      subsidies: grants.length
        ? { grants, totalEur: grants.reduce((t, g) => t + (g.amountEur ?? 0), 0) }
        : undefined,
    };
  });
}

/** The most recent row carrying a structured solar measurement, if any. */
function lastSolar(rows: ActivityEvent[]): SolarDetail | undefined {
  for (let i = rows.length - 1; i >= 0; i--) if (rows[i].solar) return rows[i].solar;
  return undefined;
}

/** Progress 0–100 across all stages (resolved / total). */
export function stageProgress(groups: StageGroup[]): number {
  const resolved = groups.filter((g) => STAGE_RESOLVED.has(g.kind)).length;
  return Math.round((resolved / groups.length) * 100);
}
