---
id: F25
title: Submission pack (README + video + deck)
epic: E4 Integration & Demo
owner: Zhou
co_owners: [Lukas, Philips]
reviewers: [Lukas]
priority: P5
mvp: true
status: Ready
branch: feat/F25-submission-pack
depends_on: [F24]
contract_impact: none
estimate_h: 2
---

# F25 — Submission pack (README + video + deck)

> **North-Star link:** packages the whole project so the jury can run it and *see the one number* —
> the README runs the demo locally, the 2-minute Loom shows `monthly_saving` moving live, and the deck
> argues why that number is **credible**. It does not change the number; it makes the number land.

## 1. Intent (what & why)

F25 is the submission pack required to qualify (HACKATHON_MANUAL §Submission Requirements). It delivers:
a **public GitHub repo**, a **comprehensive README** (setup + run for both `apps/web` and `apps/api`,
env vars, architecture, data sources/attribution, the engineering invariants), a **2-minute Loom video
demo** (walking the §9 path), a **5-slide pitch deck**, and **documentation of every API/framework/tool**
used. It must be done by **Sun 13:00** (TIMELINE) with a **hard opt-in deadline of Sun 14:00**
(HACKATHON_MANUAL: "Submit your project by Sunday at 14:00"). The deck arc is fixed (§2 R4).

**All-hands task:** this is a whole-team push at the end. **Lead = whoever is least loaded at P5** (the
person whose last feature merged earliest); the others record their own slice (each owner documents the
APIs/tools they integrated, FE vs BE setup steps), while the lead assembles README + deck and drives the
Loom. Zhou is the nominal owner (repo/contract/setup authority); Lukas reviews for accuracy of every
claimed number/source.

## 2. Scope

**In scope**
- **Public GitHub repo** — flip visibility to public, ensure no secret committed, license/README present (HACKATHON_MANUAL §Open Source Repository).
- **Comprehensive README** — setup + run for **both `apps/web` (Vite SPA)** and **`apps/api` (FastAPI, `uv`)**; **env vars** (`VITE_API_BASE_URL` only client-side; all keys server-side); **architecture** (SPA→FastAPI BFF→domain core + adapters + Supabase, §1/§2); **data sources + attribution** (PVGIS, SMARD, OSM, KfW/BAFA/GEG, Destatis, Anthropic — §11); the **engineering invariants**.
- **2-minute Loom video** (or equivalent) — solution explanation + **live walkthrough of the §9 90-sec demo path** (the F24 rehearsed path), inside the 2-min limit.
- **5-slide pitch deck** following the fixed arc (R4).
- **Documentation of all APIs/frameworks/tools** — a table mapping each (Vite/React/TS/Tailwind, FastAPI/Python/uv, Supabase, PVGIS/SMARD/aWATTar/OSM/Google-Solar, KfW/BAFA/GEG, Anthropic Claude) to where/why it's used (§11, §13).
- **Eleven Labs side-challenge note** — explicitly state whether used (HACKATHON_MANUAL §Side Challenge) — for us: **not used** (state it plainly so there's no ambiguity).
- **Confirm the (TBA) submission-form URL + the correct Discord invite early Sunday** (well before 13:00) and pin the working links for the team.
- A **submission checklist** + the **14:00 opt-in** reminder, executed at the §13:00 gate.

**Out of scope** (explicitly, to prevent creep)
- Any code/feature work, bug-fixing, or new scope → frozen at **code-freeze Sun 11:00** (TIMELINE); F25 is docs/video/deck only. Fixes after freeze are fix-only in the buffer, not F25.
- The 5-**minute** finalist live pitch deck/script → that's the **Finalist Stage** (HACKATHON_MANUAL §Stage 2), prepared only **if** selected; F25 ships the **2-min** video + 5-slide deck for pre-selection.
- Making the demo path green/rehearsed → **F24** (F25 records it; it does not fix it).
- Marketing site / extended docs → not required ("No massive documentation needed"); keep it lean and accurate.

## 3. Functional requirements

| # | Requirement | Source |
|---|-------------|--------|
| R1 | A **public GitHub repository** with the full source, no committed secret. | HACKATHON_MANUAL §Open Source Repository |
| R2 | **README** runs both apps from clean: `apps/api` (`uv` install → seed Supabase → `uvicorn`) and `apps/web` (`pnpm/npm install` → `VITE_API_BASE_URL` → `vite dev`); a one-command/seeded **offline demo** path is documented (the `?fixture` route, F24). | HACKATHON_MANUAL §README; §1, §14.3 |
| R3 | README documents **env vars** (only `VITE_API_BASE_URL` client-side; Anthropic/Google/Supabase keys server-side), **architecture** (§1/§2 diagram), **data sources + attribution** (§11), and the **engineering invariants**. | §1, §2, §11, §15 |
| R4 | **5-slide deck** follows the arc: (1) **the inversion** (today: install→financing→tariff bolted on; we sell the outcome) → (2) **the North-Star formula + honest curve** (`monthly_saving = current_spend − (installment + new_energy_cost)`; ≈cost-neutral now → €X after payoff) → (3) **live demo** (the §9 path) → (4) **why the number is credible** (official sources, 4 certainty drivers, load-aware self-consumption, transparent battery ≈€0) → (5) **up-sell wedge + Cloover business fit** (bigger upgrade ⇒ bigger saving; one product, one number). | Cloover challenge; §6.4, §7, §8, §9 |
| R5 | **2-minute video** (Loom/equiv) = solution explanation + **live §9 walkthrough**, within 2:00. | HACKATHON_MANUAL §Project Presentation |
| R6 | **APIs/frameworks/tools table** lists every dependency and where it's used (§11, §13.2). | HACKATHON_MANUAL §README; §11, §13 |
| R7 | The **Eleven Labs** side-challenge status is stated explicitly (**not used**). | HACKATHON_MANUAL §Side Challenge |
| R8 | Submitted via the project submission form **before Sun 14:00**, and the team **opts in**. | HACKATHON_MANUAL Agenda + §Submission |
| R9 | **Every financed figure** in the deck/README/video carries the **"financing 5 %/180 mo — assumption, Cloover TBC (D9)"** caveat (no financed number shown as confirmed). | §6.5, §15, D9 |
| R10 | **Confirm the (currently "TBA") submission-form URL and the correct Discord invite early Sunday**, well before 13:00 — record/pin the working links; do not discover them at the deadline. | HACKATHON_MANUAL §Submission; TIMELINE |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> **N/A — pure docs/video/deck, no computation or fetch.** F25 *describes* the data sources; it must
> **cite them accurately** (the README attribution + the deck "why credible" slide reuse §11/§10/§12
> verbatim — no new numbers, no invented precision). Any figure shown in the deck/video must trace to the
> F24 demo payload / §8 (€435 → −€24/≈€0/+€20/+€124 → +€120 now / €364 after / ±€35).

The **engineering invariants** to state verbatim in the README (the credibility spine):
```
- North Star: monthly_saving = current_monthly_spend − (loan_installment + new_energy_cost).
- The 4-layer ladder (☀️ Solar → 🔋 Battery → ♨️ Heat pump → 🚗 EV) marginals SUM EXACTLY to the headline.
- The domain core is PURE (deterministic, TDD, zero I/O); the LLM EXPLAINS but NEVER computes the number.
- Every figure cites an official source + a fallback; prices live in `price_catalog` (DB), never hard-coded.
- No secret in the frontend bundle — only VITE_API_BASE_URL; all keys in FastAPI.
- Demo determinism via the `?fixture` path; live PVGIS/SMARD/Google are toggles with seeded fallbacks
  (PVGIS→980, SMARD→€0.12, OSM→checkbox).
- Honest by construction: battery ≈€0 at low load (shown, not hidden); APR/term 5%/180mo is a labelled TBC.
```
Attribution list for the README (from §11): PVGIS (EU JRC) · SMARD/aWATTar/Energy-Charts (BNetzA /
Fraunhofer ISE) · OSM Overpass · KfW 458 · BAFA · GEG · Destatis · Google Solar (optional) · Anthropic
Claude · Supabase.

## 5. Contract surface  *(if contract_impact ≠ none)*

- **None** — `contract_impact: none`. F25 touches no `openapi.yaml` and no runtime code; it is documentation, a video, and a deck.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (repo public, no secret)** — Given the GitHub repo at submission, when opened logged-out, then it is **public**, builds, and a secret-scan/grep finds **no key** (only `VITE_API_BASE_URL` referenced; `.env` git-ignored).
- [ ] **AC2 (README runs both apps from clean)** — Given a fresh clone, when a new dev follows the README, then **`apps/api`** starts (`uv` deps → seed → `uvicorn`) and **`apps/web`** starts (`install` → set `VITE_API_BASE_URL` → `vite dev`), and the **seeded/offline `?fixture` demo** renders the §8 headline — no missing step.
- [ ] **AC3 (README content complete)** — Given the README, when reviewed, then it contains **env vars**, an **architecture** section (SPA→FastAPI BFF→domain+adapters+Supabase, §1/§2), **data sources + attribution** (§11), and the **engineering invariants** block (§4).
- [ ] **AC4 (2-min video)** — Given the Loom link, when played, then it is **≤ 2:00**, explains the solution, and shows a **live §9 walkthrough** where the headline moves (solar → 🔋 ≈€0 → ♨️+🚗 jump → assumption edit → proposal).
- [ ] **AC5 (5-slide deck arc)** — Given the deck, when reviewed, then it is **5 slides** in the exact R4 arc (inversion → North-Star formula + honest curve → live demo → why credible → up-sell + Cloover fit) and every number on it matches the F24 payload / §8.
- [ ] **AC6 (APIs/tools documented)** — Given the README, when checked against the running system, then **every** API/framework/tool (Vite/React/TS/Tailwind, FastAPI/Python/uv, Supabase, PVGIS/SMARD/OSM/(Google Solar), KfW/BAFA/GEG, Anthropic) is listed with where/why it's used (§11, §13.2).
- [ ] **AC7 (Eleven Labs status)** — Given the submission, when the side-challenge is considered, then the README/submission **states Eleven Labs was not used** (no ambiguity).
- [ ] **AC8 (honesty/edge — claims match reality, Lukas gate)** — Given the deck + video + README, when Lukas audits, then **no claim over-states** (KfW capped 70 %/€21k, EV grant €0, battery ≈€0 honest, APR/term flagged TBC) and **every figure traces to §8 / the payload / a labelled assumption** — no invented precision.
- [ ] **AC9 (submitted on time + opted in)** — Given the §13:00 submission gate, when the checklist runs, then the form is submitted with the repo + video + deck links and the team **opts in before 14:00**.
- [ ] **AC10 (financing caveat on every financed figure)** — Given the deck/README/video, when any **financed** figure is shown (installment, "+€X/mo now", break-even), then it carries the **"financing 5 %/180 mo — assumption, Cloover TBC (D9)"** caveat (visible on the deck slide / README line / video lower-third) — no financed number is presented as confirmed.
- [ ] **AC11 (submission URL + Discord confirmed early)** — Given Sunday morning, when prep starts, then the **(currently "TBA") project submission-form URL** and the **correct Discord invite** are **confirmed and recorded well before 13:00** (not discovered at the deadline); the working links are pinned for the team.

## 7. Test plan

- **Unit**: N/A (no code). The "tests" are review checks against the AC list.
- **Integration / contract**: a **fresh-clone dry-run** of the README on a clean machine/container — both apps start and the `?fixture` demo renders the §8 headline (AC2); the secret-scan/grep (AC1).
- **Demo-safety**: the video is recorded against the **F24 seeded `?fixture` path** (never a live API on camera); the deck numbers are pulled from the **same frozen payload** so deck ≡ video ≡ README ≡ §8 — one source of truth, no drift.

**Submission checklist (run at the Sun 13:00 gate — TIMELINE):**
- [ ] **EARLY Sunday (well before 13:00):** the **(TBA) submission-form URL** and the **correct Discord invite** confirmed, recorded and pinned for the team (AC11) — not left to the deadline.
- [ ] Repo **public**, no secret committed, README + license present (AC1).
- [ ] README: both-app setup/run, env vars, architecture, data attribution, invariants (AC2, AC3).
- [ ] Fresh-clone dry-run passes; `?fixture` offline demo renders §8 (AC2).
- [ ] **2-min Loom** recorded, ≤ 2:00, live §9 walkthrough, link in the form (AC4).
- [ ] **5-slide deck** in the R4 arc, numbers == payload/§8, exported (AC5).
- [ ] **Every financed figure carries the "financing 5 %/180 mo — assumption, Cloover TBC (D9)" caveat** in deck/README/video (AC10).
- [ ] APIs/frameworks/tools table complete (AC6); **Eleven Labs = not used** stated (AC7).
- [ ] Lukas accuracy audit passed — no over-claim, every figure sourced (AC8).
- [ ] **Submitted via the form + opted in before 14:00** (AC9). ⏰ *Hard stop — stop coding at 14:00.*

## 8. Dependencies & interfaces

- **Upstream (needs):** **F24** — the green, rehearsed §9 demo path on seeded data is the thing the README documents, the Loom records, and the deck's "live demo" slide shows; the F24 `?fixture` golden payload supplies the numbers used everywhere (deck/video/README), guaranteeing they agree. Each owner's notes on the APIs/tools they integrated feed the docs table.
- **Downstream (feeds):** the **jury evaluation** (pre-selection) and, if selected, the **5-minute Finalist pitch** (HACKATHON_MANUAL §Stage 2) reuses the deck arc + Loom.
- **Mock until ready:** the deck/README can be **drafted in P5 against the frozen `?fixture` payload** before the final live run; the screen-recording is taken once F24 is green. The deck skeleton (5 titled slides) can be built ahead and numbers filled from the payload last.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| **14:00 hard deadline missed** | Submission gate at **Sun 13:00** with a 1h buffer (TIMELINE); checklist (§7) executed; **stop coding at 14:00** — HACKATHON_MANUAL Agenda. |
| README doesn't actually run from clean | **Fresh-clone dry-run** on a clean env (AC2) before submit; both-app steps + env vars verified — §1. |
| A secret committed to the now-public repo | History/secret scan + grep before flipping public (AC1); `.env` git-ignored; only `VITE_API_BASE_URL` client-side — §1, §15. |
| Deck/video over-claims a number | Numbers pulled from the **one frozen payload** (deck ≡ video ≡ §8); **Lukas accuracy audit** (AC8) — KfW/EV-grant/battery/APR honesty — §15. |
| Video over 2:00 / no live walkthrough | Record against the rehearsed F24 path; trim to ≤ 2:00; show the headline moving (AC4) — §9. |
| All-hands but nobody owns it | **Lead = least-loaded at P5**; per-owner doc slices; Zhou owns repo/setup, Lukas the accuracy gate — TIMELINE swimlanes. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria satisfied (documented manual checks — this is a docs/video/deck feature, not code).
- [ ] Lint/type-check N/A (no code); but the **fresh-clone dry-run passes** (both apps start, `?fixture` demo renders §8).
- [ ] Contract honored — `contract_impact: none`; no `openapi.yaml` or code touched.
- [ ] **No secret in the repo** (public) **or** the frontend bundle; no hard-coded price introduced.
- [ ] Every figure in README/deck/video traces to the F24 payload / §8 / a labelled assumption — **Lukas accuracy sign-off recorded**.
- [ ] Reviewed by Lukas; merged to `main`; repo flipped **public**.
- [ ] **Submitted before 14:00 and opted in** — README, 2-min Loom, 5-slide deck, public repo, APIs/tools doc all linked in the form.

## 11. References

- `docs/track_doc/HACKATHON_MANUAL.md` — §Submission Requirements (2-min video, public repo + README + API/tooling docs), Agenda (**14:00 opt-in deadline**), §Side Challenge (Eleven Labs), §Stage 2 (finalist pitch)
- `docs/design_plan/system_workflow.md` §1 (stack/no-secrets/BFF/determinism), §2 (pipeline/architecture), §9 (demo flow), §11 (data sources + attribution), §13 (resource lists), §15 (invariants/risks), §8 (worked-example numbers)
- `docs/feature_track/TIMELINE.md` §1 (Sun 13:00 submission-ready, 14:00 opt-in), §2 (P5) · F24 (the rehearsed demo path + `?fixture` payload)
