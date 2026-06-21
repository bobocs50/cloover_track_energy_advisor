// Toy module layer — the four toggleable energy props (☀️ pv, 🔋 battery,
// ♨️ heat_pump, 🚗 ev) attached to the generated house. Pure presentation:
// anchors come from moduleSlots() in roofGeometry.ts. Spec: data/3d_modules.md.
//
// Each module is built from plain three primitives, rendered inside the <House>
// group (so it rises with the extrude-up), and plays a subtle looping animation.
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { ModuleSlot } from "@/features/viewer/roofGeometry";

/**
 * One attached module. Positions to its slot anchor, plays a short drop +
 * scale-in on mount, then holds. Every module is a single body rotated so its
 * +z "front" faces outward (toward the default camera view).
 */
export default function HouseModule({ slot }: { slot: ModuleSlot }) {
  const group = useRef<THREE.Group>(null);
  const t = useRef(0); // mount progress seconds

  const anchor = slot.position;

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
    <group ref={group} position={anchor} rotation={[0, slot.rotationY, 0]} scale={0.001}>
      <ModuleBody slot={slot} />
    </group>
  );
}

// Oversized-showcase scale factors — chunky, clearly-visible gadgets rather than
// real proportions against the ~10 m house. Heat pump scales from its ground base
// (local y=0), the wall slabs from their centre, so anchors stay put.
function ModuleBody({ slot }: { slot: ModuleSlot }) {
  switch (slot.kind) {
    case "pv":
      return <GroundSolarArray />;
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
      return <EvBay />;
    default:
      return null;
  }
}

// ── ☀️ Ground solar array ───────────────────────────────────────────────────────
// A free-standing tilted rack of glassy panels in a single row, sitting on the
// ground in the front yard (no roof, no cable). Fixed size — its height does NOT
// scale with the house. Each panel tilts ~32° about the local x-axis so its low
// (front) edge rests near the ground and the glass leans back-and-up to FACE the
// viewer: the wrapper's rotationY (from moduleSlots) aims the rack's +z "front"
// outward toward the default camera, and the +TILT pitch turns the glass to meet
// it. Silver frames + an animated glassy glint echo the other modules. y=0 ground.
function GroundSolarArray() {
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
    () => new THREE.MeshStandardMaterial({ color: "#11305a", roughness: 0.5 }),
    [],
  );
  const strut = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#9aa3ad",
        roughness: 0.5,
        metalness: 0.55,
      }),
    [],
  );
  const t = useRef(0);

  useFrame((_, delta) => {
    t.current += delta;
    glass.emissiveIntensity = 0.1 + 0.16 * (0.5 + 0.5 * Math.sin(t.current * 1.1));
  });

  // Fixed panel + rack dimensions (metres) — never scaled by the house.
  const PANELS = 6; // one row of six, facing the viewer
  const PANEL_W = 0.86; // each panel's width along the row (x)
  const PANEL_H = 1.5; // up the slope
  const TH = 0.07; // panel thickness
  const GAP = 0.07; // gap between adjacent panels
  const TILT = (32 * Math.PI) / 180; // tilt about x so the glass faces the camera
  const CLR = 0.06; // ground clearance under the low (front) edge

  // Geometry of the tilted plane. +TILT pitches each panel so its FRONT (+z,
  // camera-side) edge drops near the ground and its BACK (−z) edge lifts — the
  // glass normal swings from +y toward +z to meet the viewer. The slab centre
  // rides half a slope-rise up so the front edge floats just off the grass.
  const half = PANEL_H / 2;
  const slabY = half * Math.sin(TILT) + CLR;
  const frontZ = half * Math.cos(TILT); // low edge, toward camera (+z)
  const backZ = -half * Math.cos(TILT); // high edge, toward house (−z)

  // Back support legs reach from the ground up to each panel's high (back) edge.
  const legTopY = PANEL_H * Math.sin(TILT) + CLR;

  // Centre the row on x: panel i sits at xs[i].
  const pitch = PANEL_W + GAP;
  const xs = Array.from({ length: PANELS }, (_, i) => (i - (PANELS - 1) / 2) * pitch);
  const railLen = (PANELS - 1) * pitch + PANEL_W + 0.18;

  // Two parallel rows separated along the slope axis (local z). The row footprint
  // is ~PANEL_H·cos(TILT) deep; ROW_PITCH leaves a clear walkway between them. The
  // pair straddles the anchor, so the array grows symmetrically into the yard.
  const ROW_PITCH = 2.4;
  const rowZs = [-ROW_PITCH / 2, ROW_PITCH / 2];

  const renderRow = (rowZ: number) => (
    <group key={rowZ} position={[0, 0, rowZ]}>
      {/* Row of panels on the tilted plane, glass facing the camera. */}
      {xs.map((x) => (
        <group key={x} position={[x, slabY, 0]} rotation={[TILT, 0, 0]}>
          {/* Silver frame slab. */}
          <mesh material={frame} castShadow receiveShadow>
            <boxGeometry args={[PANEL_W, TH, PANEL_H]} />
          </mesh>
          {/* Glass face, proud of the frame (along the panel normal = +y). */}
          <mesh position={[0, TH * 0.6, 0]} material={glass} castShadow>
            <boxGeometry args={[PANEL_W * 0.9, TH * 0.5, PANEL_H * 0.9]} />
          </mesh>
          {/* Centre busbar for a touch of cell detail. */}
          <mesh position={[0, TH * 0.9, 0]} material={busbar}>
            <boxGeometry args={[PANEL_W * 0.9, TH * 0.12, PANEL_H * 0.04]} />
          </mesh>
        </group>
      ))}

      {/* Rear support legs (one under each panel's high back edge). */}
      {xs.map((x) => (
        <mesh
          key={`leg-${x}`}
          material={strut}
          position={[x, legTopY / 2, backZ * 0.55]}
          castShadow
        >
          <boxGeometry args={[0.06, legTopY, 0.06]} />
        </mesh>
      ))}

      {/* Front ground rail under the low (camera-side) edge. */}
      <mesh material={strut} position={[0, 0.05, frontZ]} castShadow receiveShadow>
        <boxGeometry args={[railLen, 0.1, 0.1]} />
      </mesh>
      {/* Rear ground rail tying the legs together. */}
      <mesh material={strut} position={[0, 0.05, backZ]} castShadow receiveShadow>
        <boxGeometry args={[railLen, 0.1, 0.1]} />
      </mesh>
    </group>
  );

  return <group>{rowZs.map(renderRow)}</group>;
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

// ── 🚗 EV bay (wallbox + plugged-in car) ─────────────────────────────────────────
// The "ev" module is one unit: the wallbox on the right-facing wall plus a modern
// red electric car parked alongside it in the yard and a charge cable bridging the
// two. Local frame (from the slot's rotationY = facingY(fp.u)): +z points outward
// from the wall into the yard, the wall sits at z≈0, and local y=0 is 1.4 m up the
// wall (the wallbox centre). The ground is therefore at local y ≈ −1.4.
function EvBay() {
  // Cable from the wallbox down to the car's wall-side charge port. Drawn in the
  // bay frame so it spans the (separately scaled) charger and car cleanly.
  const link = useMemo(() => {
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0.16, -0.72, 0.16), // off the wallbox, lower edge
      new THREE.Vector3(0.0, -1.06, 0.55), // sag toward the ground
      new THREE.Vector3(-0.55, -1.0, 0.95),
      new THREE.Vector3(-1.04, -0.74, 1.0), // into the car's charge port
    ]);
    return new THREE.TubeGeometry(curve, 32, 0.03, 8, false);
  }, []);

  return (
    <group>
      <group scale={2.0}>
        <EvCharger />
      </group>
      {/* Car parked parallel to the wall, ~1.8 m out in the yard, wheels on the
          ground (local y = −1.4). Its long axis runs along local x, so the
          camera-facing (+z, outward) long side is the driver's side and the
          wall-facing (−z) side carries the charge port. */}
      <group position={[0, -1.4, 1.8]}>
        <RedCar />
      </group>
      {/* Charge cable bridging wallbox → car port. */}
      <mesh geometry={link} castShadow>
        <meshStandardMaterial color="#15181c" roughness={0.75} />
      </mesh>
    </group>
  );
}

// A compact modern electric car: smooth one-box body, glassy greenhouse, full-width
// light bars front and rear, dark alloy wheels, and a glowing charge port on its
// wall-facing (−z) side. Built at real-ish metres; length runs along local x.
function RedCar() {
  const port = useRef<THREE.MeshStandardMaterial>(null);
  const t = useRef(0);

  useFrame((_, delta) => {
    t.current += delta;
    if (port.current) {
      // Breathe the charge-port glow to read as "charging".
      port.current.emissiveIntensity = 0.5 + 0.5 * (0.5 + 0.5 * Math.sin(t.current * 1.8));
    }
  });

  const LEN = 3.8; // along x
  const WID = 1.78; // along z
  const WR = 0.36; // wheel radius
  const halfW = WID / 2;

  // Four wheels: axis along z (rotate the cylinder's default +y axis onto z).
  const wheels: [number, number][] = [
    [LEN * 0.31, halfW - 0.02],
    [LEN * 0.31, -(halfW - 0.02)],
    [-LEN * 0.31, halfW - 0.02],
    [-LEN * 0.31, -(halfW - 0.02)],
  ];

  return (
    <group>
      {/* Lower body. */}
      <mesh position={[0, 0.62, 0]} castShadow receiveShadow>
        <boxGeometry args={[LEN, 0.56, WID]} />
        <meshStandardMaterial color="#d62828" roughness={0.32} metalness={0.5} />
      </mesh>
      {/* Hood / trunk taper — a slightly narrower deck for a modern profile. */}
      <mesh position={[0, 0.92, 0]} castShadow receiveShadow>
        <boxGeometry args={[LEN * 0.86, 0.18, WID * 0.9]} />
        <meshStandardMaterial color="#c81f1f" roughness={0.32} metalness={0.5} />
      </mesh>
      {/* Rocker / lower skirt. */}
      <mesh position={[0, 0.34, 0]} castShadow>
        <boxGeometry args={[LEN * 0.97, 0.2, WID * 0.94]} />
        <meshStandardMaterial color="#2a2d31" roughness={0.7} metalness={0.2} />
      </mesh>
      {/* Glassy greenhouse band (windshield + side windows). */}
      <mesh position={[-0.12, 1.18, 0]} castShadow>
        <boxGeometry args={[LEN * 0.5, 0.46, WID * 0.84]} />
        <meshStandardMaterial
          color="#10141a"
          roughness={0.15}
          metalness={0.4}
          emissive="#1b2a3a"
          emissiveIntensity={0.12}
        />
      </mesh>
      {/* Body-colour roof cap. */}
      <mesh position={[-0.12, 1.43, 0]} castShadow receiveShadow>
        <boxGeometry args={[LEN * 0.44, 0.1, WID * 0.78]} />
        <meshStandardMaterial color="#d62828" roughness={0.32} metalness={0.5} />
      </mesh>
      {/* Full-width front light bar (front = +x). */}
      <mesh position={[LEN / 2 - 0.03, 0.72, 0]}>
        <boxGeometry args={[0.06, 0.1, WID * 0.82]} />
        <meshStandardMaterial
          color="#eaf4ff"
          emissive="#cfe6ff"
          emissiveIntensity={0.9}
          roughness={0.3}
        />
      </mesh>
      {/* Full-width rear light bar. */}
      <mesh position={[-LEN / 2 + 0.03, 0.74, 0]}>
        <boxGeometry args={[0.06, 0.12, WID * 0.84]} />
        <meshStandardMaterial
          color="#7a0c12"
          emissive="#ff2a2a"
          emissiveIntensity={0.8}
          roughness={0.3}
        />
      </mesh>
      {/* Wheels — dark alloys, axis laid along z so they sit on the ground. */}
      {wheels.map(([x, z], i) => (
        <group key={i} position={[x, WR, z]} rotation={[Math.PI / 2, 0, 0]}>
          <mesh castShadow>
            <cylinderGeometry args={[WR, WR, 0.26, 24]} />
            <meshStandardMaterial color="#15171a" roughness={0.8} />
          </mesh>
          {/* Hub face. */}
          <mesh position={[0, 0.14, 0]}>
            <cylinderGeometry args={[WR * 0.55, WR * 0.55, 0.04, 16]} />
            <meshStandardMaterial color="#9aa3ad" roughness={0.4} metalness={0.7} />
          </mesh>
        </group>
      ))}
      {/* Charge port on the wall-facing (−z) side, toward the rear. Glows while
          the link cable plugs in. */}
      <mesh position={[-LEN * 0.26, 0.74, -halfW - 0.01]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.09, 0.09, 0.04, 20]} />
        <meshStandardMaterial
          ref={port}
          color="#0b3b52"
          emissive="#46c8ff"
          emissiveIntensity={0.7}
          roughness={0.4}
        />
      </mesh>
    </group>
  );
}
