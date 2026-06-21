// Unified run timeline — the redesigned right-side panel. One cohesive vertical
// timeline replaces the old PipelineGraph + ActivityFeed. Eight ordered pipeline
// stages run down a connected spine; the active stage expands to stream its live
// events, finished stages collapse to a one-line result, and the whole panel
// settles into a calm "Complete · €X/mo" checklist.
//
// Visual language is aligned with the app shell (Geist sans, Title/Sentence case)
// and the top StepBar: a hollow ring = queued, a filled accent dot = running, a
// green check-circle = done. No lowercase transforms, no slash glyph markers.
import { useEffect, useRef } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check, X } from "lucide-react";
import {
  activeWorkerCount,
  groupEventsByStage,
  stageProgress,
  type ActivityEvent,
  type PipelineRunState,
  type SolarDetail,
  type StageGroup,
  type StageKind,
  type SubsidyGrant,
} from "@/features/activity/pipeline";
import type { Recommendation } from "@/lib/types";

/** Mirrors IntakeScreen's RecStatus — the run's user-facing lifecycle. */
type RecStatus = "idle" | "loading" | "ready" | "error";

const RESOLVED: ReadonlySet<StageKind> = new Set(["ok", "warn", "err"]);

function StageIndicator({ kind }: { kind: StageKind }) {
  return (
    <span className="rt-indicator" data-kind={kind} aria-hidden>
      {kind === "ok" || kind === "warn" ? (
        <Check size={11} strokeWidth={3} />
      ) : kind === "err" ? (
        <X size={11} strokeWidth={3} />
      ) : kind === "running" ? (
        <span className="rt-indicator-dot" />
      ) : null}
    </span>
  );
}

const SOURCE_TYPE_LABEL: Record<string, string> = {
  live_internet: "Live",
  supabase_cache: "Cache",
  seeded_fallback: "Fallback",
  static_rule: "Rule",
};

function EventRow({ event }: { event: ActivityEvent }) {
  return (
    <motion.li
      className="rt-event"
      data-status={event.status}
      layout
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ type: "spring", stiffness: 520, damping: 34, mass: 0.6 }}
    >
      <span className="rt-event-source">{event.source}</span>
      <span className="rt-event-label">{event.label}</span>
      {event.sourceType && SOURCE_TYPE_LABEL[event.sourceType] && (
        <span className="rt-event-chip" data-source={event.sourceType}>
          {SOURCE_TYPE_LABEL[event.sourceType]}
        </span>
      )}
      <time className="rt-event-time">{event.timestamp}</time>
      {event.reason && <span className="rt-event-reason">{event.reason}</span>}
    </motion.li>
  );
}

/** A to-scale roof cross-section with the sun's incidence angle — the visual
 *  payoff of Google Solar measuring the real pitch + orientation. */
function SolarDiagram({ tiltDeg }: { tiltDeg: number }) {
  const rad = (Math.min(Math.max(tiltDeg, 5), 60) * Math.PI) / 180;
  const bx = 50;
  const by = 92;
  const L = 84;
  const ex = bx + L * Math.cos(rad);
  const ey = by - L * Math.sin(rad);
  // Angle arc between the ground and the roof line, radius r around the eave.
  const r = 26;
  const gx = bx + r;
  const sx = bx + r * Math.cos(rad);
  const sy = by - r * Math.sin(rad);
  // Three parallel sun rays striking the slope (sun is up and to the right).
  const sun = { x: 196, y: 22 };
  const rays = [0.28, 0.52, 0.76].map((t) => ({
    x: bx + (ex - bx) * t,
    y: by + (ey - by) * t,
  }));
  return (
    <svg className="rt-solar-svg" viewBox="0 0 224 110" role="img" aria-label={`Roof pitched at ${tiltDeg} degrees facing the sun`}>
      {/* sun + corona */}
      <circle cx={sun.x} cy={sun.y} r="9" className="rt-solar-sun" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => {
        const a = (deg * Math.PI) / 180;
        return (
          <line
            key={deg}
            x1={sun.x + 12 * Math.cos(a)}
            y1={sun.y + 12 * Math.sin(a)}
            x2={sun.x + 16 * Math.cos(a)}
            y2={sun.y + 16 * Math.sin(a)}
            className="rt-solar-sun-ray"
          />
        );
      })}
      {/* incident rays onto the panel surface */}
      {rays.map((p, i) => (
        <line key={i} x1={p.x - 34} y1={p.y - 46} x2={p.x} y2={p.y} className="rt-solar-ray" />
      ))}
      {/* house body */}
      <line x1={bx} y1={by} x2={ex + 8} y2={by} className="rt-solar-ground" />
      <line x1={bx} y1={by} x2={bx} y2={by - 26} className="rt-solar-wall" />
      <line x1={ex} y1={ey} x2={ex} y2={by} className="rt-solar-wall" />
      {/* the PV roof surface */}
      <line x1={bx} y1={by} x2={ex} y2={ey} className="rt-solar-roof" />
      {/* tilt angle arc + label */}
      <path d={`M ${gx} ${by} A ${r} ${r} 0 0 0 ${sx} ${sy}`} className="rt-solar-arc" />
      <text x={bx + 30} y={by - 7} className="rt-solar-arc-label">
        {tiltDeg}°
      </text>
    </svg>
  );
}

const fmt = (n: number) => n.toLocaleString("de-DE");

/** Rich Google-Solar detail: the angle/sun diagram + the measured roof model. */
function SolarCard({ detail }: { detail: SolarDetail }) {
  const metrics: Array<[string, string]> = [
    ["Orientation", `${detail.orientation} · ${detail.orientationLabel}`],
    ["Roof pitch", `${detail.tiltDeg}°`],
    ["Usable area", `${fmt(detail.usableM2)} m²`],
    ["Panels", `${detail.panels}`],
    ["Capacity", `${detail.kwp} kWp`],
    ["Site yield", `${fmt(detail.yieldPerKwp)} kWh/kWp`],
    ["Sun exposure", `${fmt(detail.sunHoursPerYear)} h/yr`],
    ["Generation", `~${fmt(detail.annualKwh)} kWh/yr`],
  ];
  return (
    <motion.div
      className="rt-solar"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
    >
      <SolarDiagram tiltDeg={detail.tiltDeg} />
      <dl className="rt-solar-grid">
        {metrics.map(([k, v]) => (
          <div className="rt-solar-cell" key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      {detail.shadeLossPct > 0 && (
        <p className="rt-solar-note">
          Shading loss {detail.shadeLossPct}% already subtracted from the modelled yield.
        </p>
      )}
    </motion.div>
  );
}

/** Resolved subsidy lines (Tavily + Supabase) with their combined cash value. */
function SubsidyCard({
  grants,
  totalEur,
}: {
  grants: SubsidyGrant[];
  totalEur: number;
}) {
  return (
    <motion.div
      className="rt-subsidy"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
    >
      <ul className="rt-grants">
        {grants.map((g) => (
          <li className="rt-grant" key={g.code}>
            <span className="rt-grant-code">{g.code}</span>
            <span className="rt-grant-name">{g.name}</span>
            <span className="rt-grant-value">
              {g.amountEur != null ? `€${fmt(Math.round(g.amountEur))}` : g.rateLabel}
            </span>
            {g.amountEur != null && g.rateLabel && (
              <span className="rt-grant-rate">{g.rateLabel}</span>
            )}
            <span className="rt-grant-src" data-live={g.source === "Tavily live" || undefined}>
              {g.source}
            </span>
          </li>
        ))}
      </ul>
      {totalEur > 0 && (
        <p className="rt-grant-total">
          <span>Cash grants applied</span>
          <strong>−€{fmt(Math.round(totalEur))}</strong>
        </p>
      )}
    </motion.div>
  );
}

function StageRow({
  stage,
  isLast,
  reduce,
}: {
  stage: StageGroup;
  isLast: boolean;
  reduce: boolean;
}) {
  const resolved = RESOLVED.has(stage.kind);
  // The permit stage shows its nested category tree as soon as checks arrive and
  // keeps it visible once resolved — the depth is the point. Other stages stream
  // their events only while running and then collapse to a one-line summary.
  const hasTree = !!stage.categories?.length;
  // Google Solar and Subsidies keep a rich detail card visible (running + resolved)
  // instead of collapsing to one line — the measured roof and the grants are the point.
  const hasSolar = stage.id === "solar" && !!stage.solar;
  const hasSubsidy = stage.id === "subsidy" && !!stage.subsidies;
  const hasCard = hasSolar || hasSubsidy;
  const showEvents = !hasTree && stage.kind === "running" && stage.events.length > 0;
  const showTree = hasTree && (stage.kind === "running" || resolved);
  const statusText =
    stage.kind === "running" ? "Running" : stage.kind === "idle" ? "Queued" : null;

  return (
    <motion.li
      className="rt-stage"
      data-kind={stage.kind}
      data-branch={stage.branch || undefined}
      variants={{
        hidden: { opacity: 0, x: reduce ? 0 : -8 },
        show: { opacity: 1, x: 0 },
      }}
      transition={{ type: "spring", stiffness: 460, damping: 30, mass: 0.6 }}
    >
      <div className="rt-spine">
        <StageIndicator kind={stage.kind} />
        {!isLast && <span className="rt-connector" />}
      </div>

      <div className="rt-stage-body">
        <div className="rt-stage-head">
          <span className="rt-stage-label">{stage.label}</span>
          {statusText && <span className="rt-stage-status">{statusText}</span>}
        </div>

        <AnimatePresence initial={false} mode="popLayout">
          {showEvents && (
            <motion.ul
              key="events"
              className="rt-events"
              initial={reduce ? false : { opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, height: 0 }}
              transition={{ duration: 0.26, ease: [0.32, 0.72, 0, 1] }}
            >
              {stage.events.map((e) => (
                <EventRow key={e.id} event={e} />
              ))}
            </motion.ul>
          )}
        </AnimatePresence>

        {showTree && (
          <div className="rt-tree">
            {stage.categories!.map((cat) => (
              <div className="rt-category" key={cat.name}>
                <p className="rt-category-label">{cat.name}</p>
                <ul className="rt-events">
                  {cat.events.map((e) => (
                    <EventRow key={e.id} event={e} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {hasSolar && <SolarCard detail={stage.solar!} />}
        {hasSubsidy && (
          <SubsidyCard
            grants={stage.subsidies!.grants}
            totalEur={stage.subsidies!.totalEur}
          />
        )}

        {resolved && !hasTree && !hasCard && stage.summary && (
          <p className="rt-stage-summary">{stage.summary}</p>
        )}
        {resolved && !hasTree && !hasCard && stage.summaryDetail && (
          <p className="rt-stage-effect">
            {stage.summaryDetail}
            {stage.summarySourceType && SOURCE_TYPE_LABEL[stage.summarySourceType] && (
              <span
                className="rt-event-chip"
                data-source={stage.summarySourceType}
                style={{ marginLeft: 6, verticalAlign: "middle" }}
              >
                {SOURCE_TYPE_LABEL[stage.summarySourceType]}
              </span>
            )}
          </p>
        )}
      </div>
    </motion.li>
  );
}

export interface RunTimelineProps {
  state: PipelineRunState;
  events: ActivityEvent[];
  status: RecStatus;
  recommendation: Recommendation | null;
  onOpenOffer: () => void;
}

export default function RunTimeline({
  state,
  events,
  status,
  recommendation,
  onOpenOffer,
}: RunTimelineProps) {
  const reduce = useReducedMotion() ?? false;
  const scrollRef = useRef<HTMLDivElement>(null);

  const groups = groupEventsByStage(events, state);
  const pct = stageProgress(groups);
  const parallel = activeWorkerCount(state);
  const done = state.status === "completed";
  const saving = state.result?.best.monthly_saving_eur;
  const afterPayoff = state.result?.best.saving_after_payoff_eur ?? null;

  // Footer status text mirrors the old StatusPill, now docked in the panel.
  const footEur =
    recommendation != null ? Math.round(recommendation.best.monthly_saving_eur) : null;
  const footAfter =
    recommendation != null
      ? Math.round(recommendation.best.saving_after_payoff_eur)
      : null;
  const footText =
    status === "ready"
      ? footEur != null
        ? footEur >= 1
          ? `Save €${footEur} a month from day one!`
          : footAfter != null
            ? `Near cost-neutral today → +€${footAfter}/mo once paid off`
            : "Near cost-neutral today"
        : "Recommendation ready"
      : status === "error"
        ? "Recommendation failed"
        : "Computing…";

  // Follow the newest activity as it streams in.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [events.length, done]);

  return (
    <section className="run-timeline" aria-label="Recommendation pipeline">
      <header className="rt-head" data-done={done || undefined}>
        <AnimatePresence mode="wait" initial={false}>
          {done ? (
            <motion.div
              key="done"
              className="rt-head-done"
              initial={reduce ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: "spring", stiffness: 420, damping: 32 }}
            >
              <span className="rt-head-badge">
                <Check size={13} strokeWidth={3} />
              </span>
              <div className="rt-head-text">
                <p className="rt-kicker">Analysis complete</p>
                {saving != null ? (
                  Math.round(saving) >= 1 ? (
                    <>
                      <p className="rt-headline">
                        <span className="rt-headline-lead">Save </span>
                        <span className="rt-headline-num">€{Math.round(saving)}</span>
                        <span className="rt-headline-unit">a month today!</span>
                      </p>
                      <p className="rt-subline">
                        lower energy &amp; financing bills from day one of your full upgrade
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="rt-headline">
                        <span className="rt-headline-lead">Near </span>
                        <span className="rt-headline-num">cost-neutral</span>
                        <span className="rt-headline-unit">today</span>
                      </p>
                      <p className="rt-subline">
                        the upgrade roughly pays for itself now
                        {afterPayoff != null && Math.round(afterPayoff) >= 1
                          ? `, then saves €${Math.round(afterPayoff)}/mo once it's paid off`
                          : ""}
                      </p>
                    </>
                  )
                ) : (
                  <p className="rt-headline">All checks passed</p>
                )}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="running"
              className="rt-head-running"
              initial={false}
              exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6 }}
            >
              <p className="rt-kicker">Live pipeline</p>
              <span className={`rt-meta${parallel > 1 ? " rt-meta--live" : ""}`}>
                {parallel > 1 ? `${parallel} running in parallel` : `${pct}%`}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="rt-track" aria-hidden>
          <motion.span
            className="rt-track-fill"
            data-done={done || undefined}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.52, ease: [0.23, 1, 0.32, 1] }}
          />
        </div>
      </header>

      <div className="rt-scroll" ref={scrollRef}>
        <motion.ol
          className="rt-stages"
          initial="hidden"
          animate="show"
          variants={{ hidden: {}, show: { transition: { staggerChildren: reduce ? 0 : 0.05 } } }}
        >
          {groups.map((stage, i) => (
            <StageRow
              key={stage.id}
              stage={stage}
              isLast={i === groups.length - 1}
              reduce={reduce}
            />
          ))}
        </motion.ol>
      </div>

      {status !== "idle" && (
        <footer className="rt-foot" data-status={status}>
          <button type="button" className="rt-cta" onClick={onOpenOffer}>
            Go to Recommendation
          </button>
          <span className="rt-foot-status">
            <span className="rt-foot-dot" aria-hidden />
            <motion.span
              key={footText}
              className="rt-foot-text"
              initial={reduce ? false : { opacity: 0, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: [0.23, 1, 0.32, 1] }}
            >
              {footText}
            </motion.span>
          </span>
        </footer>
      )}
    </section>
  );
}
