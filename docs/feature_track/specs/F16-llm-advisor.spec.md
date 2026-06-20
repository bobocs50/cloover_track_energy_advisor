---
id: F16
title: LLM advisor adapter (Claude, prose-only)
epic: E2 Backend & Adapters
owner: Zhou
reviewers: [Lukas]
priority: P3
mvp: true
status: Ready
branch: feat/F16-llm-advisor
depends_on: [F02]
contract_impact: reads
estimate_h: 2
---

# F16 — LLM advisor adapter (Claude, prose-only)

> **North-Star link:** The advisor *explains and sells* the headline `monthly_saving` in plain German —
> it **never computes** it. A number-assertion guard makes the prose strictly faithful to the engine
> payload, so the story can never overstate the saving.

## 1. Intent (what & why)

A provider-agnostic LLM adapter (**Claude default**, OpenAI fallback) that turns the **engine payload**
into prose: (a) a 3-sentence German rationale, (b) an up-sell nudge, (c) installer-ready proposal copy.
The LLM is **prose-only and must never compute a number** (§1, §9). A **number-assertion guard** checks
that **every € figure in the generated copy appears in the payload**, else the response is
rejected/regenerated (§15). The API key lives **only in FastAPI env** (§11).

## 2. Scope

**In scope**
- Provider-agnostic adapter; **Claude default** (model `claude-opus-4-8` or a fast tier), **OpenAI fallback** (§1, §11, §16 D8).
- Inputs = the **engine payload** (the §14.1 `Recommendation` with its `ScenarioResult` figures: `breakdown`, `installment_eur_month`, `monthly_saving_eur`, `saving_after_payoff_eur`, `capex`, `current_monthly_spend_eur`, `upsell`, `assumptions[]`); the LLM receives numbers, never derives them (§9).
- Outputs: (a) **3-sentence German rationale** → `Recommendation.explanation_md`, (b) **up-sell nudge** (diff vs next-smaller rung, §6.4) → `Recommendation.upsell.reason_md`, (c) **installer-ready proposal copy** → `Recommendation.proposal_copy_md` (§14.3).
- **Number-assertion guard**: extract every € figure in the copy; reject/regenerate unless each matches a value in the payload (§15).
- Key **only** in FastAPI env; never reaches the Vite bundle (§11, §1).

**Out of scope** (explicitly, to prevent creep)
- Computing any saving/capex/installment — that is the **pure engine** (F06–F11); the LLM only formats (§2, §9).
- The `/recommend` wiring + persisting `proposal` rows → **F17** (F16 returns the copy strings).
- Conversational-LLM **intake** → **F19 stretch** (this is the *output* advisor, not intake) (§3.4).
- PDF proposal export → **F23 stretch** (F16 emits markdown `copy_md`).

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | Provider-agnostic adapter; Claude default (`claude-opus-4-8`/fast tier), OpenAI fallback on error. | §1, §11, D8 |
| R2 | Input is the engine `Recommendation` payload; the prompt instructs **prose-only, never compute**. | §1, §9 |
| R3 | Produce (a) 3-sentence German rationale → `explanation_md`, (b) up-sell nudge → `upsell.reason_md`, (c) installer proposal copy → `proposal_copy_md`. | §9, §6.4, §14.3 |
| R4 | **Number-assertion guard**: every € figure in `explanation_md` / `proposal_copy_md` is checked against the `ScenarioResult` figures in the same payload (savings/breakdown/capex/installment), else reject. | §15 |
| R5 | On guard failure, **regenerate** (bounded retries); on repeated failure, fall back to a deterministic templated copy built from payload numbers (never ship an unverified figure). | §15 |
| R6 | API key read from FastAPI env only; never serialised to the client (§11). | §11, §1 |
| R7 | Adapter performs all I/O (LLM HTTP); the domain core stays pure and never calls it. | §2 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> The advisor computes **no number** — it consumes the engine payload. The only "source" is the payload
> itself; the guard is the correctness mechanism. No price is read here (prices already entered the
> payload via `PricingContext`, §12).

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| LLM completion | Claude API (server-side) | **Anthropic** (§11) | **OpenAI** adapter | Advisor · prose only |
| Model | `claude-opus-4-8` or fast tier | §16 D8 | OpenAI model | Advisor · generation |
| Every € figure in copy | from the engine payload | engine (F06–F11) | templated copy | Advisor · guard input |

```
# Number-assertion guard (§15 "assert every figure in the copy matches the payload"):
# allowed = every € figure on the ScenarioResult(s) in this payload:
allowed = { breakdown.{electricity,heating,mobility}_eur_month, installment_eur_month,
            monthly_saving_eur, saving_after_payoff_eur, capex.{gross,subsidy,after_subsidy}_eur,
            confidence.{band,low,high}_eur, Recommendation.current_monthly_spend_eur,
            upsell.delta_eur_month }
for figure in extract_euro_figures(explanation_md ++ proposal_copy_md ++ upsell.reason_md):
    if normalize(figure) not in normalize(allowed):
        reject → regenerate (bounded retries) → else deterministic templated copy
# Invariant (§15): "LLM never computes; assert every figure in the copy matches the ScenarioResult payload."
# Key (§11): Anthropic/OpenAI key in FastAPI env ONLY; the Vite bundle ships only VITE_API_BASE_URL.
```

> **Labelled assumption:** the exact prompt wording and the fast-tier model id are an **authoring
> choice** (§16 D8 fixes only "Claude default, OpenAI fallback"); they are documented in the adapter,
> not presented as a spec-mandated value. The number-assertion guard is mandatory regardless of model.

## 5. Contract surface  *(contract_impact = reads)*

- Reads the `Recommendation` payload (F02/§14.1) and **writes its prose into the frozen F02 copy fields**:
  the German rationale → `Recommendation.explanation_md`, the installer proposal → `Recommendation.proposal_copy_md`
  (the up-sell nudge populates `Recommendation.upsell.reason_md`). `/recommend` surfaces these and F17 persists them.
  No new wire object is introduced by F16.
- New/changed schema objects: none — F02 is frozen and already carries `explanation_md`, `proposal_copy_md` and `upsell.reason_md`.
- Backwards-compatible? yes — fills frozen copy fields; read-only over the numeric payload.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (three outputs, German)** — Given the §8 payload, when invoked, then it fills a **3-sentence** German `explanation_md`, an up-sell `upsell.reason_md`, and installer `proposal_copy_md` (all non-empty).
- [ ] **AC2 (guard passes faithful copy)** — Given copy that cites only payload figures (e.g. "+€120/mo", "€364/mo nach Tilgung"), when the guard runs, then it **passes** unchanged.
- [ ] **AC3 (guard rejects a hallucinated number)** — Given copy that invents "€500/mo" not in the payload, when the guard runs, then the response is **rejected** and regenerated (and never shipped with the bad figure) — the §15 invariant.
- [ ] **AC4 (regeneration → deterministic fallback)** — Given repeated guard failures, when retries are exhausted, then a **deterministic templated** copy built from payload numbers is returned (still passes the guard).
- [ ] **AC5 (provider fallback)** — Given the Claude call errors, when invoked, then the **OpenAI** adapter produces the copy and the guard still gates it (§1).
- [ ] **AC6 (no compute)** — Given the LLM is asked, when it responds, then it asserts **no figure absent from the payload**; the engine's `monthly_saving` is the single source of the number (§9).
- [ ] **AC7 (honesty/edge — ≈€0 rung)** — Given the §8.1 battery rung (≈€0/mo), when copy is generated, then it states the honest "≈ break-even now, pays off as load grows" framing and the guard permits "≈ €0" / "€124/mo nach Tilgung" because both are in the payload (no inflated figure).

## 7. Test plan

- **Unit** (guard + prompt assembly, LLM stubbed): AC2/AC3/AC4 with a fake completion injecting good vs hallucinated figures; assert the € extractor + normaliser catches mismatches; the §8 `+€120/mo` payload as a named fixture.
- **Integration / contract**: with a recorded Claude/OpenAI response, assert outputs land in the frozen `Recommendation.explanation_md` / `proposal_copy_md` / `upsell.reason_md` (which F17 surfaces and persists); assert no key is serialised to any client payload.
- **Demo-safety**: deterministic templated fallback (AC4) means the demo copy renders even with the LLM offline; `?fixture` returns frozen copy (F24, §15).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F02** (the `Recommendation` payload shape), the engine output (F06–F11 via F17), Anthropic/OpenAI key in **FastAPI env** (§11).
- **Downstream (feeds):** **F17** (`/recommend` surfaces the copy + persists `proposal`), **F23** (Claude paragraph + proposal view).
- **Mock until ready:** F17/F23 mock the three strings (rationale/upsell/`copy_md`) from a frozen fixture until F16 merges; the guard is testable in isolation with stubbed completions.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| LLM hallucinates a number | LLM **prose-only**; number-assertion guard rejects/regenerates any € figure not in the payload (AC3, §15). |
| LLM "improves" the saving / over-claims | Guard + deterministic templated fallback bound the copy to payload figures only (AC4, §15). |
| Provider outage | OpenAI fallback (AC5); templated fallback for full offline (§1, §15). |
| Key leaks via the bundle | Key in FastAPI env **only**; Vite ships only `VITE_API_BASE_URL` (§11, §1). |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (three outputs, guard pass/reject/fallback, provider fallback).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored — `contract_impact: reads`; prose written to the frozen `Recommendation.explanation_md` / `proposal_copy_md` / `upsell.reason_md`, no undocumented drift.
- [ ] **No secret in the frontend bundle** (LLM key server-side only); no hard-coded price.
- [ ] Every figure in generated copy traces to the engine payload (guard-enforced) — no invented precision.
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] Demo happy-path still works (templated fallback) after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §1 (provider-agnostic, Claude default, no secrets, never computes), §9 (Claude paragraph in the dashboard), §15 (LLM never computes; assert every figure matches the payload), §6.4 (up-sell), §14.1/§14.3 (`Recommendation` payload, `proposal`), §11 (Anthropic source, key server-side), §16 D8.
- Backlog `FEATURE_BACKLOG.md` §3 E2 row F16, §5 §1/§9/§15 traceability, §2 D8, §6 (LLM-invents-a-number risk).
- `specs/api/openapi.yaml` (F02) · `specs/domain/savings-engine.spec.md` (F03 — the payload it formats).
