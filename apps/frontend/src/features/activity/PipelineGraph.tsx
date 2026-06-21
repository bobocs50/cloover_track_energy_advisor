// Live pipeline mini-graph — a clean, icon-free DAG driven by PipelineRunState.
// Each stage is marked with a slash; status is carried by colour + motion, not icons.
// Pure presentation: renders only what the event stream reports.
import { motion } from "framer-motion";
import { activeWorkerCount, type LayerId, type PipelineRunState, type RunStatus } from "./pipeline";

interface Node {
  id: LayerId;
  label: string;
  branch?: boolean;
}

// Order mirrors the backend orchestration; solar + permit are the parallel branch.
const NODES: Node[] = [
  { id: "parent", label: "orchestrator" },
  { id: "solar", label: "google solar", branch: true },
  { id: "permit", label: "permits", branch: true },
  { id: "subsidy", label: "subsidy" },
  { id: "battery", label: "battery" },
  { id: "heat_pump", label: "heat pump" },
  { id: "ev_charger", label: "ev charger" },
  { id: "financing", label: "proposal" },
];

type Kind = "idle" | "running" | "ok" | "warn" | "err";

function kindOf(status: RunStatus | undefined): Kind {
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

const STATUS_TEXT: Record<Kind, string> = {
  idle: "queued",
  running: "running",
  ok: "done",
  warn: "review",
  err: "blocked",
};

const RESOLVED: ReadonlySet<Kind> = new Set(["ok", "warn", "err"]);

export default function PipelineGraph({ state }: { state: PipelineRunState }) {
  const kinds = NODES.map((n) => kindOf(state.layers[n.id]));
  const resolved = kinds.filter((k) => RESOLVED.has(k)).length;
  const pct = Math.round((resolved / NODES.length) * 100);
  const running = activeWorkerCount(state);
  const done = state.status === "completed";

  return (
    <div className="pipeline-graph">
      <div className="pl-head">
        <span className="pl-title">pipeline</span>
        <span className={`pl-meta${running > 1 ? " pl-meta--live" : ""}`}>
          {running > 1 ? `${running} in parallel` : done ? "complete" : `${pct}%`}
        </span>
      </div>

      <div className="pl-rail-wrap">
        <span className="pl-rail" aria-hidden>
          <span className="pl-rail-fill" style={{ height: `${pct}%` }} />
        </span>

        <motion.ol
          className="pl-nodes"
          initial="hidden"
          animate="show"
          variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
        >
          {NODES.map((n, i) => {
            const k = kinds[i];
            return (
              <motion.li
                key={n.id}
                className={`pl-node${n.branch ? " pl-node--branch" : ""}`}
                data-kind={k}
                variants={{
                  hidden: { opacity: 0, x: -10 },
                  show: { opacity: 1, x: 0 },
                }}
                transition={{ type: "spring", stiffness: 500, damping: 28, mass: 0.6 }}
              >
                <span className="pl-mark" aria-hidden>
                  /
                </span>
                <span className="pl-label">{n.label}</span>
                <span className="pl-status">{STATUS_TEXT[k]}</span>
              </motion.li>
            );
          })}
        </motion.ol>
      </div>
    </div>
  );
}
