// Phase 4B — R3F canvas (light Pactum theme). Renders the generated house with
// a soft extrude-up animation, a grounded contact shadow, lighting and orbit
// controls. Pure presentation: geometry comes from buildHouseGeometry().
import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, ContactShadows } from "@react-three/drei";
import * as THREE from "three";
import type { LatLng } from "@/features/roof/useMapboxDraw";
import type { RoofParams } from "@/features/roof/RoofParamsStep";
import {
  buildHouseGeometry,
  moduleSlots,
  type GeometryKind,
  type ModuleKind,
  type ModuleSlot,
} from "@/features/viewer/roofGeometry";
import HouseModule from "@/features/viewer/houseModules";

const MODULE_KINDS: ModuleKind[] = ["pv", "battery", "heat_pump", "ev"];

function House({
  geometries,
  kinds,
  slots,
  addons,
}: {
  geometries: THREE.BufferGeometry[];
  kinds: GeometryKind[];
  slots: Record<ModuleKind, ModuleSlot>;
  addons: Record<ModuleKind, boolean>;
}) {
  const group = useRef<THREE.Group>(null);

  // Extrude-up: lerp the group's vertical scale 0 → 1 over ~1s.
  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    if (g.scale.y < 1) {
      g.scale.y = Math.min(1, g.scale.y + delta * 1.4);
    }
  });

  const wall = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#f4f6f9", // near-white walls
        roughness: 0.85,
        metalness: 0,
        side: THREE.DoubleSide,
      }),
    [],
  );
  const roof = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#3f5b8b", // slate-blue roof for contrast
        roughness: 0.6,
        metalness: 0,
        side: THREE.DoubleSide,
      }),
    [],
  );

  return (
    <group ref={group} scale={[1, 0.001, 1]}>
      {geometries.map((geo, i) => (
        <mesh
          key={i}
          geometry={geo}
          material={kinds[i] === "roof" ? roof : wall}
          castShadow
          receiveShadow
        />
      ))}
      {/* Toy module layer — rises with the house's extrude-up animation. */}
      {MODULE_KINDS.filter((k) => addons[k]).map((k) => (
        <HouseModule key={k} slot={slots[k]} />
      ))}
    </group>
  );
}

export interface HouseCanvasProps {
  polygon: LatLng[] | null;
  params: RoofParams;
  addons?: Record<ModuleKind, boolean>;
}

const NO_ADDONS: Record<ModuleKind, boolean> = {
  pv: false,
  battery: false,
  heat_pump: false,
  ev: false,
};

export default function HouseCanvas({ polygon, params, addons }: HouseCanvasProps) {
  const house = useMemo(() => buildHouseGeometry(polygon, params), [polygon, params]);
  const { geometries, kinds, bounds } = house;
  const slots = useMemo(() => moduleSlots(house), [house]);
  const enabled = addons ?? NO_ADDONS;

  // Frame the camera relative to the footprint size — pulled back for a clean
  // 3/4 view that fits the whole house with headroom.
  const reach = Math.max(bounds.halfLongM, bounds.halfShortM, 4);
  // Start ~10 % further back than the snug framing — the previous view sat too
  // tight — then pull back another 15 % so the ground solar array clears frame.
  const camPos: [number, number, number] = [reach * 2.4, reach * 2.02, reach * 3.42];

  return (
    <Canvas
      shadows
      camera={{ fov: 42, position: camPos, near: 0.1, far: 400 }}
      dpr={[1, 2]}
      gl={{ antialias: true }}
    >
      <color attach="background" args={["#eef1f5"]} />

      <ambientLight intensity={0.85} />
      <hemisphereLight args={["#ffffff", "#c8cfd8", 0.6]} />
      <directionalLight
        position={[reach, reach * 2.2, reach * 1.4]}
        intensity={1.6}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={0.5}
        shadow-camera-far={reach * 8}
        shadow-camera-left={-reach * 2}
        shadow-camera-right={reach * 2}
        shadow-camera-top={reach * 2}
        shadow-camera-bottom={-reach * 2}
      />

      {/* Light ground plane + soft contact shadow under the house. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[reach * 12, reach * 12]} />
        <meshStandardMaterial color="#d8dde4" roughness={1} />
      </mesh>
      <ContactShadows
        position={[0, 0.02, 0]}
        scale={reach * 4}
        blur={2.4}
        opacity={0.35}
        far={reach * 2}
      />

      <House geometries={geometries} kinds={kinds} slots={slots} addons={enabled} />

      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        enablePan={false}
        minDistance={reach * 1.2}
        maxDistance={reach * 6}
        maxPolarAngle={Math.PI / 2.05}
        target={[0, bounds.ridgeHeightM * 0.5 + 1.2, 0]}
      />
    </Canvas>
  );
}
