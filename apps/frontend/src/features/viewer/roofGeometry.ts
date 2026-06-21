// Phase 4A — Geometry engine.
// Pure module: (LatLng[] | null) + RoofParams → Three.js BufferGeometry[] +
// RoofPlacementSurface[]. No React, no DOM. Spec: data/3d_building.md.
//
// Coordinate system (local metre space, Three.js convention):
//   +x = east, +y = up, +z = south  (north = −z)
// The footprint is recentred on its own centroid, so the house sits at the
// world origin and the camera/orbit target can stay at (0,0,0).
import * as THREE from "three";
import { rhumbBearing, rhumbDistance } from "@turf/turf";
import type { LatLng } from "@/features/roof/useMapboxDraw";
import type { RoofParams } from "@/features/roof/RoofParamsStep";

type Vec3 = [number, number, number];

/** A placement surface a future panel-layout pass can consume (3d_building.md §5). */
export interface RoofPlacementSurface {
  id: string;
  roofType: "flat" | "gable";
  vertices: Vec3[];
  normal: Vec3;
  widthM: number;
  heightM: number;
  pitchDeg: number;
  azimuthDeg: number;
}

/** Which part of the building a geometry belongs to (drives its material). */
export type GeometryKind = "wall" | "roof";

/** What a roof builder produces before the dispatch attaches the footprint. */
type RoofBuild = Omit<HouseGeometry, "footprint">;

export interface HouseGeometry {
  /** Wall + roof meshes, ready to drop into a <mesh> each. */
  geometries: THREE.BufferGeometry[];
  /** Parallel to `geometries`: whether each mesh is a wall or a roof plane. */
  kinds: GeometryKind[];
  /** Explicit roof planes for downstream panel placement. */
  surfaces: RoofPlacementSurface[];
  /** Footprint half-extents — handy for framing the camera. */
  bounds: { halfLongM: number; halfShortM: number; ridgeHeightM: number };
  /** Oriented footprint axes + wall height — anchors the toy module layer. */
  footprint: {
    u: { x: number; z: number };
    v: { x: number; z: number };
    halfLong: number;
    halfShort: number;
    wallHeightM: number;
  };
}

// ── Footprint ────────────────────────────────────────────────────────────────

/** An oriented rectangle in local metre space. u = long axis, v = short axis. */
interface Footprint {
  halfLong: number; // L: half-extent along u (ridge axis)
  halfShort: number; // W: half-extent along v
  u: { x: number; z: number }; // unit vector, long axis
  v: { x: number; z: number }; // unit vector, short axis
}

/** 10 m × 8 m rectangle, long axis pointing east — used when no polygon drawn. */
const DEFAULT_FOOTPRINT: Footprint = {
  halfLong: 5,
  halfShort: 4,
  u: { x: 1, z: 0 },
  v: { x: 0, z: 1 },
};

/**
 * Convert drawn lat/lng corners to local metre-space points, recentred on the
 * polygon centroid. Uses rhumb bearing + distance so real-world azimuth is
 * preserved (caveat in 3d_building.md): panels must face the right direction.
 */
export function latLngToLocal(polygon: LatLng[]): { x: number; z: number }[] {
  const lat0 = polygon.reduce((s, p) => s + p.lat, 0) / polygon.length;
  const lng0 = polygon.reduce((s, p) => s + p.lng, 0) / polygon.length;
  const origin = [lng0, lat0];

  return polygon.map((p) => {
    const dest = [p.lng, p.lat];
    const dist = rhumbDistance(origin, dest, { units: "meters" });
    const bearing = (rhumbBearing(origin, dest) * Math.PI) / 180; // clockwise from north
    const east = dist * Math.sin(bearing);
    const north = dist * Math.cos(bearing);
    return { x: east, z: -north }; // +z = south
  });
}

/** Oriented bounding rectangle of the local points; long axis becomes the ridge. */
function orientedFootprint(localPts: { x: number; z: number }[]): Footprint {
  // Long axis = direction of the polygon's longest edge.
  let best = { len: -1, dx: 1, dz: 0 };
  for (let i = 0; i < localPts.length; i++) {
    const a = localPts[i];
    const b = localPts[(i + 1) % localPts.length];
    const dx = b.x - a.x;
    const dz = b.z - a.z;
    const len = Math.hypot(dx, dz);
    if (len > best.len) best = { len, dx, dz };
  }
  let u = { x: best.dx / best.len, z: best.dz / best.len };
  let v = { x: -u.z, z: u.x };

  // Project every point onto u/v to get extents.
  const proj = (axis: { x: number; z: number }) => {
    let min = Infinity;
    let max = -Infinity;
    for (const p of localPts) {
      const d = p.x * axis.x + p.z * axis.z;
      if (d < min) min = d;
      if (d > max) max = d;
    }
    return (max - min) / 2;
  };
  let halfLong = proj(u);
  let halfShort = proj(v);

  // Guarantee u is the longer axis so the ridge runs lengthwise.
  if (halfShort > halfLong) {
    [u, v] = [v, u];
    [halfLong, halfShort] = [halfShort, halfLong];
  }

  // Canonicalize the axis signs toward the default camera (which sits in the
  // +x / +z octant). The longest-edge direction is otherwise arbitrary, so the
  // module-bearing faces (+v carries PV / heat pump / battery, +u carries the
  // EV bay) would point away from the camera for ~half of drawn polygons. Pin
  // +u to east and +v to south so the feature side always faces front. This
  // matches the DEFAULT_FOOTPRINT (u east, v south), so undrawn houses are
  // unaffected.
  if (u.x < 0) u = { x: -u.x, z: -u.z };
  if (v.z < 0) v = { x: -v.x, z: -v.z };

  return { halfLong, halfShort, u, v };
}

// ── Face helpers ──────────────────────────────────────────────────────────────

/** Fan-triangulate a convex planar polygon into a BufferGeometry. */
function faceGeometry(verts: Vec3[]): THREE.BufferGeometry {
  const positions: number[] = [];
  for (let i = 1; i < verts.length - 1; i++) {
    positions.push(...verts[0], ...verts[i], ...verts[i + 1]);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  g.computeVertexNormals();
  return g;
}

function faceNormal(a: Vec3, b: Vec3, c: Vec3): Vec3 {
  const ab = new THREE.Vector3(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
  const ac = new THREE.Vector3(c[0] - a[0], c[1] - a[1], c[2] - a[2]);
  const n = ab.cross(ac).normalize();
  return [n.x, n.y, n.z];
}

/** Compass bearing (deg from north, clockwise) of a local (x,z) direction. */
function bearingDeg(dir: { x: number; z: number }): number {
  const deg = (Math.atan2(dir.x, -dir.z) * 180) / Math.PI;
  return (deg + 360) % 360;
}

/** The four footprint corners in local metre space, CCW. */
function corners(fp: Footprint): Vec3[] {
  const { u, v, halfLong: L, halfShort: W } = fp;
  const c = (su: number, sv: number): Vec3 => [
    su * L * u.x + sv * W * v.x,
    0,
    su * L * u.z + sv * W * v.z,
  ];
  return [c(+1, +1), c(-1, +1), c(-1, -1), c(+1, -1)];
}

/** Side walls: four vertical quads from ground to `topY` along each footprint edge. */
function wallGeometries(base: Vec3[], topY: number): THREE.BufferGeometry[] {
  return base.map((a, i) => {
    const b = base[(i + 1) % base.length];
    return faceGeometry([
      [a[0], 0, a[2]],
      [b[0], 0, b[2]],
      [b[0], topY, b[2]],
      [a[0], topY, a[2]],
    ]);
  });
}

/**
 * Side walls where each base corner has its own top height — used by the shed
 * roof, whose two long walls are trapezoids that follow the sloping eaves.
 * `tops[i]` is the wall-top height above corner `base[i]`.
 */
function slopedWallGeometries(base: Vec3[], tops: number[]): THREE.BufferGeometry[] {
  return base.map((a, i) => {
    const j = (i + 1) % base.length;
    const b = base[j];
    return faceGeometry([
      [a[0], 0, a[2]],
      [b[0], 0, b[2]],
      [b[0], tops[j], b[2]],
      [a[0], tops[i], a[2]],
    ]);
  });
}

// ── Roof builders ─────────────────────────────────────────────────────────────

function buildFlatRoof(fp: Footprint, wallHeightM: number): RoofBuild {
  const base = corners(fp);
  const top = base.map<Vec3>(([x, , z]) => [x, wallHeightM, z]);
  const walls = wallGeometries(base, wallHeightM);
  const geometries = [...walls, faceGeometry(top)];
  const kinds: GeometryKind[] = [...walls.map(() => "wall" as const), "roof"];

  const surface: RoofPlacementSurface = {
    id: "flat-0",
    roofType: "flat",
    vertices: top,
    normal: [0, 1, 0],
    widthM: fp.halfLong * 2,
    heightM: fp.halfShort * 2,
    pitchDeg: 0,
    azimuthDeg: 180, // flat roof has no aspect; default south
  };
  return {
    geometries,
    kinds,
    surfaces: [surface],
    bounds: { halfLongM: fp.halfLong, halfShortM: fp.halfShort, ridgeHeightM: 0 },
  };
}

function buildGableRoof(
  fp: Footprint,
  wallHeightM: number,
  pitchDeg: number,
): RoofBuild {
  const { u, v, halfLong: L, halfShort: W } = fp;
  const pitchRad = (pitchDeg * Math.PI) / 180;
  const ridgeHeight = Math.tan(pitchRad) * W; // roofWidthM/2 = W
  const ridgeY = wallHeightM + ridgeHeight;

  // Named local points.
  const p = (su: number, sv: number, y: number): Vec3 => [
    su * L * u.x + sv * W * v.x,
    y,
    su * L * u.z + sv * W * v.z,
  ];
  const eaveAplus = p(+1, +1, wallHeightM);
  const eaveAminus = p(-1, +1, wallHeightM);
  const eaveBplus = p(+1, -1, wallHeightM);
  const eaveBminus = p(-1, -1, wallHeightM);
  const ridgePlus = p(+1, 0, ridgeY); // u = +L end
  const ridgeMinus = p(-1, 0, ridgeY); // u = −L end

  const base = corners(fp);
  const geometries: THREE.BufferGeometry[] = [...wallGeometries(base, wallHeightM)];
  const kinds: GeometryKind[] = base.map(() => "wall" as const);

  // Gable-end triangles on the two short walls (u = ±L) — still walls.
  geometries.push(faceGeometry([eaveAplus, eaveBplus, ridgePlus]));
  geometries.push(faceGeometry([eaveBminus, eaveAminus, ridgeMinus]));
  kinds.push("wall", "wall");

  // Two sloped roof planes.
  const planeA: Vec3[] = [eaveAminus, eaveAplus, ridgePlus, ridgeMinus]; // faces +v
  const planeB: Vec3[] = [eaveBplus, eaveBminus, ridgeMinus, ridgePlus]; // faces −v
  geometries.push(faceGeometry(planeA), faceGeometry(planeB));
  kinds.push("roof", "roof");

  const slopeLen = Math.hypot(W, ridgeHeight);
  const surfaces: RoofPlacementSurface[] = [
    {
      id: "gable-0",
      roofType: "gable",
      vertices: planeA,
      normal: faceNormal(planeA[0], planeA[1], planeA[2]),
      widthM: L * 2,
      heightM: slopeLen,
      pitchDeg,
      azimuthDeg: bearingDeg(v),
    },
    {
      id: "gable-1",
      roofType: "gable",
      vertices: planeB,
      normal: faceNormal(planeB[0], planeB[1], planeB[2]),
      widthM: L * 2,
      heightM: slopeLen,
      pitchDeg,
      azimuthDeg: bearingDeg({ x: -v.x, z: -v.z }),
    },
  ];

  return {
    geometries,
    kinds,
    surfaces,
    bounds: { halfLongM: L, halfShortM: W, ridgeHeightM: ridgeHeight },
  };
}

function buildHipRoof(
  fp: Footprint,
  wallHeightM: number,
  pitchDeg: number,
): RoofBuild {
  const { u, v, halfLong: L, halfShort: W } = fp;
  const pitchRad = (pitchDeg * Math.PI) / 180;
  const ridgeHeight = Math.tan(pitchRad) * W;
  const ridgeY = wallHeightM + ridgeHeight;

  // Standard equal-pitch hip: the ridge is inset from each gable end by the
  // half-short-width W (the hip rafters run at 45° in plan). When L ≤ W the
  // ridge collapses to a point and the roof becomes a pyramid.
  const ridgeHalf = Math.max(L - W, 0);

  const p = (su: number, sv: number, y: number): Vec3 => [
    su * L * u.x + sv * W * v.x,
    y,
    su * L * u.z + sv * W * v.z,
  ];
  const eaveAplus = p(+1, +1, wallHeightM);
  const eaveAminus = p(-1, +1, wallHeightM);
  const eaveBplus = p(+1, -1, wallHeightM);
  const eaveBminus = p(-1, -1, wallHeightM);
  const ridgePt = (signU: number): Vec3 => [
    signU * ridgeHalf * u.x,
    ridgeY,
    signU * ridgeHalf * u.z,
  ];
  const ridgePlus = ridgePt(+1);
  const ridgeMinus = ridgePt(-1);

  const base = corners(fp);
  // All four walls are plain rectangles for a hip roof.
  const geometries: THREE.BufferGeometry[] = [...wallGeometries(base, wallHeightM)];
  const kinds: GeometryKind[] = base.map(() => "wall" as const);

  // Two trapezoidal main slopes (face ±v) + two triangular hip ends (face ±u).
  const planeA: Vec3[] = [eaveAminus, eaveAplus, ridgePlus, ridgeMinus]; // +v
  const planeB: Vec3[] = [eaveBplus, eaveBminus, ridgeMinus, ridgePlus]; // −v
  const hipEndPlus: Vec3[] = [eaveAplus, eaveBplus, ridgePlus]; // +u
  const hipEndMinus: Vec3[] = [eaveBminus, eaveAminus, ridgeMinus]; // −u
  geometries.push(
    faceGeometry(planeA),
    faceGeometry(planeB),
    faceGeometry(hipEndPlus),
    faceGeometry(hipEndMinus),
  );
  kinds.push("roof", "roof", "roof", "roof");

  const slopeLen = Math.hypot(W, ridgeHeight);
  const surfaces: RoofPlacementSurface[] = [
    {
      id: "hip-0",
      roofType: "gable",
      vertices: planeA,
      normal: faceNormal(planeA[0], planeA[1], planeA[2]),
      widthM: L * 2,
      heightM: slopeLen,
      pitchDeg,
      azimuthDeg: bearingDeg(v),
    },
    {
      id: "hip-1",
      roofType: "gable",
      vertices: planeB,
      normal: faceNormal(planeB[0], planeB[1], planeB[2]),
      widthM: L * 2,
      heightM: slopeLen,
      pitchDeg,
      azimuthDeg: bearingDeg({ x: -v.x, z: -v.z }),
    },
    {
      id: "hip-2",
      roofType: "gable",
      vertices: hipEndPlus,
      normal: faceNormal(hipEndPlus[0], hipEndPlus[1], hipEndPlus[2]),
      widthM: W * 2,
      heightM: slopeLen,
      pitchDeg,
      azimuthDeg: bearingDeg(u),
    },
    {
      id: "hip-3",
      roofType: "gable",
      vertices: hipEndMinus,
      normal: faceNormal(hipEndMinus[0], hipEndMinus[1], hipEndMinus[2]),
      widthM: W * 2,
      heightM: slopeLen,
      pitchDeg,
      azimuthDeg: bearingDeg({ x: -u.x, z: -u.z }),
    },
  ];

  return {
    geometries,
    kinds,
    surfaces,
    bounds: { halfLongM: L, halfShortM: W, ridgeHeightM: ridgeHeight },
  };
}

function buildShedRoof(
  fp: Footprint,
  wallHeightM: number,
  pitchDeg: number,
): RoofBuild {
  const { v, halfLong: L, halfShort: W } = fp;
  const pitchRad = (pitchDeg * Math.PI) / 180;
  // Single plane sloping across the short axis: low eave at v=+W, high at v=−W.
  const rise = Math.tan(pitchRad) * (W * 2);
  const lowY = wallHeightM;
  const highY = wallHeightM + rise;

  const base = corners(fp); // [c(+1,+1), c(-1,+1), c(-1,-1), c(+1,-1)]
  // Per-corner wall-top height: v=+W corners are low, v=−W corners are high.
  const tops = [lowY, lowY, highY, highY];
  const geometries: THREE.BufferGeometry[] = [...slopedWallGeometries(base, tops)];
  const kinds: GeometryKind[] = base.map(() => "wall" as const);

  // Single sloped roof plane spanning the four wall-tops.
  const plane: Vec3[] = base.map<Vec3>(([x, , z], i) => [x, tops[i], z]);
  geometries.push(faceGeometry(plane));
  kinds.push("roof");

  const slopeLen = Math.hypot(W * 2, rise);
  const surface: RoofPlacementSurface = {
    id: "shed-0",
    roofType: "gable",
    vertices: plane,
    normal: faceNormal(plane[0], plane[1], plane[2]),
    widthM: L * 2,
    heightM: slopeLen,
    pitchDeg,
    azimuthDeg: bearingDeg(v), // faces the low (downslope) side
  };

  return {
    geometries,
    kinds,
    surfaces: [surface],
    bounds: { halfLongM: L, halfShortM: W, ridgeHeightM: rise },
  };
}

// ── Dispatch ──────────────────────────────────────────────────────────────────

/** Build the full house geometry from the (optional) drawn polygon + roof params. */
export function buildHouseGeometry(
  polygon: LatLng[] | null,
  params: RoofParams,
): HouseGeometry {
  const fp =
    polygon && polygon.length >= 3
      ? orientedFootprint(latLngToLocal(polygon))
      : DEFAULT_FOOTPRINT;

  let build: RoofBuild;
  switch (params.roofType) {
    case "flat":
      build = buildFlatRoof(fp, params.wallHeightM);
      break;
    case "hip":
      build = buildHipRoof(fp, params.wallHeightM, params.pitchDeg);
      break;
    case "shed":
      build = buildShedRoof(fp, params.wallHeightM, params.pitchDeg);
      break;
    case "gable":
    default:
      build = buildGableRoof(fp, params.wallHeightM, params.pitchDeg);
      break;
  }

  // Expose the oriented footprint so the toy module layer can anchor props to
  // walls/corners that scale with the drawn polygon (3d_modules.md).
  return {
    ...build,
    footprint: {
      u: fp.u,
      v: fp.v,
      halfLong: fp.halfLong,
      halfShort: fp.halfShort,
      wallHeightM: params.wallHeightM,
    },
  };
}

// ── Module slots (toy layer) ────────────────────────────────────────────────
// Anchor points for the four toggleable energy props. Each slot is keyed off the
// oriented footprint axes (u/v), so it stays glued to the right wall/corner even
// when the house is rotated to its real-world bearing. Spec: data/3d_modules.md.

/** The four energy products that can be toggled onto the house. */
export type ModuleKind = "pv" | "battery" | "heat_pump" | "ev";

/** A resolved placement for one module, in local metre space. */
export interface ModuleSlot {
  kind: ModuleKind;
  /** World position of the module's anchor (its base/back-centre). */
  position: Vec3;
  /** Y-rotation (radians) so the module's +z "front" faces outward. */
  rotationY: number;
  /** Optional roof surface a module lies on (unused now PV is ground-mounted). */
  surface?: RoofPlacementSurface;
}

/** Y-rotation that aims a +z-facing object along local direction (x,z). */
function facingY(dir: { x: number; z: number }): number {
  return Math.atan2(dir.x, dir.z);
}

/** Position from footprint axes: `au` along u (long), `av` along v (short). */
function fpPoint(
  fp: HouseGeometry["footprint"],
  au: number,
  av: number,
  y: number,
): Vec3 {
  return [au * fp.u.x + av * fp.v.x, y, au * fp.u.z + av * fp.v.z];
}

/**
 * Resolve all four module anchors from the built house geometry. Positions scale
 * with the footprint; the toy renderer reads these and draws the props.
 */
export function moduleSlots(geo: HouseGeometry): Record<ModuleKind, ModuleSlot> {
  const fp = geo.footprint;
  const L = fp.halfLong;
  const W = fp.halfShort;

  return {
    // ☀️ Solar panel — free-standing tilted 6-panel ground row in the front yard,
    // pushed ~3 m off the +v (south) wall so its depth clears the heat pump that
    // hugs the wall at the −u end. Nudged toward +u so the row doesn't sit in
    // front of the pump. Base on the ground (y=0); the tilt lives in the rack
    // mesh. rotationY aims the rack's +z "front" outward (toward the camera) and
    // the panels' +TILT turns the glass to face it.
    pv: {
      kind: "pv",
      position: fpPoint(fp, 0.45 * L, W + 3.6, 0),
      rotationY: facingY(fp.v),
    },
    // All three ground/wall props live on the two camera-facing faces (south +v
    // and east +u) so they read from the default view without orbiting.

    // ♨️ Heat pump — on the ground in the yard off the +v (south) wall, −u end.
    heat_pump: {
      kind: "heat_pump",
      position: fpPoint(fp, -0.35 * L, W + 0.9, 0),
      rotationY: facingY(fp.v), // fan faces +v, away from the house
    },
    // 🔋 Battery — wall-mounted on the +v (south) wall, pushed to the −u end so it
    // sits to the left of the heat pump (which stands on the ground at −0.45 L of
    // the same wall). Both read together on the default camera-facing south face.
    battery: {
      kind: "battery",
      position: fpPoint(fp, -0.81 * L, W, 1.5),
      rotationY: facingY(fp.v),
    },
    // 🚗 EV charger — wall-mounted on the +u (east / right-facing) short wall,
    // centred along it, so it lives on the side of the house rather than the
    // camera-facing south front. Faces +u, away from the house.
    ev: {
      kind: "ev",
      position: fpPoint(fp, L, 0, 1.4),
      rotationY: facingY(fp.u),
    },
  };
}
