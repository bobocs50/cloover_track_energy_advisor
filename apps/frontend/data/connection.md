# Frontend Data Connection — Live Run + Zoom-In Bubbles

This is one experience in two acts:

1. **The live run** — when a recommendation starts, the UI shows what the backend is *actually doing*:
   many checks start, some run in parallel, some wait for dependencies, some retry or fall back, and
   the system keeps monitoring until a final plan is assembled. A live control room, not a spinner.
2. **The zoom-in payoff** — once the run finishes, the user clicks a component on the 3D house (the
   heat pump, the solar array, the battery, the EV charger), the camera zooms to it, and a white
   bubble appears with the *interesting numbers the engine computed* for that one component.

The two are tightly coupled: **the live run fills the bubbles, the zoom-in reveals them.** As each
backend layer completes, its 3D module lights up from "computing" to "ready/clickable" — the house
visibly assembles itself from verified backend work, then the user clicks in.

---

## Goal

Connect the frontend to the backend recommendation pipeline so the user can see the work starting,
running in parallel, being monitored, moving through each layer, and producing accepted, rejected, or
error results in real time — then explore the finished result component-by-component on the 3D model.

The UI should not only show a final recommendation. The main product value is showing what is actually
happening behind the scenes, and then letting the user interrogate every number.

- the parent orchestration layer starts the run
- independent checks start in parallel when possible
- dependent layers wait for required outputs
- the user sees which workers are active, queued, blocked, completed, or failed
- the solar layer shows its internal steps while other checks may already be running
- the output moves into the battery layer and later layers
- the subsidy crawler checks database, internet, PDFs, and Supabase
- monitoring events show retries, fallback decisions, source latency, and partial results
- each layer resolves to accepted, rejected, skipped, or error
- the final recommendation is assembled from the layer outputs
- **each completed product layer turns its 3D module clickable, with its own data bubble**

## Experience Principle

The user should understand that Heimwende is doing real work, not displaying a fake loading spinner.

The UI should make these facts visible:

- sources are being checked, not guessed
- several workers can run at the same time
- each worker has a clear job
- the system monitors progress and failures
- external services can be slow, missing, or partial
- failures do not always kill the run; some layers can continue with fallbacks
- the final proposal is the result of many small verified decisions
- **every euro and spec in a component bubble traces back to a field in the `Recommendation` payload**

Avoid generic status text like `Analyzing...` when a specific status is available. Prefer concrete text:

- `Google Solar · Fetching roof polygon`
- `Engine · Calculating usable south-facing area`
- `Supabase · Checking subsidy catalog`
- `PDF · Reading eligibility rules`
- `Monitor · Google Solar response took 1.8s`
- `Fallback · Continuing without confirmed subsidy amount`

## Frontend Surfaces

The connected experience needs four synchronized surfaces, all consuming the **same run event stream
and the same final `Recommendation`**:

1. `ActivityFeed` (`features/activity/ActivityFeed.tsx`)
   - Text timeline of backend events.
   - Shows current source, action, status, timestamp, and details.
   - Shows parallel work clearly, for example multiple running rows grouped by layer.

2. Remotion / pipeline animation
   - Visualizes the pipeline moving from parent layer to child layers.
   - Shows tokens/data packets flowing from one layer to the next.
   - Highlights the currently active layer and step.
   - Shows multiple active nodes at once when backend work is parallel.

3. 3D model + component bubbles (`features/viewer/`)
   - The house assembles as layers complete; each module reflects `computing → ready → rejected/skipped`.
   - Clicking a ready module zooms the camera in and opens its data bubble.

4. Result/proposal UI
   - Uses completed layer outputs.
   - Shows accepted/rejected/error states for solar, battery, heat pump, EV charger, subsidy, permit, and financing.

---

## Pipeline Model

The backend should emit one `run` with nested layers.

```ts
type LayerId =
  | "parent"
  | "solar"
  | "battery"
  | "heat_pump"
  | "ev_charger"
  | "subsidy"
  | "permit"
  | "financing";

type LayerStatus =
  | "queued"
  | "running"
  | "accepted"
  | "rejected"
  | "skipped"
  | "error";

type StepStatus =
  | "queued"
  | "running"
  | "ok"
  | "warn"
  | "error";
```

## Event Contract

The backend should stream events over SSE first. WebSocket can come later if bidirectional control is needed.

Endpoint:

```txt
GET /api/v1/advisor/runs/:runId/events
```

Initial run request:

```txt
POST /api/v1/advisor/recommend
```

Response should include:

```ts
interface StartRecommendationResponse {
  runId: string;
}
```

Each streamed event:

```ts
interface PipelineEvent {
  id: string;
  runId: string;
  timestamp: string;
  layerId: LayerId;
  parentLayerId?: LayerId;
  stepId?: string;
  workerId?: string;
  type:
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
  status: LayerStatus | StepStatus;
  title: string;
  detail?: string;
  source?: "database" | "internet" | "pdf" | "google_solar" | "supabase" | "engine" | "crawler";
  payload?: Record<string, unknown>;
}
```

Frontend mapping:

- `layerId` drives which Remotion node is highlighted **and which 3D module changes run-state**.
- `stepId` drives which internal layer step is highlighted.
- `workerId` identifies parallel work inside the same layer.
- `title` and `detail` drive the activity row.
- `source` drives the activity icon.
- `status` drives the visual state.
- `payload` carries structured data for layer-specific UI (and seeds the component bubble).

## Deliberate Pacing (honest, not fake)

It is fine — and desirable — to pace the run so each step is legible instead of flashing past. Two
acceptable ways:

- **Real pacing:** the backend already does slow I/O (Google Solar, Tavily, Supabase). Stream events
  as they actually happen — much of the latency is genuine.
- **Demo throttle (toggleable):** a `DEMO_PACING` flag that inserts a small `await asyncio.sleep(...)`
  between layer/step emissions (e.g. 300–800 ms), plus a min-display time per step on the frontend so
  nothing flashes. Keep it **off** for real runs, **on** for the demo. Every paced step still maps to
  a real backend action — never a fake spinner.

## Parallel Work and Monitoring

The backend should emit enough events for the frontend to show concurrency honestly.

Examples of parallel work:

- parent checks cached data while starting online lookups
- solar starts Google Solar data fetch while tariff/subsidy metadata is loaded
- subsidy checks Supabase while internet search gathers updated sources
- permit and subsidy can run alongside financing pre-checks once product candidates exist
- heat pump and EV charger checks can run independently from the solar-to-battery path

The frontend should show this as multiple active workers, not as one fake sequential progress bar.

```ts
interface WorkerState {
  id: string;
  layerId: LayerId;
  label: string;
  source: PipelineEvent["source"];
  status: "queued" | "running" | "ok" | "warn" | "error";
  startedAt?: string;
  lastHeartbeatAt?: string;
  completedAt?: string;
  detail?: string;
}
```

Monitoring events should be first-class UI events.

Use monitoring for:

- external API latency
- crawler retry attempts
- missing source data
- fallback decisions
- dependency waits
- partial result warnings
- source confidence changes

Example monitor events:

```json
{
  "type": "worker_heartbeat",
  "layerId": "solar",
  "workerId": "google_solar",
  "status": "running",
  "title": "Google Solar still running",
  "detail": "Waiting for roof geometry response.",
  "source": "google_solar",
  "payload": {
    "elapsedMs": 1800
  }
}
```

```json
{
  "type": "dependency_waiting",
  "layerId": "battery",
  "parentLayerId": "solar",
  "status": "queued",
  "title": "Battery waiting for solar output",
  "detail": "Storage sizing starts after PV potential is known.",
  "source": "engine"
}
```

```json
{
  "type": "fallback_used",
  "layerId": "subsidy",
  "stepId": "pdf_read",
  "status": "warn",
  "title": "Fallback used",
  "detail": "PDF source timed out. Continuing with cached Supabase catalog.",
  "source": "pdf",
  "payload": {
    "fallback": "supabase_catalog",
    "continuable": true
  }
}
```

UI requirements:

- show a small `Running in parallel` indicator when more than one worker is active
- show worker count, for example `4 active checks`
- show queued dependencies explicitly, not as silence
- show monitoring notices in the feed with a distinct icon
- show fallback events as warnings, not hard errors
- keep completed worker rows visible long enough for the user to understand progress

## Parent Layer

The parent layer is the orchestrator. It should show what the system is checking before or while delegating to specific layers.

Parent layer steps:

```ts
const parentSteps = [
  { id: "database_lookup", label: "Looking in database", source: "database" },
  { id: "internet_search", label: "Searching the internet", source: "internet" },
  { id: "pdf_read", label: "Reading PDF documents", source: "pdf" },
  { id: "route_layers", label: "Routing data to product layers", source: "engine" },
];
```

Expected UI:

- parent node pulses while active
- current sub-step is visible in the feed
- when parent sends data to a child layer, Remotion animates a packet from `parent` to that layer
- if parent fails to gather required context, the run enters `run_error`

Example events:

```json
{
  "type": "step_started",
  "layerId": "parent",
  "stepId": "database_lookup",
  "status": "running",
  "title": "Looking in database",
  "detail": "Checking cached tariff, subsidy, permit, and site data.",
  "source": "database"
}
```

```json
{
  "type": "step_completed",
  "layerId": "parent",
  "stepId": "pdf_read",
  "status": "ok",
  "title": "PDF read complete",
  "detail": "Found subsidy rules for the household postcode.",
  "source": "pdf"
}
```

## Solar Layer

The solar layer should make the behind-the-scenes roof analysis visible.

Solar layer steps:

```ts
const solarSteps = [
  { id: "google_solar_crawl", label: "Crawling Google Solar", source: "google_solar" },
  { id: "roof_geometry", label: "Calculating roof angle, area, and usable surface", source: "engine" },
  { id: "orientation", label: "Determining roof orientation", source: "engine" },
  { id: "yield_estimate", label: "Estimating yearly PV yield", source: "engine" },
  { id: "solar_decision", label: "Deciding if solar is accepted", source: "engine" },
];
```

Important solar payload fields (these also seed the solar component bubble):

```ts
interface SolarPayload {
  roofAreaM2?: number;
  usableAreaM2?: number;
  pitchDeg?: number;
  azimuthDeg?: number;
  orientation?: "south" | "south_east" | "south_west" | "east" | "west" | "north" | "unknown";
  potentialKwp?: number;
  yearlyYieldKwh?: number;
  accepted?: boolean;
  rejectionReason?: string;
}
```

Accepted example:

```json
{
  "type": "layer_completed",
  "layerId": "solar",
  "parentLayerId": "parent",
  "status": "accepted",
  "title": "Solar accepted",
  "detail": "South-facing roof with 8.6 kWp potential.",
  "payload": { "orientation": "south", "potentialKwp": 8.6, "usableAreaM2": 42, "accepted": true }
}
```

Rejected example:

```json
{
  "type": "layer_completed",
  "layerId": "solar",
  "parentLayerId": "parent",
  "status": "rejected",
  "title": "Solar rejected",
  "detail": "Usable roof surface is below the minimum threshold.",
  "payload": { "usableAreaM2": 8, "accepted": false, "rejectionReason": "Roof area too small" }
}
```

Error example:

```json
{
  "type": "layer_error",
  "layerId": "solar",
  "parentLayerId": "parent",
  "status": "error",
  "title": "Google Solar lookup failed",
  "detail": "No roof data returned for the address.",
  "source": "google_solar"
}
```

## Battery Layer

The battery layer should start only after solar output exists, unless the user already has PV data.

Input: solar potential, expected PV yield, household electricity demand, self-consumption estimate.

Battery steps:

```ts
const batterySteps = [
  { id: "receive_solar_output", label: "Receiving solar output", source: "engine" },
  { id: "load_profile", label: "Building household load profile", source: "engine" },
  { id: "battery_size", label: "Calculating battery size", source: "engine" },
  { id: "battery_decision", label: "Deciding if storage is accepted", source: "engine" },
];
```

UI behavior:

- Remotion animates output from `solar` to `battery`.
- Battery node stays queued until solar is accepted or skipped with existing PV data.
- If solar is rejected and no existing PV exists, battery should become `skipped`.

## Subsidy Crawler Layer

The subsidy layer should make crawler work explicit: cached data, internet sources, PDFs, and Supabase.

Subsidy steps:

```ts
const subsidySteps = [
  { id: "supabase_lookup", label: "Checking Supabase subsidy catalog", source: "supabase" },
  { id: "internet_search", label: "Searching subsidy sources online", source: "internet" },
  { id: "pdf_read", label: "Reading subsidy PDF", source: "pdf" },
  { id: "eligibility_rules", label: "Evaluating household eligibility", source: "engine" },
  { id: "subsidy_decision", label: "Calculating accepted subsidy amount", source: "engine" },
];
```

Important subsidy payload fields:

```ts
interface SubsidyPayload {
  catalogHit?: boolean;
  sourceUrl?: string;
  pdfTitle?: string;
  programName?: string;
  eligible?: boolean;
  amountEur?: number;
  rejectionReason?: string;
}
```

UI behavior:

- show `Supabase` as a distinct destination/source
- show PDF read as its own event, not hidden inside the crawler
- show accepted subsidy amount when eligibility succeeds
- show rejected state with reason when not eligible
- show warning state if source data is partial but the run can continue

## Other Layers

Future layers should follow the same model:

```ts
interface LayerDefinition {
  id: LayerId;
  label: string;
  dependsOn: LayerId[];
  steps: { id: string; label: string; source: PipelineEvent["source"] }[];
}
```

Expected dependencies:

```ts
const layerDependencies = {
  parent: [],
  solar: ["parent"],
  battery: ["solar"],
  heat_pump: ["parent"],
  ev_charger: ["parent"],
  subsidy: ["solar", "battery", "heat_pump", "ev_charger"],
  permit: ["solar", "heat_pump", "ev_charger"],
  financing: ["solar", "battery", "heat_pump", "ev_charger", "subsidy"],
};
```

## Status Rules

Use the same state language everywhere.

```ts
const statusPresentation = {
  queued: "Muted node, no spinner",
  running: "Active node, spinner, animated packet",
  accepted: "Green check",
  rejected: "Amber or red rejected badge with reason",
  skipped: "Muted skipped badge",
  error: "Red error state with retry/support detail",
};
```

Rules:

- `running` means backend work is actively happening.
- `accepted` means this layer contributes to the final proposal (and its 3D module becomes clickable).
- `rejected` means the layer ran successfully but should not be offered.
- `skipped` means the layer did not run because a dependency rejected it or input was missing.
- `error` means the layer failed unexpectedly or an external source failed.

## Frontend Store Shape

The frontend should convert the event stream into a run state.

```ts
interface PipelineRunState {
  runId: string;
  status: "idle" | "running" | "completed" | "error";
  activeLayerIds: LayerId[];
  activeWorkerIds: string[];
  layers: Record<LayerId, LayerState>;
  workers: Record<string, WorkerState>;
  monitorNotices: PipelineEvent[];
  events: PipelineEvent[];
  result?: Recommendation;
}

interface LayerState {
  id: LayerId;
  status: LayerStatus;
  startedAt?: string;
  completedAt?: string;
  activeStepIds: string[];
  workerIds: string[];
  steps: Record<string, StepState>;
  output?: Record<string, unknown>;
  error?: string;
}

interface StepState {
  id: string;
  status: StepStatus;
  title: string;
  detail?: string;
  source?: PipelineEvent["source"];
  output?: Record<string, unknown>;
}
```

## Remotion Animation Mapping

The Remotion scene should be a deterministic visualization of `PipelineRunState`.

Scene objects: parent layer node, child layer nodes, animated packet between nodes, active worker
lanes inside each layer, active step labels, source icons (database, internet, PDF, Google Solar,
Supabase, engine), status badges, monitor strip showing active checks/warnings/retries/fallbacks.

Animation rules:

- `layer_started`: highlight layer node and fade in step list
- `worker_started`: create an active worker lane in the layer
- `worker_heartbeat`: keep the worker lane alive and update elapsed/monitor detail
- `worker_completed`: resolve the worker lane to ok/warn/error
- `step_started`: pulse current step row
- `step_completed`: check the step row
- `dependency_waiting`: show a queued edge between dependent layers
- `dependency_resolved`: animate data packet into the unblocked layer
- `monitor_notice`: add a short-lived notice to the monitor strip
- `fallback_used`: mark the relevant branch with a warning but keep the run moving
- `layer_completed`: move packet from layer to dependent layers
- `layer_error`: shake or flash the layer node once, then hold red error state
- `run_completed`: all nodes settle, final proposal card appears

The animation should not invent state. It renders only what the backend event stream says happened.

Parallel animation requirements: multiple nodes highlighted at once; multiple packet animations at
once; queued nodes visibly waiting on dependency edges; completed branches remain visible as evidence;
monitor notices feel operational, not decorative.

## Activity Feed Mapping

Current `ActivityFeed` can be extended from flat events to pipeline events.

```ts
function toActivityEvent(event: PipelineEvent): ActivityEvent {
  return {
    id: event.id,
    timestamp: formatTime(event.timestamp),
    source: event.source ? sourceLabel(event.source) : layerLabel(event.layerId),
    label: event.workerId
      ? `${workerLabel(event.workerId)} · ${event.detail ?? event.title}`
      : event.detail ?? event.title,
    status:
      event.status === "error" || event.type === "fallback_used"
        ? "warn"
        : event.status === "running"
          ? "loading"
          : event.status === "accepted" || event.status === "ok"
            ? "ok"
            : "info",
  };
}
```

The feed should always show the backend source in the row detail or icon, for example:
`Database · Checking cached tariff data`, `Google Solar · Crawling roof potential`,
`Engine · Calculating pitch, area, and orientation`, `PDF · Reading subsidy eligibility`,
`Supabase · Persisting subsidy match`, `Monitor · 4 active checks running`,
`Fallback · Continuing with cached catalog`.

Feed grouping: newest events stay visible at a consistent end; active workers grouped by layer when
several run; monitoring notices quieter than layer decisions; accepted/rejected/error decisions
stronger than heartbeats; if more than one worker is active, show `4 checks running in parallel`.

## Error Handling

Errors must stay visible and explain what failed: show the failed layer, the failed step, the source
if available, whether the run can continue, the fallback if used, and the final result as partial if
some layers succeeded.

Example partial run:

```json
{
  "type": "layer_error",
  "layerId": "subsidy",
  "status": "error",
  "title": "Subsidy crawler failed",
  "detail": "PDF source timed out. Continuing without confirmed subsidy.",
  "source": "pdf",
  "payload": { "continuable": true, "fallback": "No subsidy applied" }
}
```

---

# Zoom-In — Clickable 3D Component Bubbles

Once the run completes (or as each module turns ready), the user can click a component on the 3D house
— heat pump, solar array, battery, EV charger. The camera zooms to it, and a small white bubble fades
in next to it showing the *real per-component numbers the engine computed*: monthly saving, capex,
subsidy applied, and one or two physical specs. No generic marketing text — every value traces to the
`Recommendation` payload.

## What already exists (don't rebuild it)

| Piece | Where | State |
|---|---|---|
| 3D house + roof | `features/viewer/HouseCanvas.tsx`, `roofGeometry.ts` | ✅ live |
| Per-component meshes | `features/viewer/houseModules.tsx` → `HouseModule`, `MODULE_KINDS = ["pv","battery","heat_pump","ev"]` | ✅ live, placed at `moduleSlots` |
| Add-on toggles | `addons: Record<ModuleKind, boolean>` in `HouseCanvas` | ✅ live |
| Camera + 3D helpers | `@react-three/drei` (`OrbitControls`, `ContactShadows`, `Html`) | ✅ installed |
| Live status feed | `features/activity/ActivityFeed.tsx` (`ActivityEvent[]`) | ✅ live |
| Recommend call | `features/intake/IntakeScreen.tsx` → `runRecommend()` → `postRecommend()` | ✅ live (DEV uses `fixture: "demo-detached"`) |
| The numbers | backend `Recommendation` (`alternatives[]`, `breakdown`, `capex`) | ✅ computed |

The clickable objects, the camera, the bubble primitive (drei `<Html>`), and the data call **all
already exist**. Missing pieces: (a) per-component data on the contract, (b) click→zoom→bubble
interaction, (c) binding module run-state to the live run above.

> **Naming bridge:** the 3D layer uses `ModuleKind = "pv" | "battery" | "heat_pump" | "ev"`. The
> backend uses `solar / battery / heat_pump / ev_charger`. Define one mapping table and use it
> everywhere (see below).

## The data the bubble needs — current vs. missing

Today each `ScenarioResult` (`apps/backend/src/app/domain/models.py`) carries:

- `breakdown` — 3 buckets: `electricity_eur_month`, `heating_eur_month`, `mobility_eur_month`.
- `capex` — **bundle** total: `gross_eur`, `subsidy_eur`, `after_subsidy_eur`, `subsidy_note`.
- `installment_eur_month`, `monthly_saving_eur`, `confidence`.

Mapping that onto components:

| Component | Monthly saving today | Capex today | Physical specs today |
|---|---|---|---|
| **Heat pump** | ✅ `breakdown.heating_eur_month` | 🔶 bundle only (named in `subsidy_note`) | ❌ kW / SCOP / litres displaced — computed, dropped |
| **EV charger** | ✅ `breakdown.mobility_eur_month` | 🔶 bundle only | ❌ home-vs-public split — dropped |
| **Solar** | ⚠️ shares `electricity_eur_month` w/ battery | 🔶 bundle only | ❌ kWp / kWh-yr / self-consumption / panels — computed in `solar_layer`, dropped |
| **Battery** | ⚠️ shares `electricity_eur_month` w/ solar | 🔶 bundle only | ❌ kWh / brand / arbitrage value — dropped |

Heat pump and EV bubbles can ship today (each has its own saving). Solar and battery share one
electricity bucket, and the juiciest content — "8.2 kWp producing 7,800 kWh/yr covering 62% of your
use" — exists only inside the layers. That's the contract gap to close.

## Backend change — surface a `components[]` array

A **frozen-contract change (F02)**: update `specs/api/openapi.yaml`, the Pydantic model in
`domain/models.py`, **and** the frontend `src/lib/types.ts` in the same commit. No engine *math*
changes — we only stop throwing away what the layers already compute.

```yaml
# specs/api/openapi.yaml  (illustrative)
ComponentBreakdown:
  type: object
  required: [type, label, included, saving_eur_month, capex_eur, subsidy_eur]
  properties:
    type:    { type: string, enum: [solar, battery, heat_pump, ev_charger] }
    label:   { type: string, example: "♨️ Heat pump" }
    included:        { type: boolean }
    saving_eur_month:{ type: number, example: 55 }
    capex_eur:       { type: number, example: 22000 }
    subsidy_eur:     { type: number, example: 11000 }
    subsidy_note:    { type: string, example: "50% KfW 458" }
    specs: { type: object, additionalProperties: true }   # per-component, drives bubble detail rows
```

```py
# domain/models.py
class ComponentBreakdown(BaseModel):
    type: Literal["solar", "battery", "heat_pump", "ev_charger"]
    label: str
    included: bool
    saving_eur_month: float
    capex_eur: float
    subsidy_eur: float
    subsidy_note: str = ""
    specs: dict[str, float | str | bool] = {}

class ScenarioResult(BaseModel):
    ...
    components: list[ComponentBreakdown] = []   # NEW
```

Populate it where the layers already produce the data (`domain/savings/scenarios.py` / `engine.py`):

- `solar` → `solar_layer` pipeline: `{ kwp, annual_kwh, self_consumption_pct, panels, brand }`
- `battery` → `electricity_layer.battery_arbitrage_value` + sizing: `{ kwh, brand, arbitrage_eur_month }`
  (and **split** the electricity bucket: solar self-consumption vs. battery arbitrage)
- `heat_pump` → `heatpump_layer`: `{ sizing_kw, scop, fuel_displaced, litres_year }`
- `ev_charger` → `ev_layer`: `{ home_charge_pct, public_price_eur_kwh }`

Per-component `capex_eur` from `PricingContext` (`pv_per_kwp_eur × kwp`, `battery_per_kwh_eur × kwh`,
`heatpump_fixed_eur`, `wallbox_fixed_eur`); per-component `subsidy_eur` from the subsidy layer.

Decisions to lock before coding:
1. **Solar vs. battery split** of the electricity bucket (preferred — lets both bubbles show a
   distinct number) or show the combined number on both.
2. **Spec whitelist per component** — which 1–3 specs are interesting enough for the bubble.

## Tie the live run to the 3D model

This is what connects the two halves. A `layer_completed` event flips its 3D module from **"computing"**
(dim / pulsing) to **"ready"** (solid, glowing, clickable) — the house assembles from verified backend
work, then the user clicks in. `rejected`/`skipped` modules render muted and non-interactive.

```ts
type ModuleRunState = LayerStatus; // reuse the LayerStatus above
```

## Frontend implementation

### One mapping table
```ts
// features/viewer/componentMap.ts
import type { ModuleKind } from "@/features/viewer/roofGeometry";
import type { ComponentBreakdown } from "@/lib/types";

export const KIND_TO_TYPE: Record<ModuleKind, ComponentBreakdown["type"]> = {
  pv: "solar",
  battery: "battery",
  heat_pump: "heat_pump",
  ev: "ev_charger",
};
```

### Make each module clickable + selectable
`HouseModule` already renders the mesh at a `ModuleSlot`. Add pointer handlers and a `selected:
ModuleKind | null` state lifted into `HouseCanvas`:

```tsx
<group
  onPointerOver={(e) => { e.stopPropagation(); setHover(kind); document.body.style.cursor = "pointer"; }}
  onPointerOut={() => { setHover(null); document.body.style.cursor = "auto"; }}
  onClick={(e) => { e.stopPropagation(); onSelect(kind); }}
>
  {/* existing module mesh; add an emissive ring / outline when selected or runState === "ready" */}
</group>
```

### Zoom the camera to the slot
Lerp the camera toward an offset from the selected slot each frame (no new deps — plain R3F `useFrame`):

```tsx
useFrame((state) => {
  const target = selected ? moduleSlots[selected].position : DEFAULT_TARGET;
  const camGoal = selected
    ? new THREE.Vector3().copy(target).add(ZOOM_OFFSET[selected])
    : DEFAULT_CAM;
  state.camera.position.lerp(camGoal, 0.08);
  controlsRef.current?.target.lerp(target, 0.08);
  controlsRef.current?.update();
});
```
Clicking empty space (`onPointerMissed` on `<Canvas>`) clears `selected` and flies back out.

### The white bubble
Use drei `<Html>` anchored to the slot so it tracks the component in 3D:

```tsx
import { Html } from "@react-three/drei";

{selected && data && (
  <Html position={moduleSlots[selected].position} center distanceFactor={8} occlude>
    <ComponentBubble data={data} />   {/* data = components.find(c => c.type === KIND_TO_TYPE[selected]) */}
  </Html>
)}
```

`ComponentBubble` is a small white rounded card (match `ActivityFeed` tokens: `bg-white`, `--border`,
`--text-1/2/3`): a title row, the big `+€{saving}/mo`, then 2–3 spec rows and a capex/subsidy line.
Optional: a one-line, number-grounded LLM caption per component (generated from these fields — never
new numbers).

### Wire the data in
`IntakeScreen` already holds the `Recommendation` from `runRecommend()`. Pass
`recommendation.best.components` (or the configurator-selected scenario's `components`) into
`HouseCanvas`; look up the selected component by `KIND_TO_TYPE[selected]`. If `included === false`,
render that module dimmed and show a "not in this package — +€X/mo if added" bubble (ties into the
existing upsell).

## Data shapes (frontend)

```ts
// mirrors backend ComponentBreakdown (src/lib/types.ts, F02)
export interface ComponentBreakdown {
  type: "solar" | "battery" | "heat_pump" | "ev_charger";
  label: string;
  included: boolean;
  saving_eur_month: number;
  capex_eur: number;
  subsidy_eur: number;
  subsidy_note: string;
  specs: Record<string, number | string | boolean>;
}

// what each bubble renders, per type
const BUBBLE_SPECS: Record<ComponentBreakdown["type"], string[]> = {
  solar:      ["kwp", "annual_kwh", "self_consumption_pct"],
  battery:    ["kwh", "arbitrage_eur_month"],
  heat_pump:  ["sizing_kw", "scop", "fuel_displaced"],
  ev_charger: ["home_charge_pct"],
};
```

Example `components[]` for the demo household (full-bundle scenario):

```json
[
  { "type": "solar", "label": "☀️ Solar", "included": true, "saving_eur_month": 48,
    "capex_eur": 11890, "subsidy_eur": 0, "subsidy_note": "0% VAT",
    "specs": { "kwp": 8.2, "annual_kwh": 7800, "self_consumption_pct": 62, "panels": 20 } },
  { "type": "battery", "label": "🔋 Battery", "included": true, "saving_eur_month": 13,
    "capex_eur": 5600, "subsidy_eur": 0, "subsidy_note": "0% VAT",
    "specs": { "kwh": 8, "brand": "BYD", "arbitrage_eur_month": 13 } },
  { "type": "heat_pump", "label": "♨️ Heat pump", "included": true, "saving_eur_month": 55,
    "capex_eur": 22000, "subsidy_eur": 11000, "subsidy_note": "50% KfW 458",
    "specs": { "sizing_kw": 9, "scop": 4.2, "fuel_displaced": "oil", "litres_year": 1900 } },
  { "type": "ev_charger", "label": "🚗 EV charger", "included": true, "saving_eur_month": 26,
    "capex_eur": 1200, "subsidy_eur": 0, "subsidy_note": "",
    "specs": { "home_charge_pct": 80 } }
]
```

---

## Implementation Order

1. Backend returns `runId` from `POST /api/v1/advisor/recommend`.
2. Backend exposes SSE endpoint for `PipelineEvent`; add the `DEMO_PACING` throttle flag.
3. Frontend adds `usePipelineRun(runId)` to connect to SSE and store events in `PipelineRunState`.
4. Frontend derives active workers, active layers, dependency waits, and monitor notices.
5. `ActivityFeed` renders mapped pipeline events and parallel worker groups.
6. Remotion scene renders the same `PipelineRunState`.
7. **Backend contract** — add `ComponentBreakdown` to `openapi.yaml` + `models.py` + `types.ts` (one commit).
8. **Backend populate** — fill `components[]` in `scenarios.py`/`engine.py` from existing layer outputs; split the electricity bucket solar↔battery.
9. **Module run-state** — drive each 3D module's `computing → ready/rejected/skipped` from layer events.
10. **Selection + camera** — clickable `HouseModule`, `selected` state, `useFrame` zoom, `onPointerMissed` reset.
11. **Bubble** — `ComponentBubble` via drei `<Html>`, bound to `components.find(...)`, styled like the feed.
12. **Upsell tie-in** — dimmed module + "+€X/mo if added" bubble when `included === false`.
13. *(stretch)* per-component LLM caption, generated from the bubble's own fields.

## Acceptance Criteria

- Starting a recommendation immediately creates a visible live run.
- The user can see that background work is real, specific, and source-based.
- Parallel checks are visible when multiple backend workers are active.
- The UI shows active, queued, blocked, completed, warning, and failed work.
- Monitoring events show latency, retries, fallbacks, and partial results.
- Parent layer shows database, internet, and PDF checks.
- Solar layer shows Google crawl, roof geometry, angle/area, orientation, and decision.
- Solar accepted/rejected/error states are visible and explain why.
- Battery layer receives solar output visually and in state.
- Subsidy layer shows Supabase, internet, and PDF activity.
- As each layer completes, its 3D module visibly turns from "computing" to "ready/clickable".
- Clicking a ready component zooms the camera to it and opens a white bubble; clicking empty space flies back out.
- Each bubble shows that component's **own** monthly saving, capex, subsidy, and 1–3 real specs.
- Solar and battery show **distinct** savings numbers (electricity bucket is split).
- Components not in the selected package render dimmed with an upsell bubble.
- No number in any bubble (or feed) exists that isn't in the payload (same guarantee as `assert_numbers_grounded`).
- Activity feed, Remotion animation, module run-states, and bubbles never disagree — one source of truth: the run + `Recommendation`.
