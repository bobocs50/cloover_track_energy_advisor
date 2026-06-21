"""Live-run pipeline event contract (SSE transport).

Owner: backend
Feature: live activity stream (frontend ↔ backend connection)

This is the wire model for `POST /api/v1/advisor/recommend/stream`. It mirrors the
`PipelineEvent` shape documented in `apps/frontend/data/connection.md` so the frontend
`ActivityFeed` + pipeline graph can consume it directly.

Transport concern only — lives in `api/`, not `domain/`. Fields serialize to **camelCase**
(`layerId`, `parentLayerId`, …) to match the frontend contract; build events with snake_case
Python names and dump with `by_alias=True` (the `sse()` helper does this).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

# ── Vocabularies (subset of connection.md) ─────────────────────────────────────
LayerId = Literal[
    "parent",
    "solar",
    "battery",
    "heat_pump",
    "ev_charger",
    "subsidy",
    "permit",
    "financing",
]

Status = Literal[
    # LayerStatus
    "queued",
    "running",
    "accepted",
    "rejected",
    "skipped",
    "error",
    # StepStatus
    "ok",
    "warn",
]

EventType = Literal[
    "run_started",
    "layer_started",
    "worker_started",
    "worker_heartbeat",
    "worker_completed",
    "step_started",
    "step_progress",
    "step_completed",
    "dependency_waiting",
    "dependency_resolved",
    "monitor_notice",
    "fallback_used",
    "layer_completed",
    "layer_error",
    "run_completed",
    "run_error",
]

Source = Literal[
    "database",
    "internet",
    "pdf",
    "google_solar",
    "supabase",
    "engine",
    "crawler",
    "llm",
]


class PipelineEvent(BaseModel):
    """One streamed event. Serializes to camelCase JSON for the SSE `data:` line."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    run_id: str
    timestamp: str
    layer_id: LayerId
    type: EventType
    status: Status
    title: str
    parent_layer_id: LayerId | None = None
    step_id: str | None = None
    worker_id: str | None = None
    detail: str | None = None
    source: Source | None = None
    payload: dict[str, Any] | None = None


class EventBuilder:
    """Stamps monotonic ids + UTC timestamps for one run, so call sites stay terse."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._seq = 0

    def make(
        self,
        type: EventType,
        layer_id: LayerId,
        status: Status,
        title: str,
        **kw: Any,
    ) -> PipelineEvent:
        self._seq += 1
        return PipelineEvent(
            id=f"{self.run_id}-{self._seq}",
            run_id=self.run_id,
            timestamp=datetime.now(UTC).isoformat(),
            layer_id=layer_id,
            type=type,
            status=status,
            title=title,
            **kw,
        )


def sse(event: PipelineEvent) -> str:
    """Serialize an event to an SSE `data:` frame (camelCase JSON)."""
    body = json.dumps(event.model_dump(by_alias=True, exclude_none=True))
    return f"data: {body}\n\n"
