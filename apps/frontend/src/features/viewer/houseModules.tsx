// Toy module layer — the four toggleable energy props (☀️ pv, 🔋 battery,
// ♨️ heat_pump, 🚗 ev) attached to the generated house. Pure presentation:
// anchors come from moduleSlots() in roofGeometry.ts. Spec: data/3d_modules.md.
//
// Each module is built from plain three primitives, rendered inside the <House>
// group (so it rises with the extrude-up), and plays a subtle looping animation.
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { ModuleSlot, RoofPlacementSurface } from "@/features/viewer/roofGeometry";

/** Centroid of a list of [x,y,z] points. */
function centroidOf(pts: readonly [number, number, number][]): [number, number, number] {
  const s = pts.reduce(
    (a, p) => [a[0] + p[0], a[1] + p[1], a[2] + p[2]] as [number, number, number],
    [0, 0, 0] as [number, number, number],
  );
  return [s[0] / pts.length, s[1] / pts.length, s[2] / pts.length];
}

/**
 * One attached module. Positions to its slot anchor, plays a short drop +
 * scale-in on mount, then holds.
 *
 * `pv` is special: instead of a single body it lays a whole solar array flush on
 * the roof plane. The array works in the untransformed house frame (its panel
 * positions come straight from the roof-surface vertices), so the wrapper sits at
 * the roof centroid with no rotation — the scale-in then "blooms" from the centre
 * of the roof. Every other module is a single body rotated so its +z faces out.
 */
export default function HouseModule({ slot }: { slot: ModuleSlot }) {
  const group = useRef<THREE.Group>(null);
  const t = useRef(0); // mount progress seconds

  const isArray = slot.kind === "pv" && !!slot.surface;
  const anchor = useMemo<[number, number, number]>(
    () => (isArray ? centroidOf(slot.surface!.vertices) : slot.position),
    [isArray, slot],
  );

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    if (t.current < 1) {
      t.current = Math.min(1, t.current + delta * 2.2); // ~0.45 s
      const e = 1 - Math.pow(1 - t.current, 3); // ease-out cubic
      g.scale.setScalar(e);
      g.position.y = anchor[1] + (1 - e) * 0.6; // drop into place
    }
  });

  return (
    <group
      ref={group}
      position={anchor}
      rotation={isArray ? [0, 0, 0] : [0, slot.rotationY, 0]}
      scale={0.001}
    >
      {isArray ? (
        <SolarArray surface={slot.surface!} center={anchor} />
      ) : (
        <ModuleBody slot={slot} />
      )}
    </group>
  );
}

// Oversized-showcase scale factors — chunky, clearly-visible gadgets rather than
// real proportions against the ~10 m house. Heat pump scales from its ground base
// (local y=0), the wall slabs from their centre, so anchors stay put.
function ModuleBody({ slot }: { slot: ModuleSlot }) {
  switch (slot.kind) {
    case "heat_pump":
      return (
        <group scale={1.9}>
          <HeatPump />
        </group>
      );
    case "battery":
      return (
        <group scale={1.7}>
          <Battery />
        </group>
      );
    case "ev":
      return (
        <group scale={2.0}>
          <EvCharger />
        </group>
      );
    default:
      return null;
  }
}

// ── ☀️ Solar array ─────────────────────────────────────────────────────────────
// A grid of oversized glassy panels laid flush on the sun-facing roof plane. The
// layout is derived from the roof surface's quad vertices: two adjacent edges
// give the in-plane axes (eave + up-slope), and we tile the parallelogram with a
// margin so the array fills ~88 % of the roof. Silver frames give it hard
// contrast against the slate-blue roof; the glass shares one animated material
// that "glints" on a slow sine.
//
// NOTE: this tiles the single sun-facing surface, which covers the roof type
// shown in the demo. Per-roof-type layouts (gable's two planes, hip's four) are a
// follow-up — see data/3d_modules.md.
function SolarArray({
  surface,
  center,
}: {
  surface: RoofPlacementSurface;
  center: [number, number, number];
}) {
  const glass = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#0a2342",
        emissive: "#6aa6e8",
        emissiveIntensity: 0.16,
        roughness: 0.16,
        metalness: 0.3,
      }),
    [],
  );
  const frame = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#dbe2ec",
        roughness: 0.4,
        metalness: 0.6,
      }),
    [],
  );
  const busbar = useMemo(
    () =>
      new THREE.MeshStandardMaterial({ color: "#11305a", roughness: 0.5 }),
    [],
  );
  const t = useRef(0);

  useFrame((_, delta) => {
    t.current += delta;
    glass.emissiveIntensity = 0.1 + 0.16 * (0.5 + 0.5 * Math.sin(t.current * 1.1));
  });

  // Lay out the panel grid in the roof plane, relative to the group origin
  // (the roof centroid `center`).
  const panels = useMemo(() => {
    const c = new THREE.Vector3(...center);
    const v = surface.vertices.map((p) => new THREE.Vector3(...p));
    // Two adjacent edges of the quad span the plane.
    const edgeA = v[1].clone().sub(v[0]); // eave-ish
    const edgeB = (v[3] ?? v[2]).clone().sub(v[0]); // up-slope-ish
    const lenA = edgeA.length();
    const lenB = edgeB.length();
    const n = new THREE.Vector3(...surface.normal).normalize();

    // Orthonormal panel basis: local +y = roof normal, +x along edgeA, +z in-plane.
    const xAxis = edgeA.clone().normalize();
    xAxis.sub(n.clone().multiplyScalar(n.dot(xAxis))).normalize();
    const zAxis = new THREE.Vector3().crossVectors(n, xAxis).normalize();
    const quat = new THREE.Quaternion().setFromRotationMatrix(
      new THREE.Matrix4().makeBasis(xAxis, n, zAxis),
    );
    const q: [number, number, number, number] = [quat.x, quat.y, quat.z, quat.w];

    // Oversized panels: aim for ~2.4 m cells, fill 88 % of the plane.
    const m = 0.06; // margin fraction per side
    const cols = Math.max(2, Math.round(lenA / 2.4));
    const rows = Math.max(2, Math.round(lenB / 2.4));
    const cellW = ((1 - 2 * m) * lenA) / cols;
    const cellH = ((1 - 2 * m) * lenB) / rows;
    const panelW = cellW * 0.9;
    const panelH = cellH * 0.9;
    const lift = 0.12;

    const out: {
      key: string;
      pos: [number, number, number];
      panelW: number;
      panelH: number;
    }[] = [];
    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        const s = m + ((i + 0.5) / cols) * (1 - 2 * m);
        const tt = m + ((j + 0.5) / rows) * (1 - 2 * m);
        const p = v[0]
          .clone()
          .add(edgeA.clone().multiplyScalar(s))
          .add(edgeB.clone().multiplyScalar(tt))
          .add(n.clone().multiplyScalar(lift))
          .sub(c);
        out.push({ key: `${i}-${j}`, pos: [p.x, p.y, p.z], panelW, panelH });
      }
    }
    return { panels: out, q };
  }, [surface, center]);

  const TH = 0.16; // oversized panel thickness

  return (
    <group>
      {panels.panels.map(({ key, pos, panelW, panelH }) => (
        <group key={key} position={pos} quaternion={panels.q}>
          {/* Silver frame slab. */}
          <mesh material={frame} castShadow receiveShadow>
            <boxGeometry args={[panelW, TH, panelH]} />
          </mesh>
          {/* Glass face, inset and proud of the frame. */}
          <mesh position={[0, TH * 0.55, 0]} material={glass} castShadow>
            <boxGeometry args={[panelW * 0.9, TH * 0.5, panelH * 0.9]} />
          </mesh>
          {/* Centre busbar for a touch of cell detail. */}
          <mesh position={[0, TH * 0.83, 0]} material={busbar}>
            <boxGeometry args={[panelW * 0.9, TH * 0.12, panelH * 0.04]} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

// ── ♨️ Heat pump ───────────────────────────────────────────────────────────────
// Outdoor condenser box with a recessed spinning fan on the outward (+z) face,
// a gentle "pumping" breathe, and a glowing hub. Base sits on the ground (y=0).
function HeatPump() {
  const housing = useRef<THREE.Group>(null);
  const blades = useRef<THREE.Group>(null);
  const hub = useRef<THREE.MeshStandardMaterial>(null);
  const t = useRef(0);

  useFrame((_, delta) => {
    t.current += delta;
    if (blades.current) blades.current.rotation.z += delta * 6; // continuous spin
    if (housing.current) {
      // "Pumping" breathe: ±2 % vertical scale.
      housing.current.scale.y = 1 + 0.02 * Math.sin(t.current * 2.4);
    }
    if (hub.current) {
      hub.current.emissiveIntensity =
        0.2 + 0.25 * (0.5 + 0.5 * Math.sin(t.current * 2.4));
    }
  });

  const blade = useMemo(() => [0, 1, 2, 3, 4].map((i) => (i * Math.PI * 2) / 5), []);

  return (
    <group>
      {/* Pipe stub into the wall (−z, behind the unit). */}
      <mesh position={[0.3, 0.45, -0.25]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.04, 0.04, 0.3, 12]} />
        <meshStandardMaterial color="#b9c0c9" roughness={0.5} metalness={0.5} />
      </mesh>
      <group ref={housing}>
        {/* Casing — base on ground, so centre at half-height. */}
        <mesh position={[0, 0.45, 0]} castShadow receiveShadow>
          <boxGeometry args={[1.0, 0.9, 0.4]} />
          <meshStandardMaterial color="#8a96a4" roughness={0.6} metalness={0.2} />
        </mesh>
        {/* Fan housing — recessed dark ring on the +z face. */}
        <mesh position={[0, 0.45, 0.205]} rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[0.37, 0.37, 0.06, 32]} />
          <meshStandardMaterial color="#2b3440" roughness={0.7} />
        </mesh>
        {/* Spinning blades around the +z axis. */}
        <group ref={blades} position={[0, 0.45, 0.235]}>
          {blade.map((a, i) => (
            <mesh key={i} rotation={[0, 0, a]}>
              <boxGeometry args={[0.07, 0.6, 0.02]} />
              <meshStandardMaterial color="#cfd6de" roughness={0.5} metalness={0.3} />
            </mesh>
          ))}
          {/* Hub. */}
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.08, 0.08, 0.05, 16]} />
            <meshStandardMaterial
              ref={hub}
              color="#3a4350"
              emissive="#6fd0ff"
              emissiveIntensity={0.25}
              roughness={0.4}
            />
          </mesh>
        </group>
      </group>
    </group>
  );
}

// ── 🔋 Battery ─────────────────────────────────────────────────────────────────
// Wall-mounted Powerwall-style slab. A charge bar fills 0→100 % over ~3 s and
// holds; a side LED strip breathes. Anchor y is the slab centre.
function Battery() {
  const fill = useRef<THREE.Group>(null);
  const led = useRef<THREE.MeshStandardMaterial>(null);
  const t = useRef(0);

  useFrame((_, delta) => {
    t.current += delta;
    if (fill.current) {
      const charge = Math.min(1, t.current / 3); // fill over 3 s, then hold
      fill.current.scale.y = Math.max(0.001, charge);
    }
    if (led.current) {
      led.current.emissiveIntensity = 0.3 + 0.3 * (0.5 + 0.5 * Math.sin(t.current * 2));
    }
  });

  return (
    <group position={[0, 0, 0.1]}>
      {/* Shell — pushed out half its depth so it sits on the wall. */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[0.75, 1.2, 0.2]} />
        <meshStandardMaterial color="#36444f" roughness={0.5} metalness={0.15} />
      </mesh>
      {/* Charge bar — grows upward from its bottom pivot. */}
      <group ref={fill} position={[0, -0.5, 0.11]} scale={[1, 0.001, 1]}>
        <mesh position={[0, 0.5, 0]}>
          <boxGeometry args={[0.16, 1.0, 0.02]} />
          <meshStandardMaterial
            color="#34d27b"
            emissive="#34d27b"
            emissiveIntensity={0.5}
            roughness={0.4}
          />
        </mesh>
      </group>
      {/* LED status strip down the right edge. */}
      <mesh position={[0.33, 0, 0.11]}>
        <boxGeometry args={[0.03, 1.05, 0.02]} />
        <meshStandardMaterial
          ref={led}
          color="#1f8a52"
          emissive="#34d27b"
          emissiveIntensity={0.35}
          roughness={0.4}
        />
      </mesh>
    </group>
  );
}

// ── 🚗 EV charger ──────────────────────────────────────────────────────────────
// Compact wallbox with a glowing LED ring (breathing + a travelling dot) and a
// curled hanging cable. Anchor y is the box centre.
function EvCharger() {
  const ring = useRef<THREE.MeshStandardMaterial>(null);
  const dot = useRef<THREE.Group>(null);
  const t = useRef(0);
  const ringR = 0.1;

  useFrame((_, delta) => {
    t.current += delta;
    if (ring.current) {
      ring.current.emissiveIntensity = 0.5 + 0.4 * (0.5 + 0.5 * Math.sin(t.current * 1.6));
    }
    if (dot.current) dot.current.rotation.z = -t.current * 1.8; // travelling dot
  });

  const cable = useMemo(() => {
    // A short curled cable hanging off the right side.
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0.18, -0.05, 0.06),
      new THREE.Vector3(0.26, -0.18, 0.08),
      new THREE.Vector3(0.2, -0.32, 0.05),
      new THREE.Vector3(0.08, -0.36, 0.04),
    ]);
    return new THREE.TubeGeometry(curve, 24, 0.022, 8, false);
  }, []);

  return (
    <group position={[0, 0, 0.075]}>
      {/* Wallbox shell. */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[0.4, 0.3, 0.15]} />
        <meshStandardMaterial color="#27313c" roughness={0.6} metalness={0.2} />
      </mesh>
      {/* LED ring on the +z face. */}
      <mesh position={[0, 0, 0.08]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[ringR, 0.015, 12, 32]} />
        <meshStandardMaterial
          ref={ring}
          color="#0b3b52"
          emissive="#46c8ff"
          emissiveIntensity={0.6}
          roughness={0.4}
        />
      </mesh>
      {/* Travelling dot orbiting the ring. */}
      <group ref={dot} position={[0, 0, 0.085]}>
        <mesh position={[ringR, 0, 0]}>
          <sphereGeometry args={[0.022, 12, 12]} />
          <meshStandardMaterial
            color="#bdecff"
            emissive="#9ad9ff"
            emissiveIntensity={1.2}
            roughness={0.3}
          />
        </mesh>
      </group>
      {/* Curled cable. */}
      <mesh geometry={cable} castShadow>
        <meshStandardMaterial color="#1b1f24" roughness={0.7} />
      </mesh>
    </group>
  );
}
