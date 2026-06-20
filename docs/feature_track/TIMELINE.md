# Heimwende — build timeline (Sat 18:00 → Sun 14:00)

> **Now: Sat 2026-06-20 18:00. Abgabe: Sun 14:00 → 20 hours, sleep in the middle.**
> We build as a **stack, bottom-up**: get the boilerplate solid, stack the layers on top,
> and *only when all layers are green* do we put the UI on top. Last 3 h are the video.
> Owners: 🟦 Zhou (backend) · 🟩 Lukas (engine/data) · 🟪 Philips (frontend).
> Feature IDs ↔ [`FEATURE_BACKLOG.md`](./FEATURE_BACKLOG.md).

```
  🎬 video + submission   ← Sun 11:00–14:00 (frozen)
  🎨 UI                   ← when ALL layers are green
  ⚙️ layers L1–L4 + opt   ← Sat 20:00 → 💤 → Sun morning
  🧱 boilerplate (base)   ← Sat 18:00, the pipe everything stacks on
```

---

## ⏱ The clock at a glance

- **Sat 18:00** — 🧱 start: boilerplate
- **Sat ~20:00** — base done → start ⚙️ layers
- **Sat 23:00** — 💤 **sleep** (get as many layers done as possible first)
- **Sun ~06:30** — wake → finish remaining layers
- **Sun (layers green)** — 🎨 UI
- **Sun 11:00** — 🧊 freeze, hands off code
- **Sun 11:00–14:00** — 🎬 product video + submission
- **Sun 14:00** — 🏁 deadline, stop coding

---

## 🧱 Base — Boilerplate  ·  Sat 18:00 → ~20:00

**Done means:** the empty pipe works end-to-end — form → `/recommend` → fixture → renders on screen.
Everything else stacks on this, so nail it first.

- [ ] 🟦 Scaffold repo (Vite SPA + FastAPI/uv), **delete stale `.next/`**, lint+test run
- [ ] 🟦 Freeze `openapi.yaml` + generate TS client + Pydantic models — *the seam*
- [ ] 🟦+🟩 Supabase schema + `price_catalog` + `reference_plz` seeded (offline-safe)
- [ ] 🟦 Resolver PLZ → pricing context
- [ ] 🟦 `/recommend` skeleton returns a `?fixture` payload
- [ ] 🟪 App shell + TS client + intake form → posts and renders the fixture
- [ ] 🟩 Domain spec + §8 worked example as test vectors (so layers are TDD-ready)
- [ ] ☎️ Ask a Cloover mentor the financing APR/term (D9 — the one real unknown)

## ⚙️ Stack the layers  ·  Sat 20:00 → 23:00, then Sun morning

**Done means:** real numbers replace the fixture, one layer at a time. Each layer = a TDD slice.
**Get as far down this list as you can before 23:00; the rest is the first thing Sunday morning.**

- [ ] 🟩 Intake normalisation + baseline (€→km, existing equipment)
- [ ] 🟩 **L1 Solar** — load-aware self-consumption *(the first real number)*
- [ ] 🟩 **L2 Battery** — arbitrage + ≈€0 honesty
- [ ] 🟩 **L3 Heat pump** — fossil→HP and HP→HP
- [ ] 🟩 **L4 EV charger** — petrol→EV and EV-without-charger
- [ ] 🟦 Adapters seeded/offline-safe: PVGIS (980 fallback), tariff (€0.12), site-check
- [ ] 🟩 Optimiser + marginals + up-sell (ladder sums to headline; pick best rung)
- [ ] 🟩 Financing overlay + confidence band (annuity, KfW, 0 % VAT, break-even)
- [ ] 🟦 LLM advisor adapter (Claude prose + number-assertion guard)
- [ ] 🟦 `/recommend` + `/site-check` fully wired + persistence

## 💤 Sleep  ·  Sat 23:00 → ~06:30

- [ ] keep one person on-call for a red `main` (or just leave it green and all sleep)

## 🎨 UI on top  ·  Sun morning — once ALL layers are green

**Done means:** the numbers from the engine become the demo. Don't start until the layers hold.

- [ ] 🟪 Configurator — 4 layer rows + toggles
- [ ] 🟪 Dashboard hero number + honest two-phase before/after curve
- [ ] 🟪 Bucket tiles + up-sell line
- [ ] 🟪 Confidence chip + assumptions drawer (live re-run) + Claude paragraph + CTA
- [ ] 🟩 Review pass — every number sanity-checked vs §8; source audit
- [ ] 🟪 Polish + run the 90-sec demo path 3× until smooth

> 🟪 head-start: the **shell is part of the boilerplate**, so Philips can build UI components
> against the `?fixture` Saturday night while the engine fills in — just don't wire to real layers
> until they're green.

## 🧊 Freeze  ·  Sun 11:00

- [ ] end-to-end green on seeded data; `?fixture` demo path **locked**
- [ ] no new features after this — fix-only

---

## 🎬 Product video + submission  ·  Sun 11:00 → 14:00 (3 h)

**Done means:** ≤2-min video + public repo + deck submitted, and you've **opted in**.

### Hour 1 — 11:00–12:00 · prep & record
- [ ] Lock the final numbers on the `?fixture` path
- [ ] Write the shot list / script from the 90-sec demo flow (§ below)
- [ ] Record 2–3 clean narrated screen takes; pick the best

### Hour 2 — 12:00–13:00 · edit & assets *(in parallel)*
- [ ] 🟪 Edit / caption / voiceover; export ≤2-min video; upload
- [ ] 🟦+🟩 README (runnable, `?fixture` documented); deck/one-pager; **make repo public**

### Hour 3 — 13:00–14:00 · buffer & submit
- [ ] Re-watch the full video end-to-end
- [ ] Fix-only — no new features
- [ ] **Submit + opt in** before 14:00

### Submission checklist (all done by 13:00)
- [ ] ≤2-min product video (90-sec demo + ~30 s "why it's honest")
- [ ] Public repo, README runnable, stale `.next/` gone
- [ ] Deck/one-pager with the North Star: `monthly_saving = current_spend − (installment + new_energy_cost)`
- [ ] D9 financing assumption labelled wherever a number depends on it

---

## The 90-second demo (what the video shows)

`type address + 5 numbers` → solar number appears → tick 🔋 (≈€0, shown honestly) →
tick ♨️ + 🚗 (number jumps + up-sell line) → edit one assumption (band tightens) →
**"Generate proposal"** → installer copy appears. _(system_workflow.md §9.)_

## If behind — cut in this order (protect the demo, not the feature count)

1. **Live adapters F13/F14 (cheapest — zero demo impact):** the seeds already ship (PVGIS 980, SMARD €0.12) — skip the live calls.
2. F11 sensitivity analysis → keep the headline + a static ±band.
3. Conversational LLM intake → form only.
4. PDF proposal → copy-to-clipboard text only.
5. À-la-carte configurator → nested ladder only.
6. Site-Check richness → green-checks panel + the one real flag only.

**Never cut:** the hero number, the honest curve, the 4-layer ladder, the optimiser pick, the LLM
explanation, and `?fixture` demo determinism. Those _are_ the pitch.
