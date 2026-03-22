import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import useRealtimeTable from '../hooks/useRealtimeTable';
import {
  effectiveMapStatus,
  bayIsActivelyCharging,
} from '../lib/mapTruckStatus';

<<<<<<< Updated upstream
/** Approach + UI offsets — idle berth centers come from `getIdleCenterForTruck` (pier Y1…Y11). */
const TRUCK_PATHS = {
  amazon_truck: {
    approachPosition: { x: 175, y: 275 },
    tooltipOffset: { x: 20, y: -50 },
    driftDuration: 4.2,
  },
  fedex_truck: {
    approachPosition: { x: 210, y: 268 },
    tooltipOffset: { x: 20, y: -50 },
    driftDuration: 5.1,
  },
  ups_truck: {
    approachPosition: { x: 265, y: 280 },
    tooltipOffset: { x: -110, y: -50 },
    driftDuration: 3.6,
  },
  dhl_truck: {
    approachPosition: { x: 150, y: 272 },
    tooltipOffset: { x: 20, y: -50 },
    driftDuration: 4.5,
  },
  rivian_truck: {
    approachPosition: { x: 230, y: 285 },
    tooltipOffset: { x: -110, y: -50 },
    driftDuration: 5.8,
  },
  TRUCK_01: {
    approachPosition: { x: 175, y: 275 },
    tooltipOffset: { x: 20, y: -50 },
    driftDuration: 4.2,
  },
  TRUCK_07: {
    approachPosition: { x: 210, y: 268 },
    tooltipOffset: { x: 20, y: -50 },
    driftDuration: 5.1,
  },
  TRUCK_12: {
    approachPosition: { x: 265, y: 280 },
    tooltipOffset: { x: -110, y: -50 },
    driftDuration: 3.6,
  },
  TRUCK_15: {
    approachPosition: { x: 300, y: 272 },
    tooltipOffset: { x: -110, y: -50 },
    driftDuration: 4.8,
  },
  TRUCK_03: {
    approachPosition: { x: 190, y: 260 },
    tooltipOffset: { x: 20, y: -50 },
    driftDuration: 5.5,
  },
=======
// ─── Coordinate Constants ──────────────────────────────────────────────────────

const BAY_POSITIONS_3D = {
  A1: { x: -20, z: -20 },
  A2: { x:  -7, z: -20 },
  B1: { x:   7, z: -20 },
  B2: { x:  20, z: -20 },
};

// Pier T (west) container stack anchors
const PIER_T_STACKS = [
  { x:  -90, z: -50 },
  { x:  -90, z: -20 },
  { x:  -90, z:  10 },
  { x: -115, z: -38 },
  { x: -115, z:   5 },
];

// Pier E (east) container stack anchors
const PIER_E_STACKS = [
  { x:  70, z: -50 },
  { x:  70, z: -20 },
  { x:  70, z:  10 },
  { x:  95, z: -38 },
  { x:  95, z:   5 },
];

// Gantry crane base positions
const CRANE_POSITIONS = [
  { x: -105, z: -28 },
  { x:    0, z: -90 },
  { x:  105, z: -28 },
];

// ISO container colours
const CONTAINER_COLORS = [
  0xc0392b, 0x2980b9, 0x16a085, 0xf39c12,
  0x8e44ad, 0x27ae60, 0xd35400, 0x1a5276,
];

const TRUCK_COLORS = [0xf59e0b, 0x8b5cf6, 0x3b82f6, 0x10b981, 0xef4444];

// ─── SoC Label Helpers (CanvasTexture) ────────────────────────────────────────

function makeSocCanvas() {
  const c = document.createElement('canvas');
  c.width  = 160;
  c.height =  56;
  return c;
>>>>>>> Stashed changes
}

function drawSocLabel(canvas, soc) {
  const ctx  = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Dark pill background
  ctx.fillStyle = 'rgba(8, 10, 20, 0.82)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const pct   = soc != null ? Math.round(soc) : null;
  const label = pct != null ? `\u26a1 ${pct}%` : '\u26a1 --';
  const color = pct == null  ? '#94a3b8'
              : pct > 70     ? '#22c55e'
              : pct > 30     ? '#eab308'
              :                '#ef4444';

  // Coloured border
  ctx.strokeStyle = color;
  ctx.lineWidth   = 3;
  ctx.strokeRect(2, 2, canvas.width - 4, canvas.height - 4);

  // Label text
  ctx.fillStyle    = color;
  ctx.font         = 'bold 26px sans-serif';
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, canvas.width / 2, canvas.height / 2);
}

// ─── Misc Helper ──────────────────────────────────────────────────────────────

function latestReasoningForTruck(powerBids, truckId) {
  const list = (powerBids ?? []).filter((b) => b.truck_id === truckId);
  list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  return list[0]?.reasoning || 'Waiting for auction...';
}

// ─── Component ─────────────────────────────────────────────────────────────────

export default function TerminalMap({ powerBids, demo, style }) {
  const { rows: trucksDb } = useRealtimeTable('trucks');
  const { rows: baysDb }   = useRealtimeTable('bays');

  const mountRef = useRef(null);
  const [selectedTruckId, setSelectedTruckId] = useState(null);
  const sceneRef = useRef(null);

  const trucks   = demo?.truck ? [demo.truck] : trucksDb;
  const baysRows = demo?.bays  ? demo.bays    : baysDb;

<<<<<<< Updated upstream
/** Tooltip box is ~100px wide — keep copy short so it stays inside the rect. */
const MAP_TOOLTIP_REASON_MAX = 22
const MAP_TOOLTIP_NAME_MAX = 14

function truncateTooltipText(s, maxLen) {
  const t = String(s).trim()
  if (t.length <= maxLen) return t
  return t.slice(0, Math.max(0, maxLen - 1)) + '…'
}

function latestReasoningForTruck(powerBids, truckId, maxLen = 38) {
  const list = (powerBids ?? []).filter((b) => b.truck_id === truckId)
  list.sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )
  const empty = 'Waiting for auction...'
  if (list.length === 0) return truncateTooltipText(empty, maxLen)
  const r = list[0]?.reasoning
  if (r == null || String(r).trim() === '') return truncateTooltipText(empty, maxLen)
  return truncateTooltipText(String(r), maxLen)
}

function resolveTruckPosition(truck, baysRows) {
  const status = effectiveMapStatus(truck, baysRows)
  const idle = getIdleCenterForTruck(truck.name)

  if (status === 'at_port') {
    return { x: EXIT_RIGHT_X, y: idle.y }
  }
  if (status === 'charging') {
    const bay = (baysRows ?? []).find((b) => b.id === truck.bay_id)
    const bayName = bay?.name
    if (bayName && BAY_POSITIONS[bayName]) {
      const p = BAY_POSITIONS[bayName]
      return { x: p.cx, y: p.cy }
    }
    return { x: idle.x, y: idle.y }
  }
  if (status === 'bidding') {
    // Approach from the truck's own pier slot toward the charging zone
    return { x: idle.x, y: idle.y + 20 }
  }
  return { x: idle.x, y: idle.y }
}

function nodeColors(status) {
  const s = (status ?? 'idle').toLowerCase()
  if (s === 'idle') return { fill: '#00ff88', stroke: '#00ff88' }
  if (s === 'bidding') return { fill: '#00aaff', stroke: '#00aaff' }
  if (s === 'charging') return { fill: '#ffaa00', stroke: '#ffaa00' }
  if (s === 'at_port') return { fill: '#6a8aaa', stroke: '#88aacc' }
  if (s === 'done') return { fill: '#3a5a6a', stroke: '#3a5a6a' }
  return { fill: '#00ff88', stroke: '#00ff88' }
}

const svgStyles = `
  @keyframes drift {
    0%, 100% { transform: translate(0, 0); }
    50% { transform: translate(6px, -4px); }
  }
  @keyframes ripple {
    0% { transform: scale(1); opacity: 0.8; }
    100% { transform: scale(2.2); opacity: 0; }
  }
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  @keyframes baylock {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
  }
`

const TOOLTIP_OFFSETS = [
  { x: 20, y: -50 },
  { x: 20, y: -50 },
  { x: -110, y: -50 },
  { x: 20, y: -50 },
  { x: -110, y: -50 },
]

const TRUCK_ORDER = ['amazon_truck', 'fedex_truck', 'ups_truck', 'dhl_truck', 'rivian_truck']

function getTruckTooltipOffset(name) {
  const idx = TRUCK_ORDER.indexOf(name)
  return TOOLTIP_OFFSETS[idx >= 0 ? idx : 0]
}

function TruckNode({ truck, baysRows, powerBids, respawnEpoch = 0 }) {
  const status = effectiveMapStatus(truck, baysRows)
  const idleCenter = getIdleCenterForTruck(truck.name)
  const target = resolveTruckPosition(truck, baysRows)
  const moveMs =
    respawnEpoch > 0 ? 2000 : status === 'at_port' ? 2200 : 1500
  const pos = useSmoothPosition(
    target.x,
    target.y,
    moveMs,
    respawnEpoch,
    respawnEpoch > 0 ? SPAWN_LEFT_X : null,
    respawnEpoch > 0 ? idleCenter.y : null
  )
  const path = getTruckPath(truck.name)
  const off = getTruckTooltipOffset(truck.name)
  const colors = nodeColors(status)
  const drift = `${path?.driftDuration ?? 4}s`
  const reasoning = latestReasoningForTruck(
    powerBids,
    truck.id,
    MAP_TOOLTIP_REASON_MAX
  )
  const nameLabel = truncateTooltipText(String(truck.name ?? ''), MAP_TOOLTIP_NAME_MAX)
  const anchorX = status === 'charging' ? target.x : pos.x
  const anchorY = status === 'charging' ? target.y : pos.y
  const tx = anchorX + off.x
  const ty = anchorY + off.y
  const tw = 100
  const th = 46
  const socDisplay = useSmoothSoc(truck.state_of_charge ?? 0)

  return (
    <g>
      {status === 'bidding' && (
        <circle
          cx={pos.x}
          cy={pos.y}
          r="14"
          fill="none"
          stroke="#00aaff"
          strokeWidth="0.5"
          opacity="0.3"
          style={{
            transformBox: 'fill-box',
            transformOrigin: 'center',
            animation: 'ripple 2s infinite',
          }}
        />
      )}

      {status === 'idle' && (
        <circle
          cx={pos.x}
          cy={pos.y}
          r="6"
          fill="#00ff88"
          style={{
            transformBox: 'fill-box',
            transformOrigin: 'center',
            animation: `drift ${drift} ease-in-out infinite`,
          }}
        />
      )}

      {status === 'bidding' && (
        <circle
          cx={pos.x}
          cy={pos.y}
          r="6"
          fill="#00aaff"
          style={{
            transformBox: 'fill-box',
            transformOrigin: 'center',
            animation: `drift ${drift} ease-in-out infinite`,
          }}
        />
      )}

      {status === 'charging' && (
        <circle
          cx={target.x}
          cy={target.y}
          r="6"
          fill="#ffaa00"
          style={{
            transformBox: 'fill-box',
            transformOrigin: 'center',
            animation: 'blink 1.2s infinite',
          }}
        />
      )}

      {status === 'at_port' && (
        <circle
          cx={pos.x}
          cy={pos.y}
          r="5"
          fill="#88aacc"
          opacity="0.85"
          style={{
            transformBox: 'fill-box',
            transformOrigin: 'center',
            animation: 'drift 3s ease-in-out infinite',
          }}
        />
      )}

      {status === 'done' && (
        <circle cx={pos.x} cy={pos.y} r="6" fill="#3a5a6a" />
      )}

      {!['idle', 'bidding', 'charging', 'at_port', 'done'].includes(status) && (
        <circle
          cx={pos.x}
          cy={pos.y}
          r="6"
          fill="#00ff88"
          style={{
            transformBox: 'fill-box',
            transformOrigin: 'center',
            animation: `drift ${drift} ease-in-out infinite`,
          }}
        />
      )}

      <line
        x1={anchorX}
        y1={anchorY}
        x2={tx + 8}
        y2={ty + th / 2}
        stroke="#00aaff"
        strokeWidth="0.5"
        opacity="0.5"
      />
      <rect
        x={tx}
        y={ty}
        width={tw}
        height={th}
        rx="3"
        fill="#0d1a2e"
        stroke={colors.stroke}
        strokeWidth="0.5"
      />
      <text
        x={tx + 6}
        y={ty + 14}
        fill={colors.fill}
        fontSize="8"
        fontWeight="700"
        fontFamily="Courier New, monospace"
      >
        {nameLabel}
      </text>
      <text
        x={tx + 6}
        y={ty + 26}
        fill={socBarFill(socDisplay)}
        fontSize="8"
        fontFamily="Courier New, monospace"
      >
        {socBarText(socDisplay)}
      </text>
      <text
        x={tx + tw - 6}
        y={ty + 26}
        textAnchor="end"
        fill="#6a8aaa"
        fontSize="7"
        fontFamily="Courier New, monospace"
      >
        {formatSocPercent(socDisplay)}
      </text>
      <text
        x={tx + 6}
        y={ty + 38}
        fill="#3a7aaa"
        fontSize="7"
        fontFamily="Courier New, monospace"
      >
        {reasoning}
      </text>
    </g>
  )
}

export default function TerminalMap({ powerBids, style, demo }) {
  const { rows: trucksDb } = useRealtimeTable('trucks')
  const { rows: baysDb } = useRealtimeTable('bays')

  const trucks = demo ? [demo.truck] : trucksDb
  const baysRows = demo ? demo.bays : baysDb

  const [respawnEpoch, setRespawnEpoch] = useState({})
  const prevStatusRef = useRef({})
=======
  const latestDataRef = useRef({ trucks, bays: baysRows, powerBids });
  useEffect(() => {
    latestDataRef.current = { trucks, bays: baysRows, powerBids };
  }, [trucks, baysRows, powerBids]);
>>>>>>> Stashed changes

  useEffect(() => {
    if (!mountRef.current) return;

    // ── Scene ──────────────────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87ceeb);   // bright sky blue – daytime
    sceneRef.current = scene;

    const camera   = new THREE.PerspectiveCamera(55, 1, 0.1, 3000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mountRef.current.appendChild(renderer.domElement);

    // ── Lighting – Daytime ─────────────────────────────────────────────────────
    // Bright neutral ambient fills shadowed areas
    scene.add(new THREE.AmbientLight(0xffffff, 1.2));

    // Primary sun — sharp daytime shadows
    const sun = new THREE.DirectionalLight(0xfff5e0, 1.5);
    sun.position.set(100, 100, 50);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.near   =    1;
    sun.shadow.camera.far    =  600;
    sun.shadow.camera.left   = -200;
    sun.shadow.camera.right  =  200;
    sun.shadow.camera.top    =  200;
    sun.shadow.camera.bottom = -200;
    scene.add(sun);

    // Soft sky-fill bounce from opposite hemisphere
    const skyFill = new THREE.DirectionalLight(0xadd8e6, 0.35);
    skyFill.position.set(-80, 60, -60);
    scene.add(skyFill);

    // ── Asphalt Ground (2000 × 2000 units) ────────────────────────────────────
    const groundMat = new THREE.MeshStandardMaterial({
      color:     0x2a2a2a,
      roughness: 0.94,
      metalness: 0.02,
    });
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), groundMat);
    ground.rotation.x    = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    // ── Lane Markings (white) ──────────────────────────────────────────────────
    const whiteMat  = new THREE.MeshBasicMaterial({ color: 0xe8e8e8 });
    const yellowMat = new THREE.MeshBasicMaterial({ color: 0xf5c518 });

    // N–S lanes
    [-45, -15, 15, 45].forEach((x) => {
      const s = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 300), whiteMat);
      s.rotation.x = -Math.PI / 2;
      s.position.set(x, 0.04, 0);
      scene.add(s);
    });
    // E–W cross-lanes
    [-35, 0, 35].forEach((z) => {
      const s = new THREE.Mesh(new THREE.PlaneGeometry(300, 0.6), whiteMat);
      s.rotation.x = -Math.PI / 2;
      s.position.set(0, 0.04, z);
      scene.add(s);
    });
    // Yellow centreline double-stripe
    [-0.6, 0.6].forEach((off) => {
      const c = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 300), yellowMat);
      c.rotation.x = -Math.PI / 2;
      c.position.set(off, 0.05, 0);
      scene.add(c);
    });

    // ── Yellow Staging Lines ───────────────────────────────────────────────────
    // Idle row 1  (trucks 0-4 land at z ≈ 32)
    const stageRow1 = new THREE.Mesh(new THREE.PlaneGeometry(90, 1.4), yellowMat);
    stageRow1.rotation.x = -Math.PI / 2;
    stageRow1.position.set(0, 0.06, 32);
    scene.add(stageRow1);

    // Idle row 2  (trucks 5-9 land at z ≈ 47)
    const stageRow2 = new THREE.Mesh(new THREE.PlaneGeometry(90, 1.4), yellowMat);
    stageRow2.rotation.x = -Math.PI / 2;
    stageRow2.position.set(0, 0.06, 47);
    scene.add(stageRow2);

    // Individual bay markers along the idle rows
    [-30, -15, 0, 15, 30].forEach((x) => {
      [32, 47].forEach((z) => {
        const mk = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 10), yellowMat);
        mk.rotation.x = -Math.PI / 2;
        mk.position.set(x, 0.07, z + 5);
        scene.add(mk);
      });
    });

    // Bidding-zone box outline (trucks 0-2 land at x≈10-38, z≈10-24)
    const biddingMat = new THREE.MeshBasicMaterial({ color: 0x00bfff });
    [[50, 1.0, 24, 8], [50, 1.0, 24, 24], [1.0, 18, 10, 16], [1.0, 18, 38, 16]].forEach(
      ([w, h, x, z]) => {
        const mk = new THREE.Mesh(new THREE.PlaneGeometry(w, h), biddingMat);
        mk.rotation.x = -Math.PI / 2;
        mk.position.set(x, 0.06, z);
        scene.add(mk);
      },
    );

    // ── Container Stacks ───────────────────────────────────────────────────────
    const createContainerStack = (cx, cz, cols = 3, tiers = 3) => {
      const group = new THREE.Group();
      let ci = 0;
      for (let col = 0; col < cols; col++) {
        for (let tier = 0; tier < tiers; tier++) {
          const mat = new THREE.MeshStandardMaterial({
            color:     CONTAINER_COLORS[ci % CONTAINER_COLORS.length],
            roughness: 0.50,
            metalness: 0.55,
          });
          ci++;
          const box = new THREE.Mesh(new THREE.BoxGeometry(20, 8, 8), mat);
          box.position.set(0, tier * 8.4 + 4, col * 9);
          box.castShadow    = true;
          box.receiveShadow = true;
          group.add(box);
        }
      }
      group.position.set(cx, 0, cz);
      return group;
    };

    [...PIER_T_STACKS, ...PIER_E_STACKS].forEach(({ x, z }) =>
      scene.add(createContainerStack(x, z)),
    );

    // ── Gantry Cranes ──────────────────────────────────────────────────────────
    const createGantryCrane = (cx, cz) => {
      const group    = new THREE.Group();
      const craneMat = new THREE.MeshPhongMaterial({ color: 0xe8b800, shininess: 50 });
      const darkMat  = new THREE.MeshPhongMaterial({ color: 0x1e1e1e });

      [-14, 14].forEach((xOff) => {
        const leg = new THREE.Mesh(new THREE.BoxGeometry(2.5, 72, 2.5), craneMat);
        leg.position.set(xOff, 36, 0);
        leg.castShadow = true;
        group.add(leg);
      });
      [12, 30, 48, 64].forEach((h) => {
        const brace = new THREE.Mesh(new THREE.BoxGeometry(28.5, 1.5, 1.5), darkMat);
        brace.position.set(0, h, 0);
        group.add(brace);
      });
      const beam = new THREE.Mesh(new THREE.BoxGeometry(34, 2.5, 2.5), craneMat);
      beam.position.set(0, 72, 0);
      group.add(beam);
      const boom = new THREE.Mesh(new THREE.BoxGeometry(2.5, 2.5, 38), craneMat);
      boom.position.set(0, 72, -19);
      group.add(boom);
      const wire = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.4, 38), darkMat);
      wire.position.set(0, 69.5, -19);
      group.add(wire);

      group.position.set(cx, 0, cz);
      return group;
    };

    CRANE_POSITIONS.forEach(({ x, z }) => scene.add(createGantryCrane(x, z)));

    // ── Truck Mesh (cab + trailer ≈ 16 unit total) ─────────────────────────────
    //   Truck "front" is local +Z — cardinal rotation logic controls rotation.y.
    const createTruckMesh = (colorHex) => {
      const group = new THREE.Group();

      // bodyMat is shared across cab + trailer so the charging glow hits both.
      const bodyMat = new THREE.MeshStandardMaterial({
        color: colorHex, roughness: 0.42, metalness: 0.52,
      });
      const darkMat  = new THREE.MeshStandardMaterial({ color: 0x252525, roughness: 0.85 });
      const wheelMat = new THREE.MeshStandardMaterial({ color: 0x0e0e0e, roughness: 1.0 });

      // Cab  – children[0]
      const cab = new THREE.Mesh(new THREE.BoxGeometry(5, 5.5, 6), bodyMat);
      cab.position.set(0, 3.8, 5.5);
      cab.castShadow = true;
      group.add(cab);

      // Hood / engine block
      const hood = new THREE.Mesh(new THREE.BoxGeometry(4, 3.2, 3.5), darkMat);
      hood.position.set(0, 2.3, 7.5);
      hood.castShadow = true;
      group.add(hood);

      // Trailer container (shares bodyMat)
      const trailer = new THREE.Mesh(new THREE.BoxGeometry(5, 5, 10), bodyMat);
      trailer.position.set(0, 3.8, -2.5);
      trailer.castShadow = true;
      group.add(trailer);

      // Chassis / flatbed
      const chassis = new THREE.Mesh(new THREE.BoxGeometry(5.6, 1.1, 17), darkMat);
      chassis.position.set(0, 1.3, 0.5);
      chassis.castShadow = true;
      group.add(chassis);

      // Wheel pairs (simplified cylinders)
      [[-3, 6.5], [-3, -5], [3, 6.5], [3, -5]].forEach(([xOff, zOff]) => {
        const wheel = new THREE.Mesh(new THREE.CylinderGeometry(1.3, 1.3, 1.2, 14), wheelMat);
        wheel.rotation.z = Math.PI / 2;
        wheel.position.set(xOff, 1.3, zOff);
        group.add(wheel);
      });

      return group;
    };

    // ── Bay Mesh ───────────────────────────────────────────────────────────────
    const createBayMesh = (x, z) => {
      const g = new THREE.Group();

      // Ground pad  – children[0]
      const pad = new THREE.Mesh(
        new THREE.PlaneGeometry(14, 22),
        new THREE.MeshBasicMaterial({ color: 0x10b981, transparent: true, opacity: 0.18, side: THREE.DoubleSide }),
      );
      pad.rotation.x = -Math.PI / 2;
      g.add(pad);

      // Charging tower  – children[1]
      const tower = new THREE.Mesh(
        new THREE.BoxGeometry(2.5, 12, 2.5),
        new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.5, metalness: 0.72 }),
      );
      tower.position.set(0, 6, -10);
      tower.castShadow = true;
      g.add(tower);

      // Status indicator  – children[2]
      const indicator = new THREE.Mesh(
        new THREE.BoxGeometry(1.8, 1.8, 1.8),
        new THREE.MeshBasicMaterial({ color: 0x10b981 }),
      );
      indicator.position.set(0, 12.8, -10);
      g.add(indicator);

      g.position.set(x, 0.1, z);
      return g;
    };

    // ── Camera ─────────────────────────────────────────────────────────────────
    camera.position.set(-50, 40, 60);
    camera.lookAt(0, 0, 0);

    // ── Runtime State ──────────────────────────────────────────────────────────
    const trucksMap = {};
    const baysMap   = {};
    let animationId;

    // ── Resize Observer ────────────────────────────────────────────────────────
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
          renderer.setSize(width, height);
        }
      }
    });
    resizeObserver.observe(mountRef.current);

    // ── Interaction ────────────────────────────────────────────────────────────
    const raycaster = new THREE.Raycaster();
    let isDragging = false;
    let previousMousePosition = { x: 0, y: 0 };
    let rotationTarget = { x: 0.6, y: -0.8 };
    let orbitRadius    = 85;
    const MIN_ORBIT    =  30;
    const MAX_ORBIT    = 200;

    const handlePointerDown = (e) => {
      isDragging = true;
      const rect  = mountRef.current.getBoundingClientRect();
      const mouse = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width)  *  2 - 1,
        -((e.clientY - rect.top) / rect.height) *  2 + 1,
      );
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(
        Object.values(trucksMap).map((t) => t.mesh), true,
      );
      if (intersects.length > 0) {
        let obj = intersects[0].object;
        while (obj.parent && obj.parent.type !== 'Scene') {
          if (obj.userData?.id) break;
          obj = obj.parent;
        }
        if (obj?.userData?.id) setSelectedTruckId(obj.userData.id);
      } else {
        setSelectedTruckId(null);
      }
    };

    const handlePointerUp   = () => { isDragging = false; };
    const handlePointerMove = (e) => {
      if (isDragging) {
        rotationTarget.y -= (e.offsetX - previousMousePosition.x) * 0.01;
        rotationTarget.x -= (e.offsetY - previousMousePosition.y) * 0.01;
        rotationTarget.x  = Math.max(0.1, Math.min(Math.PI / 2.2, rotationTarget.x));
      }
      previousMousePosition = { x: e.offsetX, y: e.offsetY };
    };
    const handleWheel = (e) => {
      e.preventDefault();
      orbitRadius = Math.min(MAX_ORBIT, Math.max(MIN_ORBIT, orbitRadius + e.deltaY * 0.08));
    };

    const container = mountRef.current;
    container.addEventListener('pointerdown', handlePointerDown);
    container.addEventListener('pointermove', handlePointerMove);
    container.addEventListener('wheel', handleWheel, { passive: false });
    window.addEventListener('pointerup', handlePointerUp);

    // ── Animate ────────────────────────────────────────────────────────────────
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      const { trucks: currentTrucks, bays: currentBays } = latestDataRef.current;

      // Camera orbit
      camera.position.x = Math.sin(rotationTarget.y) * orbitRadius * Math.cos(rotationTarget.x);
      camera.position.z = Math.cos(rotationTarget.y) * orbitRadius * Math.cos(rotationTarget.x);
      camera.position.y = Math.sin(rotationTarget.x) * orbitRadius;
      camera.lookAt(0, 0, 0);

      // ── Bays ──────────────────────────────────────────────────────────────────
      (currentBays || []).forEach((bay, i) => {
        if (!baysMap[bay.id]) {
          const pos  = BAY_POSITIONS_3D[bay.name] || { x: -30 + i * 20, z: -20 };
          const mesh = createBayMesh(pos.x, pos.z);
          scene.add(mesh);
          baysMap[bay.id] = mesh;
        }
        const charging = bayIsActivelyCharging(bay, currentTrucks);
        const tint = charging ? 0xf59e0b : 0x10b981;
        baysMap[bay.id].children[0].material.color.setHex(tint);
        baysMap[bay.id].children[2].material.color.setHex(tint);
      });

      // ── Remove stale trucks ────────────────────────────────────────────────────
      const liveIds = new Set((currentTrucks || []).map((t) => t.id));
      Object.keys(trucksMap).forEach((id) => {
        if (!liveIds.has(id)) {
          scene.remove(trucksMap[id].mesh);
          trucksMap[id].socTexture?.dispose();
          delete trucksMap[id];
        }
      });

      // ── Trucks ────────────────────────────────────────────────────────────────
      (currentTrucks || []).forEach((truck, i) => {
        // ── Create entry on first sight ────────────────────────────────────────
        if (!trucksMap[truck.id]) {
          const color = TRUCK_COLORS[i % TRUCK_COLORS.length];
          const mesh  = createTruckMesh(color);
          mesh.userData = { id: truck.id };
          scene.add(mesh);

          // SoC label sprite
          const socCanvas  = makeSocCanvas();
          const soc0       = truck.current_soc ?? truck.state_of_charge ?? null;
          drawSocLabel(socCanvas, soc0);
          const socTexture = new THREE.CanvasTexture(socCanvas);
          const socSprite  = new THREE.Sprite(
            new THREE.SpriteMaterial({ map: socTexture, depthTest: false }),
          );
          // Scale in world units — width × height
          socSprite.scale.set(12, 4.5, 1);
          // Float 14 units above truck group origin (top of cab ≈ 9 units)
          socSprite.position.set(0, 14, 0);
          mesh.add(socSprite);    // child of group → follows truck automatically

          trucksMap[truck.id] = {
            mesh,
            color,
            targetQuat: new THREE.Quaternion(),
            socCanvas,
            socTexture,
            lastSoc: soc0,
          };
        }

        const tData  = trucksMap[truck.id];
        const status = effectiveMapStatus(truck, currentBays);

        // ── Target position ────────────────────────────────────────────────────
        // Default: idle staging grid (south of origin, aligns with yellow lines)
        let targetX = -30 + (i % 5) * 15;
        let targetZ  =  32 + Math.floor(i / 5) * 15;

        if (status === 'bidding') {
          // Bidding zone (north-east quadrant, inside blue outline)
          targetX = 10 + (i % 3) * 14;
          targetZ  = 10 + Math.floor(i / 3) * 14;
        }
        if (status === 'charging' && truck.bay_id) {
          const bay = (currentBays || []).find((b) => b.id === truck.bay_id);
          if (bay) {
            const pos = BAY_POSITIONS_3D[bay.name] || { x: -20, z: -20 };
            targetX = pos.x;
            targetZ  = pos.z;
          }
        }

        const targetVec = new THREE.Vector3(targetX, 0, targetZ);
        tData.mesh.position.lerp(targetVec, 0.05);

        // ── Cardinal Rotation Logic ────────────────────────────────────────────
        // Only 0 / 90 / 180 / 270° — no diagonal rotations.
        //
        // Truck geometry: "front" (cab + hood) is at local +Z, so:
        //   rotation.y =  π/2 → world +X (east)
        //   rotation.y = -π/2 → world -X (west)
        //   rotation.y =  0   → world +Z (south)
        //   rotation.y =  π   → world -Z (north)
        //
        // Turn speed = slerp factor (0.12). Raise for snappier, lower for drifty.
        const dx = targetX - tData.mesh.position.x;
        const dz = targetZ - tData.mesh.position.z;

        if (tData.mesh.position.distanceTo(targetVec) > 1.0) {
          const targetRotY = Math.abs(dx) >= Math.abs(dz)
            ? (dx > 0 ? Math.PI / 2 : -Math.PI / 2)   // east / west
            : (dz > 0 ? 0           : Math.PI);         // south / north
          tData.targetQuat.setFromEuler(new THREE.Euler(0, targetRotY, 0));
          // TUNE HERE: replace 0.12 to adjust turn speed
          tData.mesh.quaternion.slerp(tData.targetQuat, 0.12);
        }

        // ── SoC label update (only redraws canvas when value changes) ──────────
        const soc = truck.current_soc ?? truck.state_of_charge ?? null;
        if (tData.lastSoc !== soc) {
          drawSocLabel(tData.socCanvas, soc);
          tData.socTexture.needsUpdate = true;
          tData.lastSoc = soc;
        }

        // ── Charging glow (bodyMat shared → cab + trailer glow together) ───────
        const mat = tData.mesh.children[0].material;
        if (status === 'charging') {
          mat.emissive.setHex(0x10b981);
          mat.emissiveIntensity = 0.35 + Math.sin(Date.now() * 0.005) * 0.35;
        } else {
          mat.emissive.setHex(0x000000);
          mat.emissiveIntensity = 0;
        }
      });

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationId);
      resizeObserver.disconnect();
      container.removeEventListener('pointerdown', handlePointerDown);
      container.removeEventListener('pointermove', handlePointerMove);
      container.removeEventListener('wheel', handleWheel);
      window.removeEventListener('pointerup', handlePointerUp);
      Object.values(trucksMap).forEach((t) => t.socTexture?.dispose());
      if (renderer.domElement && mountRef.current) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return (
    <div style={{ ...style, position: 'relative', background: '#87ceeb' }}>
      <div ref={mountRef} style={{ width: '100%', height: '100%', cursor: 'grab' }} />
      {selectedTruckId && (
        <div className="absolute top-4 left-4 p-4 bg-slate-900/80 backdrop-blur border border-blue-500 rounded text-white font-mono text-xs z-10 w-80 shadow-2xl">
          <div className="text-blue-400 font-bold uppercase mb-2">Agent Telemetry</div>
          {'> '}{latestReasoningForTruck(powerBids, selectedTruckId)}
        </div>
      )}
    </div>
  );
}
