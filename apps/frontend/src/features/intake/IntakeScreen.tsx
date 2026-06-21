// Intake screen. Step flow:
//   intake → zooming → roof-draw → roof-params → viewing (3D model + feed)
import { useRef, useState } from "react";
import type { Map as MapboxMap } from "mapbox-gl";
import GlobeBackground, { type GlobeHandle } from "@/components/globe-background";
import StepBar from "@/components/StepBar";
import IntakeForm from "@/features/intake/IntakeForm";
import RoofDrawStep from "@/features/roof/RoofDrawStep";
import RoofParamsStep, { type RoofParams } from "@/features/roof/RoofParamsStep";
import HouseCanvas from "@/features/viewer/HouseCanvas";
import type { ModuleKind } from "@/features/viewer/roofGeometry";
import ActivityFeed, { type ActivityEvent } from "@/features/activity/ActivityFeed";
import type { LatLng } from "@/features/roof/useMapboxDraw";
import { postRecommend } from "@/lib/api";
import type { Household, Recommendation } from "@/lib/types";

// Toggle bar entries, in savings-ladder order (3d_modules.md).
const MODULE_TOGGLES: { kind: ModuleKind; emoji: string; label: string }[] = [
  { kind: "pv", emoji: "☀️", label: "Solar" },
  { kind: "battery", emoji: "🔋", label: "Battery" },
  { kind: "heat_pump", emoji: "♨️", label: "Heat pump" },
  { kind: "ev", emoji: "🚗", label: "EV charger" },
];

const NO_ADDONS: Record<ModuleKind, boolean> = {
  pv: false,
  battery: false,
  heat_pump: false,
  ev: false,
};

// Cumulative savings-ladder order — mirrors Recommendation.alternatives[].
const ADDON_LADDER: ModuleKind[] = ["pv", "battery", "heat_pump", "ev"];

// Map the recommended scenario to the modules it implies. The ladder is
// cumulative, so best === alternatives[n] means rungs 0..n are enabled.
function seedFromRecommendation(rec: Recommendation): Record<ModuleKind, boolean> {
  let idx = rec.alternatives.findIndex((a) => a.scenario_id === rec.best.scenario_id);
  if (idx < 0) {
    // Fallback: match by saving value if scenario_id doesn't line up.
    idx = rec.alternatives.findIndex(
      (a) => a.monthly_saving_eur === rec.best.monthly_saving_eur,
    );
  }
  if (idx < 0) idx = rec.alternatives.length - 1; // default: full ladder
  const next = { ...NO_ADDONS };
  for (let i = 0; i <= idx && i < ADDON_LADDER.length; i++) next[ADDON_LADDER[i]] = true;
  return next;
}

export interface IntakeScreenProps {
  onComplete?: (household: Household) => void;
}

type Step = "intake" | "zooming" | "roof-draw" | "roof-params" | "viewing";

// Maps each step to the StepBar index (0 = Address, 1 = Roof, 2 = Parameters, 3 = Model).
const STEP_INDEX: Record<Step, number> = {
  intake: 0,
  zooming: 0,
  "roof-draw": 1,
  "roof-params": 2,
  viewing: 3,
};

// Short clock label for activity rows. Stable & dependency-free.
function clock(): string {
  return new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

let eventSeq = 0;
function makeEvent(
  source: string,
  label: string,
  status: ActivityEvent["status"],
): ActivityEvent {
  return { id: `ev-${eventSeq++}`, timestamp: clock(), source, label, status };
}

const ROOF_LABEL: Record<RoofParams["roofType"], string> = {
  flat: "Flat roof",
  gable: "Gable roof",
  hip: "Hip roof",
  shed: "Shed roof",
};

type RecStatus = "idle" | "loading" | "ready" | "error";

export default function IntakeScreen({ onComplete }: IntakeScreenProps) {
  const globeRef = useRef<GlobeHandle>(null);
  const [step, setStep] = useState<Step>("intake");
  const [roofMap, setRoofMap] = useState<MapboxMap | null>(null);
  const [polygon, setPolygon] = useState<LatLng[] | null>(null);
  const [household, setHousehold] = useState<Household | null>(null);
  const [params, setParams] = useState<RoofParams | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recStatus, setRecStatus] = useState<RecStatus>("idle");
  // Toy module toggles — always interactive; auto-seeded once from the
  // recommendation, but only if the user hasn't already touched them.
  const [addons, setAddons] = useState<Record<ModuleKind, boolean>>(NO_ADDONS);
  const userTouchedAddons = useRef(false);

  const toggleAddon = (kind: ModuleKind) => {
    userTouchedAddons.current = true;
    setAddons((prev) => ({ ...prev, [kind]: !prev[kind] }));
  };

  const handleHousehold = (h: Household) => {
    setHousehold(h);
    onComplete?.(h);
  };

  const handleAddressPick = (lat: number, lon: number) => {
    if (import.meta.env.DEV) {
      (window as unknown as { __pick?: unknown }).__pick = { lat, lon };
    }
    globeRef.current?.flyTo(lat, lon);
    setStep("zooming");
  };

  const handleZoomComplete = () => {
    setRoofMap(globeRef.current?.getMap() ?? null);
    setStep("roof-draw");
  };

  const handleDrawNext = (poly: LatLng[]) => {
    setPolygon(poly);
    setStep("roof-params");
  };

  const handleDrawSkip = () => {
    setPolygon(null);
    setStep("roof-params");
  };

  // Kick off the recommendation request and stream progress into the feed (4C).
  const runRecommend = (h: Household, p: RoofParams) => {
    setRecStatus("loading");
    setEvents([
      makeEvent("Location", `${h.address.street} ${h.address.house_no}, ${h.plz}`, "ok"),
      makeEvent("Roof model", `${ROOF_LABEL[p.roofType]} · ${p.pitchDeg}° pitch`, "ok"),
      makeEvent("Solar layer", "Computing roof yield…", "loading"),
    ]);
    // In DEV, use a golden fixture so we don't need a running backend.
    const opts = import.meta.env.DEV ? { fixture: "demo-detached" } : undefined;
    postRecommend(h, opts)
      .then((rec) => {
        setRecommendation(rec);
        setRecStatus("ready");
        // Seed the toggles to match the recommended rung — once, and only if the
        // user hasn't manually toggled anything yet.
        if (!userTouchedAddons.current) setAddons(seedFromRecommendation(rec));
        const eur = Math.round(rec.best.monthly_saving_eur);
        setEvents((prev) => [
          ...prev.map((e) => (e.status === "loading" ? { ...e, status: "ok" as const } : e)),
          makeEvent("Recommendation", `€${eur}/month potential savings`, "ok"),
        ]);
      })
      .catch(() => {
        setRecStatus("error");
        setEvents((prev) => [
          ...prev.map((e) => (e.status === "loading" ? { ...e, status: "warn" as const } : e)),
          makeEvent("Error", "Recommendation failed — backend offline?", "warn"),
        ]);
      });
  };

  const handleParamsNext = (p: RoofParams) => {
    setParams(p);
    setStep("viewing");
    if (household) {
      runRecommend(household, p);
    } else {
      // Defensive: household should be set from the intake form. Surface the gap
      // in the feed rather than firing /recommend with no body.
      setRecStatus("error");
      setEvents([makeEvent("Error", "Household data missing — please restart", "warn")]);
    }
  };

  const formHidden = step !== "intake";

  return (
    <main className="intake-screen">
      <GlobeBackground ref={globeRef} onZoomComplete={handleZoomComplete} />
      <StepBar currentStep={STEP_INDEX[step]} />

      <div className={`intake-form-col${formHidden ? " intake-form-col--revealed" : ""}`}>
        <IntakeForm onComplete={handleHousehold} onAddressPick={handleAddressPick} />
      </div>

      {step === "roof-draw" && (
        <RoofDrawStep
          map={roofMap}
          onBack={() => setStep("intake")}
          onNext={handleDrawNext}
          onSkip={handleDrawSkip}
        />
      )}

      {step === "roof-params" && (
        <RoofParamsStep onBack={() => setStep("roof-draw")} onNext={handleParamsNext} />
      )}

      {step === "viewing" && params && (
        <div className="viewer-split">
          <div className="viewer-stage">
            <div className="viewer-stage-header">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-3)]">
                Live model
              </p>
              <h2 className="mt-0.5 text-[17px] font-bold tracking-[-0.01em] text-[var(--text-1)]">
                {ROOF_LABEL[params.roofType]}
                {params.roofType !== "flat" ? ` · ${params.pitchDeg}°` : ""}
              </h2>
            </div>

            <HouseCanvas polygon={polygon} params={params} addons={addons} />

            <div className="viewer-module-bar">
              {MODULE_TOGGLES.map(({ kind, emoji, label }) => (
                <button
                  key={kind}
                  type="button"
                  onClick={() => toggleAddon(kind)}
                  className={`viewer-module-chip${addons[kind] ? " viewer-module-chip--on" : ""}`}
                  aria-pressed={addons[kind]}
                >
                  <span aria-hidden>{emoji}</span>
                  {label}
                </button>
              ))}
            </div>

            <StatusPill status={recStatus} recommendation={recommendation} />
          </div>
          <div className="viewer-feed">
            <ActivityFeed events={events} />
          </div>
        </div>
      )}
    </main>
  );
}

// Bottom-left status chip over the 3D stage (mirrors Pactum's status pill).
function StatusPill({
  status,
  recommendation,
}: {
  status: RecStatus;
  recommendation: Recommendation | null;
}) {
  if (status === "idle") return null;

  const eur =
    recommendation != null ? Math.round(recommendation.best.monthly_saving_eur) : null;

  const config: Record<Exclude<RecStatus, "idle">, { dot: string; text: string }> = {
    loading: { dot: "bg-[#d97706]", text: "Computing recommendation…" },
    ready: {
      dot: "bg-[#059669]",
      text: eur != null ? `€${eur}/month possible` : "Recommendation ready",
    },
    error: { dot: "bg-[#dc2626]", text: "Recommendation failed" },
  };
  const c = config[status];

  return (
    <div className="viewer-status-pill">
      <span
        className={`h-2 w-2 rounded-full ${c.dot} ${status === "loading" ? "animate-pulse" : ""}`}
      />
      <span className="text-[13px] font-medium text-[var(--text-1)]">{c.text}</span>
    </div>
  );
}
