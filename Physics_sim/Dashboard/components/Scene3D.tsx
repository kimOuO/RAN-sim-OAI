'use client';

/**
 * Scene3D — TopDownMap 的 3D 對應版本（WebGL / react-three-fiber）。
 *
 * 與 TopDownMap 共用同一組 Props，可在 editor 頁以 2D/3D 切換鈕互換。
 * 顏色與配色函式（toRgb / footprintColor / valToRgb）直接沿用 TopDownMap
 * 匯出的實作，確保兩個視圖看起來是同一個場景。
 *
 * 座標系：後端 scene config 與 three.js 同為 Y-up 右手座標，
 * position=[x, y, z] 直接對應 three 的 (x, y, z)，不需任何轉換。
 * （只有匯出到 Omniverse USD 的 Z-up 時才需要 -90° 繞 X 軸。）
 *
 * 拖曳（A4）：把滑鼠射線與 y=0 地面求交得到世界座標 (x, z)，
 * 再回呼與 2D 視圖完全相同的 onMoveBuilding / onMoveGnb / onMoveCell /
 * onMoveUE / onMoveWaypoint —— 後端與 state 邏輯共用，沒有另一套。
 * 提交時機也對齊 2D：waypoint 即時更新，其餘物件拖曳中只做預覽、放開才寫回。
 */

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useThree, type ThreeEvent } from '@react-three/fiber';
import { Grid, Html, Line, OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import {
  SCENE_MIN,
  SCENE_MAX,
  footprintColor,
  toRgb,
  valToRgb,
  type Props,
} from './TopDownMap';

const SCENE_SIZE = SCENE_MAX - SCENE_MIN;
// 以下尺寸都是「城市尺度」的預設值，實際使用時一律乘上 markerScale。
// 室內場景（走廊只有 14 m 寬）不縮的話，一顆 4 m 半徑的 UE 球就足以遮住整條走廊。
const GNB_COVERAGE_R = 37.5; // 與 2D 視圖同一個示意半徑
const AZIMUTH_LEN_M = 40;
const TRAJ_COLORS = ['#f59e0b', '#3b82f6', '#ec4899', '#22d3ee', '#a78bfa', '#f97316', '#84cc16'];

/** 與 TopDownMap 的 DragTarget 對齊（該型別在 2D 檔內為私有，這裡重宣告一份）。 */
type DragTarget =
  | { type: 'waypoint'; idx: number }
  | { type: 'building'; name: string }
  | { type: 'gnb'; name: string }
  | { type: 'cell'; gnbName: string; cellIdx: number }
  | { type: 'ue'; name: string };

type TempPos = { x: number; z: number } | null;

/** 拖曳共用的滑鼠事件組：按下即開始拖，游標進出時切換 cursor。 */
type DragBinding = {
  onPointerDown: (e: ThreeEvent<PointerEvent>) => void;
  onPointerOver: () => void;
  onPointerOut: () => void;
};

/** 疊在 3D 物件上的文字標籤（用 DOM，避免 troika 字型需連外下載）。 */
function Label({
  position,
  color,
  children,
  size = 10,
  weight = 400,
}: {
  position: [number, number, number];
  color: string;
  children: React.ReactNode;
  size?: number;
  weight?: number;
}) {
  return (
    <Html position={position} center={false} style={{ pointerEvents: 'none' }}>
      <div
        style={{
          color,
          fontSize: size,
          fontWeight: weight,
          whiteSpace: 'nowrap',
          textShadow: '0 1px 3px #000',
          transform: 'translate(6px, -50%)',
        }}
      >
        {children}
      </div>
    </Html>
  );
}

/* ────────────────────────── 拖曳控制器 ────────────────────────── */

/**
 * 拖曳期間掛在 canvas 上的 pointer 監聽：把螢幕座標轉成 y=0 平面上的世界座標。
 *
 * 刻意不靠「滑鼠壓在某個 mesh 上」來取座標 —— 拖曳時游標常會滑出物件、
 * 甚至被建築擋住，用 mesh 事件會斷掉。直接對無限延伸的 y=0 平面求交最穩。
 */
function DragController({
  dragging,
  onDragMove,
  onDragEnd,
}: {
  dragging: DragTarget | null;
  onDragMove: (x: number, z: number) => void;
  onDragEnd: () => void;
}) {
  const camera = useThree((s) => s.camera);
  const gl = useThree((s) => s.gl);
  const invalidate = useThree((s) => s.invalidate);

  useEffect(() => {
    if (!dragging) return;
    const el = gl.domElement;
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const raycaster = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    const hit = new THREE.Vector3();

    const handleMove = (ev: PointerEvent) => {
      const rect = el.getBoundingClientRect();
      ndc.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      ndc.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(ndc, camera);
      if (raycaster.ray.intersectPlane(plane, hit)) {
        onDragMove(hit.x, hit.z);
        invalidate(); // frameloop="demand"：拖曳中要主動要求重畫
      }
    };

    // pointerup 掛在 window：放開時游標可能已經離開 canvas
    el.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', onDragEnd);
    return () => {
      el.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', onDragEnd);
    };
  }, [dragging, camera, gl, invalidate, onDragMove, onDragEnd]);

  return null;
}

/* ────────────────────────── 匯入網格 (.glb) ────────────────────────── */

/** 瀏覽器端能撐住的最大貼圖邊長。 */
const MAX_TEXTURE_PX = 1024;

/**
 * 非同步把過大的貼圖縮小。
 *
 * 掃描檔常見 15 張 4096² JPEG —— 解碼後每張是 4096*4096*4 ≈ 67 MB 的 RGBA，
 * 15 張約 1 GB VRAM，不縮會直接壓垮分頁。
 *
 * **一定要非同步**：第一版用 canvas.drawImage 同步縮圖，15 張全擠在主執行緒上，
 * 一按 3D 整個頁面凍住好幾秒。createImageBitmap 的 resize 選項是在瀏覽器內部
 * 執行緒做的，而且每張之間 await 一次會把控制權交還事件迴圈，UI 全程可操作。
 */
async function downscaleTextureAsync(tex: THREE.Texture): Promise<boolean> {
  const img = tex.image as (ImageBitmap | HTMLImageElement | HTMLCanvasElement | undefined);
  if (!img) return false;
  const w = (img as any).width ?? 0;
  const h = (img as any).height ?? 0;
  if (!w || !h || Math.max(w, h) <= MAX_TEXTURE_PX) return false;
  if (typeof createImageBitmap !== 'function') return false;

  const ratio = MAX_TEXTURE_PX / Math.max(w, h);
  try {
    const small = await createImageBitmap(img as ImageBitmapSource, {
      resizeWidth: Math.max(1, Math.round(w * ratio)),
      resizeHeight: Math.max(1, Math.round(h * ratio)),
      resizeQuality: 'medium',
    });
    tex.image = small;
    tex.needsUpdate = true;
    if (typeof (img as ImageBitmap).close === 'function') (img as ImageBitmap).close();
    return true;
  } catch {
    return false;   // 縮不動就照原尺寸用，總比整個圖層消失好
  }
}

/**
 * 載入匯入的 .glb 並貼在場景原點（與後端轉 USD 時的置中規則一致）。
 *
 * cutHeight：水平剖面高度。用 clipping plane 把這個高度以上切掉，
 * 就能從上方看進走廊內部、看到人站在哪裡（天花板與上半段牆會被切掉）。
 */
function ImportedMesh({
  url,
  opacity,
  cutHeight,
}: {
  url: string;
  opacity: number;
  cutHeight: number | null;
}) {
  const { scene } = useGLTF(url);
  const invalidate = useThree((s) => s.invalidate);
  const gl = useThree((s) => s.gl);

  // clipping plane 要開 localClippingEnabled，否則材質上的 clippingPlanes 會被忽略
  useEffect(() => {
    gl.localClippingEnabled = true;
  }, [gl]);

  const prepared = useMemo(() => {
    // useGLTF 會快取同一個 URL 的 scene，直接改材質會污染其他使用者 → 先 clone。
    // 這裡只做「便宜」的事：貼圖縮小改在下面的 effect 非同步做。
    const root = scene.clone(true);
    const materials: THREE.MeshStandardMaterial[] = [];
    root.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.raycast = () => {};   // 背景幾何不參與點選/拖曳的 hit test
      const wasArray = Array.isArray(mesh.material);
      const source = (wasArray ? mesh.material : [mesh.material]) as THREE.Material[];
      const cloned = source.map((m) => {
        const mat = (m as THREE.MeshStandardMaterial).clone();
        // 掃描網格沒有法線、面又多半朝室內 → 兩面都畫，否則從外面看是空的
        mat.side = THREE.DoubleSide;
        materials.push(mat);
        return mat;
      });
      mesh.material = wasArray ? cloned : cloned[0];
    });
    return { root, materials };
  }, [scene]);

  // 透明度與剖面高度是「常改」的參數，直接寫在既有材質上，不重建整棵樹
  useEffect(() => {
    const plane = cutHeight === null ? null : new THREE.Plane(new THREE.Vector3(0, -1, 0), cutHeight);
    for (const mat of prepared.materials) {
      mat.transparent = opacity < 1;
      mat.opacity = opacity;
      mat.clippingPlanes = plane ? [plane] : null;
      mat.needsUpdate = true;
    }
    invalidate();
  }, [prepared, opacity, cutHeight, invalidate]);

  // 貼圖縮小：逐張非同步處理，每張之間把控制權讓回事件迴圈
  useEffect(() => {
    let cancelled = false;
    const seen = new Set<THREE.Texture>();
    (async () => {
      for (const mat of prepared.materials) {
        if (cancelled) return;
        const map = mat.map;
        if (!map || seen.has(map)) continue;
        seen.add(map);
        if (await downscaleTextureAsync(map)) invalidate();
      }
    })();
    return () => { cancelled = true; };
  }, [prepared, invalidate]);

  return <primitive object={prepared.root} />;
}

/* ────────────────────────── Coverage heatmap ────────────────────────── */

/**
 * 把 coverage grid 畫成「一張 DataTexture 貼在地面平面」，
 * 而不是每格一個 mesh —— 幾千格時後者會直接拖垮 frame rate。
 */
function CoverageLayer({ overlay }: { overlay: NonNullable<Props['coverageOverlay']> }) {
  const { grid, data, opacity = 0.65 } = overlay;

  const texture = useMemo(() => {
    const flat = data.flat().filter((v): v is number => v !== null);
    if (!flat.length) return null;
    const minV = Math.min(...flat);
    const maxV = Math.max(...flat);

    const w = grid.n_cols;
    const h = grid.n_rows;
    const buf = new Uint8Array(w * h * 4);
    for (let zi = 0; zi < h; zi++) {
      for (let xi = 0; xi < w; xi++) {
        const val = data[zi]?.[xi];
        const o = (zi * w + xi) * 4;
        if (val === null || val === undefined) {
          buf[o + 3] = 0; // 無資料 → 全透明
          continue;
        }
        const [r, g, b] = valToRgb(val, minV, maxV);
        buf[o] = r;
        buf[o + 1] = g;
        buf[o + 2] = b;
        buf[o + 3] = 255;
      }
    }
    // flipY=false：第 0 列資料落在 v=0，經下方 rotation-x=-90° 後對應 world +Z，
    // 正好等於 grid.z_range[1]（最大 z），與 2D 視圖的列順序一致。
    const tex = new THREE.DataTexture(buf, w, h, THREE.RGBAFormat);
    tex.flipY = false;
    tex.magFilter = THREE.LinearFilter;
    tex.minFilter = THREE.LinearFilter;
    tex.needsUpdate = true;
    return tex;
  }, [grid, data]);

  useEffect(() => () => texture?.dispose(), [texture]);

  if (!texture) return null;

  const w = grid.n_cols * grid.x_step;
  const d = grid.n_rows * grid.z_step;
  const cx = grid.x_range[0] + w / 2;
  const cz = grid.z_range[1] - d / 2;

  return (
    <mesh position={[cx, 0.15, cz]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={1} raycast={() => null}>
      <planeGeometry args={[w, d]} />
      <meshBasicMaterial
        map={texture}
        transparent
        opacity={opacity}
        depthWrite={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/* ────────────────────────── OSM footprints ────────────────────────── */

/** OSM 校園輪廓：把 2D 多邊形沿 +Y 拉伸成實體量體（背景層，不可互動）。 */
function Footprints({ footprints }: { footprints: NonNullable<Props['mapFootprints']> }) {
  const meshes = useMemo(
    () =>
      footprints.map((f, i) => {
        // shape 建在 (x, -z) 平面：經 rotation-x=-90° 後，
        // local +Z → world +Y（拉伸方向），local -Y → world +Z（還原 z 軸方向）。
        const shape = new THREE.Shape();
        f.points.forEach(([x, z], idx) => {
          if (idx === 0) shape.moveTo(x, -z);
          else shape.lineTo(x, -z);
        });
        shape.closePath();
        const geom = new THREE.ExtrudeGeometry(shape, {
          depth: Math.max(f.height, 1),
          bevelEnabled: false,
        });
        return { key: `fp-${i}`, geom, color: footprintColor(f.height) };
      }),
    [footprints],
  );

  useEffect(() => () => meshes.forEach((m) => m.geom.dispose()), [meshes]);

  return (
    <group rotation={[-Math.PI / 2, 0, 0]}>
      {meshes.map((m) => (
        <mesh key={m.key} geometry={m.geom} raycast={() => null}>
          <meshLambertMaterial color={m.color} transparent opacity={0.55} />
        </mesh>
      ))}
    </group>
  );
}

/* ────────────────────────── Buildings ────────────────────────── */

function Buildings({
  buildings,
  onSelectObject,
  dragging,
  tempPos,
  bindDrag,
}: Pick<Props, 'buildings' | 'onSelectObject'> & {
  dragging: DragTarget | null;
  tempPos: TempPos;
  bindDrag: (t: DragTarget) => DragBinding;
}) {
  return (
    <>
      {buildings.map((b) => {
        const isDragging = dragging?.type === 'building' && dragging.name === b.name;
        const bx = isDragging && tempPos ? tempPos.x : b.position[0];
        const bz = isDragging && tempPos ? tempPos.z : b.position[2];
        const [sx, sy, sz] = b.size;
        // scene config 的 position.y 是「地面基準」(範例中恆為 0)，
        // 而 three 的 box 以中心定位 → 中心要抬高半個樓高。
        const cy = b.position[1] + sy / 2;
        const rot = b.rotation_xyz_deg ?? [0, 0, 0];
        return (
          <group key={`building-${b.name}`}>
            <mesh
              position={[bx, cy, bz]}
              rotation={[
                (rot[0] * Math.PI) / 180,
                (rot[1] * Math.PI) / 180,
                (rot[2] * Math.PI) / 180,
              ]}
              onClick={(e) => {
                e.stopPropagation();
                onSelectObject?.({ type: 'building', name: b.name });
              }}
              {...bindDrag({ type: 'building', name: b.name })}
            >
              <boxGeometry args={[sx, sy, sz]} />
              <meshLambertMaterial
                color="#38384a"
                emissive={isDragging ? '#88ff88' : '#000000'}
                emissiveIntensity={isDragging ? 0.35 : 0}
                transparent={isDragging}
                opacity={isDragging ? 0.7 : 1}
              />
            </mesh>
            <Label position={[bx, b.position[1] + sy, bz]} color="#aaa" size={9}>
              {b.name}
            </Label>
          </group>
        );
      })}
    </>
  );
}

/* ────────────────────────── gNBs ────────────────────────── */

function circlePoints(cx: number, cz: number, r: number, y: number, seg = 64) {
  const pts: [number, number, number][] = [];
  for (let i = 0; i <= seg; i++) {
    const t = (i / seg) * Math.PI * 2;
    pts.push([cx + r * Math.cos(t), y, cz + r * Math.sin(t)]);
  }
  return pts;
}

function GNBs({
  gnbs,
  onSelectObject,
  dragging,
  tempPos,
  bindDrag,
  ms,
}: Pick<Props, 'gnbs' | 'onSelectObject'> & {
  dragging: DragTarget | null;
  tempPos: TempPos;
  bindDrag: (t: DragTarget) => DragBinding;
  ms: number;
}) {
  return (
    <>
      {gnbs.map((g: any) => {
        const isDragging = dragging?.type === 'gnb' && dragging.name === g.name;
        const gx = isDragging && tempPos ? tempPos.x : g.position[0];
        const gz = isDragging && tempPos ? tempPos.z : g.position[2];
        const gy = g.position[1] ?? 0;
        const color = toRgb(g.color);

        // 有 cells 就每個 sector 一支箭頭；沒有就用 gNB 自身的 azimuth 畫一支。
        // 有自己 position 的 cell（分散式/DAS）畫在該處且可獨立拖曳。
        const sectors: Array<{
          az: number;
          pci?: number;
          cx: number;
          cy: number;
          cz: number;
          movable: boolean;
          idx: number;
        }> =
          g.cells && g.cells.length > 0
            ? g.cells.map((c: any, ci: number) => {
                const dragMe =
                  dragging?.type === 'cell' && dragging.gnbName === g.name && dragging.cellIdx === ci;
                const hasPos = Array.isArray(c.position) && c.position.length >= 3;
                return {
                  az: c.azimuth_deg ?? 0,
                  pci: c.pci,
                  idx: ci,
                  movable: hasPos,
                  cx: dragMe && tempPos ? tempPos.x : hasPos ? c.position[0] : gx,
                  cy: hasPos ? c.position[1] : gy,
                  cz: dragMe && tempPos ? tempPos.z : hasPos ? c.position[2] : gz,
                };
              })
            : [{ az: g.azimuth_deg ?? 0, pci: g.pci, cx: gx, cy: gy, cz: gz, movable: false, idx: 0 }];

        return (
          <group key={`gnb-${g.name}`}>
            {/* 天線桿 + 站心（皆可拖曳整站） */}
            <mesh
              position={[gx, gy / 2, gz]}
              onClick={(e) => {
                e.stopPropagation();
                onSelectObject?.({ type: 'gnb', name: g.name });
              }}
              {...bindDrag({ type: 'gnb', name: g.name })}
            >
              <cylinderGeometry args={[1.2 * ms, 1.2 * ms, Math.max(gy, 2), 12]} />
              <meshLambertMaterial color={color} />
            </mesh>
            <mesh
              position={[gx, gy, gz]}
              onClick={(e) => {
                e.stopPropagation();
                onSelectObject?.({ type: 'gnb', name: g.name });
              }}
              {...bindDrag({ type: 'gnb', name: g.name })}
            >
              <sphereGeometry args={[(isDragging ? 4 : 3) * ms, 16, 12]} />
              <meshLambertMaterial
                color={color}
                emissive={isDragging ? '#ffff00' : color}
                emissiveIntensity={isDragging ? 0.7 : 0.4}
              />
            </mesh>

            {/* Coverage 示意圈（貼地） */}
            <Line
              points={circlePoints(gx, gz, GNB_COVERAGE_R * ms, 0.25 * ms)}
              color={color}
              lineWidth={1}
              dashed
              dashSize={6}
              gapSize={4}
              transparent
              opacity={0.5}
            />

            {/* 每個 sector 的 azimuth 箭頭。Sionna 慣例 azimuth=0 沿 +X 軸。 */}
            {sectors.map((s) => {
              const az = (s.az * Math.PI) / 180;
              const ex = s.cx + AZIMUTH_LEN_M * ms * Math.cos(az);
              const ez = s.cz + AZIMUTH_LEN_M * ms * Math.sin(az);
              return (
                <group key={`gnb-${g.name}-sec-${s.idx}`}>
                  <Line
                    points={[
                      [s.cx, s.cy, s.cz],
                      [ex, s.cy, ez],
                    ]}
                    color={color}
                    lineWidth={2}
                    transparent
                    opacity={0.85}
                  />
                  {/* 錐體箭頭：預設朝 +Y，先轉到 +X 再繞 Y 套 azimuth */}
                  <mesh position={[ex, s.cy, ez]} rotation={[0, -az, -Math.PI / 2]} raycast={() => null}>
                    <coneGeometry args={[2.5 * ms, 7 * ms, 12]} />
                    <meshLambertMaterial color={color} />
                  </mesh>
                  {s.pci !== undefined && (
                    <Label position={[ex, s.cy + 4 * ms, ez]} color={color} size={9} weight={500}>
                      pci{s.pci}
                    </Label>
                  )}
                  {/* 分散式 cell：與母站連一條淡線 + 可獨立拖曳的菱形把手 */}
                  {s.movable && (
                    <>
                      <Line
                        points={[
                          [gx, gy, gz],
                          [s.cx, s.cy, s.cz],
                        ]}
                        color={color}
                        lineWidth={1}
                        dashed
                        dashSize={3}
                        gapSize={4}
                        transparent
                        opacity={0.35}
                      />
                      <mesh
                        position={[s.cx, s.cy, s.cz]}
                        {...bindDrag({ type: 'cell', gnbName: g.name, cellIdx: s.idx })}
                      >
                        <octahedronGeometry args={[3.5 * ms]} />
                        <meshLambertMaterial color={color} emissive={color} emissiveIntensity={0.5} />
                      </mesh>
                    </>
                  )}
                </group>
              );
            })}

            <Label position={[gx, gy + 8 * ms, gz]} color={color} size={10} weight={600}>
              {g.name}
            </Label>
          </group>
        );
      })}
    </>
  );
}

/* ────────────────────────── UEs + 軌跡 ────────────────────────── */

/**
 * 火柴人 UE 標記。
 *
 * 原本用球體，在室內場景裡就是一顆看不出方向、也看不出是「人」的圓點。
 * 火柴人用線段畫（drei 的 Line 是螢幕空間寬度），所以不管鏡頭拉多遠都看得見，
 * 又比 sprite 好的是它有真實的 3D 位置與高度，站在地板上的感覺是對的。
 *
 * height 直接就是人的公尺身高：室內 1.7 m，城市尺度會依 markerScale 放大，
 * 否則 1000 m 的場景裡一個 1.7 m 的人只有半個像素。
 */
function StickFigure({
  position,
  height,
  color,
  lineWidth,
}: {
  position: [number, number, number];
  height: number;
  color: string;
  lineWidth: number;
}) {
  const [x, y, z] = position;
  // 依人體比例切幾個關鍵高度（頭 / 肩 / 胯），比例取自常見的 7.5 頭身簡化
  const headR = height * 0.09;
  const yHead = y + height - headR;
  const yShoulder = y + height * 0.78;
  const yHip = y + height * 0.48;
  const armSpan = height * 0.22;
  const legSpan = height * 0.13;

  const seg = (a: [number, number, number], b: [number, number, number]) => [a, b] as [number, number, number][];

  return (
    <group>
      <mesh position={[x, yHead, z]} raycast={() => null}>
        <sphereGeometry args={[headR, 12, 10]} />
        <meshLambertMaterial color={color} emissive={color} emissiveIntensity={0.35} />
      </mesh>
      {/* 軀幹 */}
      <Line points={seg([x, yShoulder, z], [x, yHip, z])} color={color} lineWidth={lineWidth} />
      {/* 雙臂（張開，從正面/側面都看得出是人形） */}
      <Line points={seg([x - armSpan, yHip + height * 0.12, z], [x, yShoulder, z])} color={color} lineWidth={lineWidth} />
      <Line points={seg([x, yShoulder, z], [x + armSpan, yHip + height * 0.12, z])} color={color} lineWidth={lineWidth} />
      {/* 雙腿 */}
      <Line points={seg([x, yHip, z], [x - legSpan, y, z])} color={color} lineWidth={lineWidth} />
      <Line points={seg([x, yHip, z], [x + legSpan, y, z])} color={color} lineWidth={lineWidth} />
    </group>
  );
}



function UEs({
  ues,
  trajectories,
  selectedUEIndex,
  onSelectObject,
  onSelectUEIndex,
  dragging,
  tempPos,
  bindDrag,
  ms,
}: Pick<Props, 'ues' | 'trajectories' | 'selectedUEIndex' | 'onSelectObject' | 'onSelectUEIndex'> & {
  dragging: DragTarget | null;
  tempPos: TempPos;
  bindDrag: (t: DragTarget) => DragBinding;
  ms: number;
}) {
  // 人的身高。室內 markerScale=0.1 → 1.7 m（真實身高）；
  // 城市尺度 markerScale=1 → 17 m，否則在 1000 m 的場景裡看不見
  const figureH = 17 * ms;
  return (
    <>
      {ues.map((u: any, idx: number) => {
        const isSelected = idx === selectedUEIndex;
        const isDragging = dragging?.type === 'ue' && dragging.name === u.name;
        const live = trajectories.find((t) => t.name === u.name)?.position;
        const base = live ?? u.position;
        const ux = isDragging && tempPos ? tempPos.x : base[0];
        const uz = isDragging && tempPos ? tempPos.z : base[2];
        const uy = base[1] ?? 0;
        const color = isSelected ? '#FFC107' : '#FF9800';
        return (
          <group key={`ue-${u.name}`}>
            <StickFigure
              position={[ux, uy, uz]}
              height={figureH}
              color={color}
              lineWidth={isSelected ? 2.5 : 1.5}
            />
            {/* 火柴人是線段，射線點不到 → 疊一個看不見的圓柱當點選/拖曳的把手 */}
            <mesh
              position={[ux, uy + figureH / 2, uz]}
              onClick={(e) => {
                e.stopPropagation();
                onSelectObject?.({ type: 'ue', name: u.name });
                onSelectUEIndex?.(idx);
              }}
              {...bindDrag({ type: 'ue', name: u.name })}
            >
              <cylinderGeometry args={[figureH * 0.28, figureH * 0.28, figureH, 8]} />
              <meshBasicMaterial
                transparent
                opacity={isDragging ? 0.25 : 0}
                color={color}
                depthWrite={false}
              />
            </mesh>
            <Label
              position={[ux, uy + figureH * 1.05, uz]}
              color={isSelected ? '#FFC107' : '#aaa'}
              size={isSelected ? 11 : 9}
              weight={isSelected ? 700 : 400}
            >
              {u.name}
            </Label>
          </group>
        );
      })}

      {trajectories.map((t, idx) => {
        if (!t.waypoints || t.waypoints.length < 2) return null;
        const isSelected = idx === selectedUEIndex;
        return (
          <Line
            key={`traj-${t.name}`}
            points={t.waypoints.map((w) => [w[0], (w[1] ?? 0) + 1 * ms, w[2]] as [number, number, number])}
            color={isSelected ? '#4CAF50' : TRAJ_COLORS[idx % TRAJ_COLORS.length]}
            lineWidth={isSelected ? 2.5 : 1.5}
            dashed
            dashSize={6}
            gapSize={3}
            transparent
            opacity={isSelected ? 1 : 0.85}
          />
        );
      })}
    </>
  );
}

/* ────────────────────────── Waypoint 把手 ────────────────────────── */

/** 只有被選取的 UE 顯示可拖曳的 waypoint 把手（與 2D 一致）；右鍵刪除。 */
function Waypoints({
  waypoints,
  dragging,
  bindDrag,
  onRemoveWaypoint,
  ms,
}: {
  waypoints: [number, number, number][];
  dragging: DragTarget | null;
  bindDrag: (t: DragTarget) => DragBinding;
  onRemoveWaypoint: Props['onRemoveWaypoint'];
  ms: number;
}) {
  // 劇本產生的軌跡可以有上千個點（實測 24 小時劇本每人 1478 個）。
  // 為每個點畫一顆球 + 一個 HTML 標籤，會變成一條白牆並塞爆 DOM，
  // 畫布直接卡住。超過門檻就只畫球、不畫編號，再多就抽樣顯示。
  const LABEL_LIMIT = 60;
  const HANDLE_LIMIT = 200;
  const showLabels = waypoints.length <= LABEL_LIMIT;
  const stride = Math.max(1, Math.ceil(waypoints.length / HANDLE_LIMIT));

  return (
    <>
      {waypoints.map((w, idx) => {
        if (idx % stride !== 0) return null;
        const isDragging = dragging?.type === 'waypoint' && dragging.idx === idx;
        return (
          <group key={`wp-${idx}`}>
            <mesh
              position={[w[0], (w[1] ?? 0) + 2 * ms, w[2]]}
              onContextMenu={(e) => {
                e.stopPropagation();
                e.nativeEvent.preventDefault();
                onRemoveWaypoint(idx);
              }}
              {...bindDrag({ type: 'waypoint', idx })}
            >
              <sphereGeometry args={[3.5 * ms, 16, 12]} />
              <meshLambertMaterial
                color={isDragging ? '#FFD54F' : '#4CAF50'}
                emissive={isDragging ? '#FFD54F' : '#4CAF50'}
                emissiveIntensity={0.4}
              />
            </mesh>
            {showLabels && (
              <Label position={[w[0], (w[1] ?? 0) + 7 * ms, w[2]]} color="#fff" size={9} weight={700}>
                {idx + 1}
              </Label>
            )}
          </group>
        );
      })}
    </>
  );
}

/* ────────────────────────── 路徑規劃圖層 ────────────────────────── */

function PathLayer({ pathA, pathB, plannedPath, ms }: Pick<Props, 'pathA' | 'pathB' | 'plannedPath'> & { ms: number }) {
  return (
    <>
      {pathA && pathB && (
        <Line
          points={[
            [pathA[0], 1 * ms, pathA[1]],
            [pathB[0], 1 * ms, pathB[1]],
          ]}
          color="#ef4444"
          lineWidth={1.5}
          dashed
          dashSize={6}
          gapSize={4}
          transparent
          opacity={0.7}
        />
      )}
      {plannedPath && plannedPath.length > 1 && (
        <Line
          points={plannedPath.map(([x, z]) => [x, 1.5 * ms, z] as [number, number, number])}
          color="#22c55e"
          lineWidth={3}
        />
      )}
      {pathA && (
        <mesh position={[pathA[0], 3 * ms, pathA[1]]} raycast={() => null}>
          <sphereGeometry args={[4 * ms, 16, 12]} />
          <meshLambertMaterial color="#f59e0b" emissive="#f59e0b" emissiveIntensity={0.4} />
        </mesh>
      )}
      {pathB && (
        <mesh position={[pathB[0], 3 * ms, pathB[1]]} raycast={() => null}>
          <sphereGeometry args={[4 * ms, 16, 12]} />
          <meshLambertMaterial color="#ef4444" emissive="#ef4444" emissiveIntensity={0.4} />
        </mesh>
      )}
    </>
  );
}

/* ────────────────────────── 場景本體 ────────────────────────── */

/** frameloop="demand" 下，資料變動時要主動要求重畫一次。 */
function InvalidateOnChange({ deps }: { deps: unknown[] }) {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return null;
}

export function Scene3D({
  width = 700,
  height = 600,
  buildings,
  gnbs,
  ues,
  selectedUEIndex,
  trajectories,
  onAddWaypoint,
  onMoveWaypoint,
  onRemoveWaypoint,
  onMoveBuilding,
  onMoveGnb,
  onMoveCell,
  onMoveUE,
  onSelectObject,
  onSelectUEIndex,
  coverageOverlay,
  mapFootprints,
  pathA,
  pathB,
  plannedPath,
  meshUrl,
  markerScale = 1,
}: Props) {
  const ms = markerScale;
  // 場景尺度也跟著縮：1000 m 的格線配 25 m 一格，在 65 m 的走廊上等於沒有參考價值
  const sceneSize = SCENE_SIZE * ms;
  const camDist = 300 * ms;
  const [dragging, setDragging] = useState<DragTarget | null>(null);
  // 預設不載入：掃描檔動輒數十 MB，一按 3D 就下載會讓人以為當掉了。
  // 要看室內幾何時再自己打開。
  const [showMesh, setShowMesh] = useState(false);
  const [meshOpacity, setMeshOpacity] = useState(1);
  // 剖面高度（公尺）。null = 不切；切了才看得到走廊裡的人站在哪。
  const [cutHeight, setCutHeight] = useState<number | null>(2.0);
  const [tempPos, setTempPos] = useState<TempPos>(null);
  const [hovering, setHovering] = useState(false);
  // 分辨「點一下」與「拖過再放開」：拖曳結束後那一發 click 不該再加 waypoint
  const movedRef = useRef(false);
  // 拖曳結束要讀當下的 tempPos，但 handler 掛在 window 上不會跟著 re-render
  const tempPosRef = useRef<TempPos>(null);
  const draggingRef = useRef<DragTarget | null>(null);

  const bindDrag = useCallback(
    (target: DragTarget): DragBinding => ({
      onPointerDown: (e) => {
        e.stopPropagation();
        movedRef.current = false;
        draggingRef.current = target;
        tempPosRef.current = null;
        setDragging(target);
        setTempPos(null);
      },
      onPointerOver: () => setHovering(true),
      onPointerOut: () => setHovering(false),
    }),
    [],
  );

  const handleDragMove = useCallback(
    (x: number, z: number) => {
      const target = draggingRef.current;
      if (!target) return;
      movedRef.current = true;
      if (target.type === 'waypoint') {
        // Waypoint 需要即時反應（與 2D 視圖相同）
        onMoveWaypoint(target.idx, x, z);
      } else {
        // Buildings / gNBs / cells / UEs：拖曳中只預覽，放開才寫回
        tempPosRef.current = { x, z };
        setTempPos({ x, z });
      }
    },
    [onMoveWaypoint],
  );

  const handleDragEnd = useCallback(() => {
    const target = draggingRef.current;
    const pos = tempPosRef.current;
    draggingRef.current = null;
    tempPosRef.current = null;
    setDragging(null);
    setTempPos(null);
    if (!target || !pos) return;

    if (target.type === 'building') onMoveBuilding(target.name, pos.x, pos.z);
    else if (target.type === 'gnb') onMoveGnb(target.name, pos.x, pos.z);
    else if (target.type === 'cell') onMoveCell?.(target.gnbName, target.cellIdx, pos.x, pos.z);
    else if (target.type === 'ue') onMoveUE(target.name, pos.x, pos.z);
  }, [onMoveBuilding, onMoveGnb, onMoveCell, onMoveUE]);

  const selectedUe = trajectories[selectedUEIndex] ?? null;

  return (
    <div
      style={{
        width,
        height,
        background: '#0d0d1a',
        border: '1px solid #1a1a3e',
        borderRadius: 6,
        overflow: 'hidden',
        position: 'relative',
        cursor: dragging ? 'grabbing' : hovering ? 'move' : 'default',
      }}
      onContextMenu={(e) => e.preventDefault()} // 右鍵留給刪除 waypoint
    >
      {meshUrl && (
        <div
          style={{
            position: 'absolute', top: 8, left: 8, zIndex: 2,
            display: 'flex', flexDirection: 'column', gap: '6px',
            padding: '7px 9px', borderRadius: '5px',
            background: 'rgba(13,13,26,0.85)', border: '1px solid #1f1f3a',
            fontSize: '11px', color: '#9ca3af',
          }}
        >
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
            <input type="checkbox" checked={showMesh} onChange={(e) => setShowMesh(e.target.checked)} />
            載入匯入網格（掃描模型，數十 MB）
          </label>

          {showMesh && (
            <>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '52px' }}>透明度</span>
                <input
                  type="range" min={0.15} max={1} step={0.05} value={meshOpacity}
                  onChange={(e) => setMeshOpacity(parseFloat(e.target.value))}
                  style={{ width: '90px' }}
                />
                <span style={{ width: '28px' }}>{Math.round(meshOpacity * 100)}%</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '52px' }}>剖面</span>
                <input
                  type="checkbox"
                  checked={cutHeight !== null}
                  onChange={(e) => setCutHeight(e.target.checked ? 2.0 : null)}
                  title="切掉某個高度以上的幾何（天花板／上半段牆），從上方看進室內"
                />
                <input
                  type="range" min={0.5} max={8} step={0.1}
                  value={cutHeight ?? 8}
                  disabled={cutHeight === null}
                  onChange={(e) => setCutHeight(parseFloat(e.target.value))}
                  style={{ width: '90px' }}
                />
                <span style={{ width: '34px' }}>
                  {cutHeight === null ? '關' : `${cutHeight.toFixed(1)}m`}
                </span>
              </label>
            </>
          )}
        </div>
      )}

      <Canvas
        frameloop="demand"
        dpr={[1, 2]}
        camera={{
          position: [camDist, camDist, camDist],
          fov: 50,
          near: Math.max(0.01, 0.5 * ms),
          far: 5000 * Math.max(ms, 0.2),
        }}
        onPointerMissed={() => onSelectObject?.(null)}
      >
        <color attach="background" args={['#0d0d1a']} />
        <ambientLight intensity={0.55} />
        <directionalLight position={[300, 500, 200]} intensity={1.1} />
        <directionalLight position={[-300, 200, -200]} intensity={0.35} />

        {/* 地面：接住點擊以新增 waypoint（與 2D 視圖點背景的行為一致） */}
        <mesh
          position={[0, 0, 0]}
          rotation={[-Math.PI / 2, 0, 0]}
          onClick={(e) => {
            e.stopPropagation();
            // 剛結束一次拖曳（含 OrbitControls 轉視角）就不要順手加點
            if (movedRef.current) {
              movedRef.current = false;
              return;
            }
            onSelectObject?.(null);
            onAddWaypoint(e.point.x, e.point.z);
          }}
          onPointerDown={() => {
            movedRef.current = false;
          }}
          onPointerMove={(e) => {
            // 只有「按著鍵移動」才算轉視角；單純 hover 不能算，否則永遠加不了 waypoint
            if (!draggingRef.current && e.nativeEvent.buttons !== 0) movedRef.current = true;
          }}
        >
          <planeGeometry args={[sceneSize, sceneSize]} />
          <meshLambertMaterial color="#12122a" />
        </mesh>

        <Grid
          args={[sceneSize, sceneSize]}
          position={[0, 0.05 * ms, 0]}
          cellSize={25 * ms}
          cellColor="#1f1f3a"
          sectionSize={100 * ms}
          sectionColor="#333355"
          fadeDistance={2000 * Math.max(ms, 0.2)}
          infiniteGrid={false}
        />

        {/* 匯入網格：Suspense 讓載入中的其餘場景照常互動，載入失敗也不會整頁掛掉 */}
        {meshUrl && showMesh && (
          <Suspense fallback={null}>
            <ImportedMesh url={meshUrl} opacity={meshOpacity} cutHeight={cutHeight} />
          </Suspense>
        )}

        {coverageOverlay && <CoverageLayer overlay={coverageOverlay} />}
        {mapFootprints && mapFootprints.length > 0 && <Footprints footprints={mapFootprints} />}
        <Buildings
          buildings={buildings}
          onSelectObject={onSelectObject}
          dragging={dragging}
          tempPos={tempPos}
          bindDrag={bindDrag}
        />
        <GNBs
          gnbs={gnbs}
          onSelectObject={onSelectObject}
          dragging={dragging}
          tempPos={tempPos}
          bindDrag={bindDrag}
          ms={ms}
        />
        <UEs
          ues={ues}
          trajectories={trajectories}
          selectedUEIndex={selectedUEIndex}
          onSelectObject={onSelectObject}
          onSelectUEIndex={onSelectUEIndex}
          dragging={dragging}
          tempPos={tempPos}
          bindDrag={bindDrag}
          ms={ms}
        />
        {selectedUe?.waypoints && (
          <Waypoints
            waypoints={selectedUe.waypoints as [number, number, number][]}
            dragging={dragging}
            bindDrag={bindDrag}
            onRemoveWaypoint={onRemoveWaypoint}
            ms={ms}
          />
        )}
        <PathLayer pathA={pathA} pathB={pathB} plannedPath={plannedPath} ms={ms} />

        {/* 拖物件時停用 OrbitControls，否則會邊拖邊轉視角 */}
        <OrbitControls
          enabled={!dragging}
          enableDamping={false}
          maxPolarAngle={Math.PI / 2.05}
          target={[0, 0, 0]}
        />
        <DragController dragging={dragging} onDragMove={handleDragMove} onDragEnd={handleDragEnd} />
        <InvalidateOnChange
          deps={[
            buildings,
            gnbs,
            ues,
            trajectories,
            selectedUEIndex,
            coverageOverlay,
            mapFootprints,
            pathA,
            pathB,
            plannedPath,
            dragging,
            tempPos,
            showMesh,
            meshOpacity,
            cutHeight,
            ms,
          ]}
        />
      </Canvas>
    </div>
  );
}
