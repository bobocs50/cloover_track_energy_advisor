# Spec-Based Development Process — Heimwende (Cloover track)

> **Why this exists:** 3 people, ~20 hours (Sat 18:00 → Sun 14:00 — ~15 build hours + a sleep shift,
> last 3 h reserved for the video + submission), one shared codebase, a hard deadline of
> **Sun 2026-06-21 14:00**. Spec-first + contract-first is not bureaucracy here — it is what lets
> Lukas, Philips and Zhou work **in parallel without blocking each other** and lets us trust the
> number on demo day. Keep specs short; keep the contract frozen; keep `main` green.

---

## 1. The loop (per feature)

```
  ┌── SPEC ──┐    ┌── BRANCH ──┐   ┌── BUILD (TDD) ──┐   ┌── REVIEW ──┐   ┌── MERGE ──┐
  │ fill the │ →  │ feat/Fxx-* │ → │ red → green →    │ → │ Lukas + AC │ → │ squash to │
  │ template │    │ off main   │   │ refactor; ACs=   │   │ checklist  │   │ main, green│
  │ → Ready  │    │            │   │ the tests        │   │            │   │            │
  └──────────┘    └────────────┘   └─────────────────┘   └────────────┘   └────────────┘
```

A feature is a file in [`specs/`](./specs/) created from [`_TEMPLATE.spec.md`](./_TEMPLATE.spec.md).
The acceptance criteria (§6 of the spec) **are** the test cases — write them before the code.

## 2. Spec lifecycle (the `status` field)

| Status | Meaning | Gate to advance |
|--------|---------|-----------------|
| **Draft** | exists, not yet agreed | author fills §1–§9 |
| **Ready** (DoR) | safe to start; nothing will block it mid-flight | spec reviewed; deps merged or mockable; contract impact known |
| **In-Progress** | branch open, building | — |
| **In-Review** | PR open | tests green, self-review done |
| **Done** (DoD) | merged to `main` | DoD checklist (spec §10) all ticked |

**Definition of Ready (DoR)** — before you open a branch:
1. Spec §1–§6 filled; acceptance criteria are concrete and testable.
2. `depends_on` features are **merged** *or* you have a **mock** (a fixture from the frozen contract).
3. `contract_impact` is known; if `extends`, the contract change is agreed with the contract owner (Zhou).

**Definition of Done (DoD)** — the spec §10 checklist. The short version: **ACs pass as tests · lint+types clean · contract honored · no frontend secret · no hard-coded price · Lukas-reviewed · merged · demo path still works.**

## 3. Git & PR conventions

- **Trunk-based, short-lived branches.** One feature = one branch off `main`:
  `feat/F06-layer1-solar`, `fix/F11-annuity-rounding`, `doc/feature-track`.
- **Conventional commits** (matches our existing history): `feat:`, `fix:`, `doc:`, `test:`, `chore:`, `refactor:`.
- **Small PRs, merge often.** Target < ~300 lines changed. A feature too big for that should have been split in the backlog.
- **PR title:** `Fxx <title>`; body links the spec and ticks the DoD checklist.
- **Review (scoped so the critical-path reviewer is never the bottleneck):** Lukas is the **gate for engine / domain / contract / number-bearing PRs** — the credibility surface. **Plumbing and UI PRs self-merge behind green tests** with an async post-merge glance; they do **not** block on Lukas. Anything with `contract_impact ≠ none` needs the contract owner (Zhou). Lukas's one mandatory synchronous pass is the **number-audit before code-freeze** (TIMELINE H+17). Rationale: Lukas also owns the 15.5h engine critical path, so a universal review gate would collide with the freeze (see `FEATURE_BACKLOG.md` §6 risk).
- **Squash-merge** to keep `main` history one-commit-per-feature. **Never push broken code to `main`** — it is the integration surface all three pull from.
- **Keep `main` green:** lint + type-check + unit tests must pass before merge. If you must land something amber, say so loudly in the standup channel and open a follow-up `fix/` immediately.

## 4. Engineering invariants (non-negotiable — these win the track)

These come straight from `system_workflow.md` and the challenge. Violating one breaks the demo's credibility, so they are enforced in review:

1. **The LLM never computes a number.** It receives the engine's structured output and only *explains/sells*. Every figure in generated copy is asserted to match the payload. (Trust + determinism.) — *system_workflow.md §1, §15.*
2. **Contract-first.** `specs/api/openapi.yaml` is the seam. Freeze it in P0; the FE codes against the generated TS client, the BE implements the schema. Changing it = a deliberate, reviewed PR that bumps the client in the same change.
3. **No secret in the frontend.** Vite inlines every `VITE_*` var into the public bundle, so the **only** FE env var is `VITE_API_BASE_URL`. All keys (Anthropic, Supabase service-role, Google) live in FastAPI's env. — *§1.*
4. **No hard-coded prices.** Every monetary unit price is read from the Supabase `price_catalog` and injected into the pure engine via a `PricingContext`. The domain core imports no price. — *§12.*
5. **Pure domain core.** `apps/api/src/app/domain/` is deterministic, zero-I/O, fully unit-tested. All I/O (HTTP, DB, LLM) lives in `adapters/`. This is where credibility lives — it is TDD'd against the §8 worked example.
6. **Honest over precision.** Show a confidence band and the biggest-uncertainty driver. Never print false precision. A near-zero or early-negative saving is shown honestly (it is a differentiator). — *§7, §8.1.*
7. **Demo determinism.** A `?fixture=<id>` path returns a frozen payload; the reference dataset is seeded so the live demo has **zero hard external dependencies**. Live PVGIS/SMARD/Google are upgrade *toggles*, never the critical path. — *§1, §13.2.*

## 5. Where things live (repo map)

```
specs/                          # SOURCE OF TRUTH for contracts (wins over docs)
  api/openapi.yaml              # frozen API contract (F02)            ← owner: Zhou
  domain/savings-engine.spec.md # the math, with worked-example vectors (F03) ← owner: Lukas
apps/
  api/   FastAPI (Python 3.12, uv) — BFF + pure domain core           ← Zhou (plumbing) · Lukas (domain/)
    src/app/domain/   pure engine: layers 1–4, optimiser, financing   ← Lukas
    src/app/adapters/ PVGIS · SMARD · resolver · site-check · llm      ← Zhou
    src/app/api/      routes (/recommend, /site-check) · deps          ← Zhou
  web/   Vite + React + TS + Tailwind SPA                              ← Philips
docs/
  design_plan/system_workflow.md   # the executable blueprint (v0.3.1) — the WHAT
  feature_track/                    # THIS folder — the HOW/WHO/WHEN
    README.md FEATURE_BACKLOG.md TIMELINE.md PROCESS.md _TEMPLATE.spec.md specs/
```

> **Stack note / cleanup:** the plan mandates **Vite** (§1). Stale **Next.js** build artifacts
> (`apps/web/.next/`) from an earlier attempt must be removed in F01 — see the risk in
> `FEATURE_BACKLOG.md`. Decision is recorded there; do not reintroduce a Next.js server tier.

## 6. Daily rhythm (lightweight, no ceremony)

- **Sync points** at each phase boundary (see `TIMELINE.md`): 5-minute check — *what merged, what's blocked, are we cutting any stretch?*
- **Blocked > 20 min?** Post in the channel and mock the dependency (the frozen contract makes this cheap).
- **Integration owner** watches `main` stays green and the end-to-end happy path works after each merge.
- **Cut stretch early, not late.** If a phase exit criterion (TIMELINE.md) is missed, drop the next stretch item rather than compress the demo/pitch window.

## 7. How to start a feature (copy-paste)

```bash
# 1. Pick your next Ready feature from FEATURE_BACKLOG.md (respect depends_on)
git switch main && git pull
git switch -c feat/F06-layer1-solar
# 2. Open specs/F06-*.spec.md — turn its acceptance criteria into failing tests first (TDD)
# 3. Build to green; keep it small; run lint+types+tests locally
# 4. Open a PR titled "F06 Layer 1 — Solar"; link the spec; tick the DoD checklist
# 5. Lukas reviews → squash-merge → confirm main is green and the demo path still runs
```
