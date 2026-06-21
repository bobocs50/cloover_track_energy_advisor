// Live activity feed — a clean, icon-free stream of backend events. Status is
// carried by a coloured slash marker + colour, never glyphs or emoji. Rows pop in
// with a snappy spring (framer-motion) and the list auto-scrolls to the newest.
import { useEffect, useRef } from "react";
import { motion } from "framer-motion";

export type ActivityStatus = "ok" | "warn" | "info" | "loading";

export interface ActivityEvent {
  id: string;
  /** Pre-formatted clock label, e.g. "14:32". */
  timestamp: string;
  /** Bold lead-in (the "agent" / layer name). */
  source: string;
  /** Body line. */
  label: string;
  status: ActivityStatus;
}

export interface ActivityFeedProps {
  events: ActivityEvent[];
}

export default function ActivityFeed({ events }: ActivityFeedProps) {
  const bodyRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the newest event as the feed streams in.
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  return (
    <aside className="agent-feed">
      <header className="agent-feed-head">
        <div>
          <p className="agent-feed-kicker">live activity</p>
          <h2 className="agent-feed-title">agent feed</h2>
        </div>
        <span className="agent-feed-count">
          {events.length} {events.length === 1 ? "event" : "events"}
        </span>
      </header>

      <div className="agent-feed-body" ref={bodyRef}>
        {events.length === 0 ? (
          <p className="agent-feed-empty">/ waiting for checks…</p>
        ) : (
          <ul className="agent-feed-list">
            {events.map((e) => (
              <motion.li
                key={e.id}
                className="feed-row"
                data-status={e.status}
                initial={{ opacity: 0, x: -12, scale: 0.97 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                transition={{ type: "spring", stiffness: 540, damping: 30, mass: 0.6 }}
              >
                <span className="feed-mark" aria-hidden>
                  /
                </span>
                <div className="feed-body">
                  <div className="feed-row-top">
                    <p className="feed-source">{e.source}</p>
                    <span className="feed-time">{e.timestamp}</span>
                  </div>
                  <p className="feed-label">{e.label}</p>
                </div>
              </motion.li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
