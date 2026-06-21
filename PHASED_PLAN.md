# Plan: Fix & oversize the 3D house modules

## Progress
- [ ] Phase 1: Solar array on the roof
- [ ] Phase 2: Oversize + relocate heat pump, battery, EV
- [ ] Phase 3: Scene framing + verification

---

## Phase 1: Solar array on the roof
**Goal:** Replace the single invisible panel with a high-contrast, oversized grid of panels laid flush on the sun-facing roof plane.
**Effort:** ~2h

Steps:
1. In `houseModules.tsx`, special-case `pv`: render a new `SolarArray` from `slot.surface` directly in the house frame (bypass the single-panel tilt wrapper).
2. Build an in-plane basis from `surface.vertices` (eave axis + up-slope axis + normal) and tile a `cols x rows` grid that fills ~85% of the plane, lifted ~0.08 m off it, oriented to the slope.
3. Restyle panels for contrast on the slate-blue roof: lighter frames, distinct cell grid, keep the glassy glint. Keep the mount drop/scale-in.
4. Confirm it works for the currently-shown roof type; note in code that per-roof-type tiling is a follow-up.

**Risk:** in-plane axis selection from the quad must pick eave vs. slope correctly; verify numerically.

---

## Phase 2: Oversize + relocate heat pump, battery, EV
**Goal:** Make the three non-solar props chunky and move them all onto the visible south + east faces.
**Effort:** ~1.5h

Steps:
1. In `roofGeometry.ts` `moduleSlots`, move the EV charger off the `-v` (north) wall onto the south (`+v`) wall near the `+u` corner; keep heat pump on south (`-u` end), battery on east (`+u`).
2. Scale all three bodies up to oversized-showcase proportions and bump anchor offsets so they sit clear of the wall.
3. Improve material contrast so each reads against the near-white walls.

**Risk:** oversized bodies may clip the wall or each other — verify spacing against the default footprint.

---

## Phase 3: Scene framing + verification
**Goal:** Default south-east view shows all four big and legible with zero orbiting; static gates green.
**Effort:** ~1h

Steps:
1. Tweak camera distance/target if the oversized props need more headroom.
2. Verify in the preview: load the flow to `viewing`, toggle all four on, screenshot from the default angle.
3. `tsc --noEmit` + `eslint` clean.

**Risk:** none expected; verification only.
