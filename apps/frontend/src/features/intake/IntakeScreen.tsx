// Intake screen. Step flow:
//   intake → zooming → roof-draw → roof-params → viewing (3D model + feed)
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { motion } from "framer-motion";
import type { Map as MapboxMap } from "mapbox-gl";
import GlobeBackground, { type GlobeHandle } from "@/components/globe-background";
import StepBar from "@/components/StepBar";
import IntakeForm from "@/features/intake/IntakeForm";
import RoofDrawStep from "@/features/roof/RoofDrawStep";
import RoofParamsStep, { type RoofParams } from "@/features/roof/RoofParamsStep";
import HouseCanvas from "@/features/viewer/HouseCanvas";
import type { ModuleKind } from "@/features/viewer/roofGeometry";
import RunTimeline from "@/features/activity/RunTimeline";
import {
  activeWorkerCount,
  applyEvent,
  initialRunState,
  simulateRecommendStream,
  toActivityEvent,
  type ActivityEvent,
  type LayerId,
  type PipelineEvent,
  type PipelineRunState,
} from "@/features/activity/pipeline";
import OfferResultPage from "@/features/offer/OfferResultPage";
import { demoOfferRecommendation } from "@/features/offer/demoOfferRecommendation";
import type { LatLng } from "@/features/roof/useMapboxDraw";
import { postRecommendStream } from "@/lib/api";
import type { Household, Recommendation, Tier } from "@/lib/types";

// Tier selector entries, ordered low → middle → high (matches Recommendation.tiers).
const TIER_BUTTONS: { id: Tier["id"]; label: string }[] = [
  { id: "low", label: "Starter" },
  { id: "middle", label: "Value" },
  { id: "high", label: "Future-proof" },
];

// The emotional framing for each tier — the "how it feels" the data alone can't
// convey. The hard numbers + bundle copy come live from the selected Tier; this
// only adds the customer-feeling headline and an accent color per rank.
const TIER_INSIGHTS: Record<Tier["id"], { feeling: string; accent: string }> = {
  low: {
    feeling: "Dip a toe in — the lightest commitment, with room to grow later.",
    accent: "#0284c7",
  },
  middle: {
    feeling: "The comfortable middle — where most homeowners feel it's worth it.",
    accent: "#2f6fed",
  },
  high: {
    feeling: "All-in and future-proof — saving from day one, nothing left to add.",
    accent: "#08744a",
  },
};

// Strip the bundle emoji prefix (☀️🔋♨️🚗) from a Tier label for clean display.
function stripBundleEmoji(value: string) {
  return value.replace(/[☀️🔋♨️🚗]/gu, "").trim();
}

// Tidy LLM/demo prose for inline display: drop markdown bold and normalise the
// "EUR" the backend emits into a real € sign.
function cleanTierCopy(value: string) {
  return value
    .replace(/\*\*/g, "")
    .replace(/EUR\s?/g, "€")
    .replace(/\s+/g, " ")
    .trim();
}

const NO_ADDONS: Record<ModuleKind, boolean> = {
  pv: false,
  battery: false,
  heat_pump: false,
  ev: false,
};

// Default: show the full bundle so the live model lands fully kitted.
const ALL_ADDONS: Record<ModuleKind, boolean> = {
  pv: true,
  battery: true,
  heat_pump: true,
  ev: true,
};

// Fallback household so the live pipeline always has a valid body to stream,
// even if the intake form didn't produce a parsed Household.
const DEMO_HOUSEHOLD: Household = {
  address: { street: "Invalidenstraße", house_no: "116", city: "Berlin" },
  plz: "10115",
  floor_area_m2: 140,
  building_year: 1985,
  occupants: 3,
  electricity_eur_month: 95,
  heating: { fuel: "OIL", eur_month: 180 },
  mobility: { kind: "PETROL", km_month: 1233 },
};

// Cumulative savings-ladder order — mirrors Recommendation.alternatives[].
const ADDON_LADDER: ModuleKind[] = ["pv", "battery", "heat_pump", "ev"];

// Map a tier to the modules it implies. A tier points at a scenario in the
// cumulative ladder, so selecting tier == alternatives[n] enables rungs 0..n.
function addonsForTier(rec: Recommendation, tierId: Tier["id"]): Record<ModuleKind, boolean> {
  const tier = rec.tiers.find((t) => t.id === tierId);
  if (!tier) return ALL_ADDONS;
  let idx = rec.alternatives.findIndex((a) => a.scenario_id === tier.scenario_id);
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
  layerId: LayerId = "parent",
): ActivityEvent {
  return { id: `ev-${eventSeq++}`, timestamp: clock(), source, label, status, layerId };
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
  const [runState, setRunState] = useState<PipelineRunState>(initialRunState());
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recStatus, setRecStatus] = useState<RecStatus>("idle");
  const [showOfferPage, setShowOfferPage] = useState(false);
  // The live 3D model shows the modules implied by the selected tier. Default to
  // the high tier (full bundle) so the model lands fully kitted.
  const [selectedTier, setSelectedTier] = useState<Tier["id"]>("high");
  const selectedTierRef = useRef<Tier["id"]>("high");
  const [addons, setAddons] = useState<Record<ModuleKind, boolean>>(ALL_ADDONS);

  // Live-event pacing. Real backend events arrive in bursts — the solar worker and
  // 12 permit checks land almost together over the SSE. We buffer them and release
  // one at a time on a fast, slightly-randomized cadence so the feed *pops* in a
  // lively "lots is happening" order instead of dumping a block. This only controls
  // reveal *timing* — every event and every number is the real backend's.
  const eventQueueRef = useRef<PipelineEvent[]>([]);
  const drainTimerRef = useRef<number | null>(null);
  const applyEventRef = useRef<(ev: PipelineEvent) => void>(() => {});

  // Cleanup any pending drain timer on unmount.
  useEffect(
    () => () => {
      if (drainTimerRef.current !== null) window.clearTimeout(drainTimerRef.current);
    },
    [],
  );

  const selectTier = (id: Tier["id"]) => {
    selectedTierRef.current = id;
    setSelectedTier(id);
    setAddons(addonsForTier(recommendation ?? demoOfferRecommendation, id));
  };

  // The Tier object backing the selected button — live recommendation when it has
  // arrived, otherwise the demo fallback so the panel always has content to show.
  const activeTier = (recommendation ?? demoOfferRecommendation).tiers.find(
    (t) => t.id === selectedTier,
  );

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

  // The reducer: fold one event into the feed + run state. Kept in a ref so the
  // stable drain loop below always invokes the latest closure.
  applyEventRef.current = (ev: PipelineEvent) => {
    setRunState((prev) => applyEvent(prev, ev));
    setEvents((prev) => [...prev, toActivityEvent(ev)]);
    if (ev.type === "run_completed") {
      const rec = ev.payload?.recommendation as Recommendation | undefined;
      if (rec) {
        setRecommendation(rec);
        setRecStatus("ready");
        // Re-sync the model to the selected tier — the backend's tier→bundle
        // mapping may differ from the demo fallback.
        setAddons(addonsForTier(rec, selectedTierRef.current));
      }
    } else if (ev.type === "run_error") {
      setRecStatus("error");
    }
  };

  // Release one buffered event, then schedule the next on a slightly-jittered
  // delay (~98–210ms) so reveals feel alive rather than mechanical — paced so the
  // stream stays readable before the run completes.
  const drainQueue = () => {
    const next = eventQueueRef.current.shift();
    if (!next) {
      drainTimerRef.current = null;
      return;
    }
    applyEventRef.current(next);
    const delay = 98 + Math.floor(Math.random() * 112);
    drainTimerRef.current = window.setTimeout(drainQueue, delay);
  };

  // Stream sink: buffer the event and make sure the drain loop is running.
  const enqueuePipelineEvent = (ev: PipelineEvent) => {
    eventQueueRef.current.push(ev);
    if (drainTimerRef.current === null) {
      drainTimerRef.current = window.setTimeout(drainQueue, 0);
    }
  };

  const resetEventQueue = () => {
    eventQueueRef.current = [];
    if (drainTimerRef.current !== null) {
      window.clearTimeout(drainTimerRef.current);
      drainTimerRef.current = null;
    }
  };

  // Kick off the recommendation as a live SSE run and stream progress into the feed.
  // Falls back to a simulated stream (golden fixture) if the backend is unreachable,
  // so the live UI still works without a running backend.
  const runRecommend = (h: Household, p: RoofParams) => {
    setRecStatus("loading");
    setRunState(initialRunState());
    resetEventQueue();
    setEvents([
      makeEvent("Location", `${h.address.street} ${h.address.house_no}, ${h.plz}`, "ok"),
      makeEvent("Roof model", `${ROOF_LABEL[p.roofType]} · ${p.pitchDeg}° pitch`, "ok"),
    ]);
    postRecommendStream(h, enqueuePipelineEvent).catch(() => {
      setEvents((prev) => [
        ...prev,
        makeEvent("Monitor", "Backend unreachable — replaying demo run", "warn"),
      ]);
      void simulateRecommendStream(demoOfferRecommendation, enqueuePipelineEvent);
    });
  };

  const handleParamsNext = (p: RoofParams) => {
    setParams(p);
    setStep("viewing");
    // Always run the live pipeline. If the form didn't yield a parsed Household
    // (e.g. a blank required field), fall back to the demo household so the live
    // activity still streams rather than dead-ending on an error.
    runRecommend(household ?? DEMO_HOUSEHOLD, p);
  };

  if (import.meta.env.DEV) {
    (window as unknown as { __goViewing?: () => void }).__goViewing = () =>
      handleParamsNext({ roofType: "gable", pitchDeg: 30, wallHeightM: 6 });
  }

  const formHidden = step !== "intake";

  if (showOfferPage) {
    return (
      <OfferResultPage
        rec={recommendation ?? demoOfferRecommendation}
        onBack={() => setShowOfferPage(false)}
        events={events}
        run={runState}
      />
    );
  }

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
          <motion.div
            className="viewer-stage"
            initial={{ opacity: 0, scale: 0.985 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="viewer-stage-header">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-3)]">
                Live model
              </p>
              <h2 className="mt-0.5 text-[17px] font-bold tracking-[-0.01em] text-[var(--text-1)]">
                {ROOF_LABEL[params.roofType]}
                {params.roofType !== "flat" ? ` · ${params.pitchDeg}°` : ""}
              </h2>
              {runState.status === "running" && activeWorkerCount(runState) > 1 && (
                <span className="mt-1 block animate-pulse text-[12px] font-semibold text-[#b45309]">
                  / {activeWorkerCount(runState)} checks running in parallel
                </span>
              )}
            </div>

            <HouseCanvas polygon={polygon} params={params} addons={addons} />

            <div className="viewer-tier-bar" role="group" aria-label="Offer tier">
              {TIER_BUTTONS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => selectTier(id)}
                  className={`viewer-tier-btn${selectedTier === id ? " viewer-tier-btn--on" : ""}`}
                  style={
                    selectedTier === id
                      ? ({ "--tier-accent": TIER_INSIGHTS[id].accent } as CSSProperties)
                      : undefined
                  }
                  aria-pressed={selectedTier === id}
                >
                  {label}
                </button>
              ))}
            </div>

            {activeTier && <TierInsight tier={activeTier} />}
          </motion.div>
          <motion.div
            className="viewer-feed"
            initial={{ opacity: 0, x: 44 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 30, mass: 0.7 }}
          >
            <RunTimeline
              state={runState}
              events={events}
              status={recStatus}
              recommendation={recommendation}
              onOpenOffer={() => setShowOfferPage(true)}
            />
          </motion.div>
        </div>
      )}
    </main>
  );
}

// Floating panel under the tier bar that explains the selected offer — the
// customer-feeling headline plus the two figures that matter (net today, after
// payoff) and the live rationale. Re-keyed on tier id so it re-animates on switch.
function TierInsight({ tier }: { tier: Tier }) {
  const insight = TIER_INSIGHTS[tier.id];
  const net = Math.round(tier.monthly_saving_eur);
  const after = Math.round(tier.saving_after_payoff_eur);

  return (
    <motion.div
      key={tier.id}
      className="viewer-tier-panel"
      style={{ "--tier-accent": insight.accent } as CSSProperties}
      initial={{ opacity: 0, y: 6, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
    >
      <div className="viewer-tier-panel-main">
        <p className="viewer-tier-panel-name">{tier.name}</p>
        <h3 className="viewer-tier-panel-title">{stripBundleEmoji(tier.label)}</h3>
        <p className="viewer-tier-panel-feeling">{insight.feeling}</p>
        <p className="viewer-tier-panel-rationale">{cleanTierCopy(tier.rationale_md)}</p>
      </div>

      <div className="viewer-tier-panel-stats">
        <div className="viewer-tier-stat">
          <span className="viewer-tier-stat-label">Net today</span>
          <span
            className="viewer-tier-stat-value"
            data-tone={net >= 0 ? "pos" : "neg"}
          >
            {net >= 0 ? "+" : "−"}€{Math.abs(net)}/mo
          </span>
        </div>
        <div className="viewer-tier-stat">
          <span className="viewer-tier-stat-label">After payoff</span>
          <span className="viewer-tier-stat-value" data-tone="pos">
            +€{after}/mo
          </span>
        </div>
      </div>
    </motion.div>
  );
}
