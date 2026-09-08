'use client';

import React, { useRef, useState, type MouseEvent as RMouseEvent } from 'react';
import type { Building, UE } from '@/types';

export const SCENE_MIN = -500;
export const SCENE_MAX = 500;

export function toRgb(c: number[] | undefined): string {
  if (!c || c.length < 3) return '#666';
  return `rgb(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)})`;
}

export interface CoverageOverlayData {
  grid: {
    x_range: [number, number]
    x_step: number
    z_range: [number, number]
    z_step: number
    n_rows: number
    n_cols: number
  }
  data: (number | null)[][]
  opacity?: number
}

export function valToRgb(val: number, min: number, max: number): [number, number, number] {
  const t = max > min ? Math.max(0, Math.min(1, (val - min) / (max - min))) : 0.5
  if (t < 0.5) {
    const s = t * 2
    return [0, Math.round(s * 255), Math.round((1 - s) * 255)]
  }
  const s = (t - 0.5) * 2
  return [Math.round(s * 255), Math.round((1 - s) * 255), 0]
}

export function valToColor(val: number, min: number, max: number): string {
  const [r, g, b] = valToRgb(val, min, max)
  return `rgb(${r},${g},${b})`
}

type DragTarget =
  | { type: 'waypoint'; idx: number }
  | { type: 'building'; name: string }
  | { type: 'gnb'; name: string }
  | { type: 'cell'; gnbName: string; cellIdx: number }   // 分散式 cell(有自己 position 才可拖)
  | { type: 'ue'; name: string };

export interface Props {
  width?: number;
  height?: number;
  buildings: Building[];
  gnbs: any[];
  ues: any[];
  selectedUEIndex: number;
  trajectories: UE[];
  onAddWaypoint: (x: number, z: number) => void;
  onMoveWaypoint: (idx: number, x: number, z: number) => void;
  onRemoveWaypoint: (idx: number) => void;
  onMoveBuilding: (name: string, x: number, z: number) => void;
  onMoveGnb: (name: string, x: number, z: number) => void;
  onMoveCell?: (gnbName: string, cellIdx: number, x: number, z: number) => void;
  onMoveUE: (name: string, x: number, z: number) => void;
  onSelectObject?: (obj: { type: 'building' | 'gnb' | 'ue'; name: string } | null) => void;
  onSelectUEIndex?: (idx: number) => void;
  coverageOverlay?: CoverageOverlayData;
  mapFootprints?: { points: [number, number][]; height: number }[];
  // 路徑規劃:A/B 端點與規劃出的路線(繞過建築)
  pathA?: [number, number] | null;
  pathB?: [number, number] | null;
  plannedPath?: [number, number][];
  // 匯入網格(.glb)的絕對 URL。只有 3D 視圖會用；2D 俯視圖忽略它。
  meshUrl?: string;
  // 標記尺寸係數。gNB/UE/覆蓋圈的預設尺寸是城市尺度(公尺級塔與百公尺覆蓋)，
  // 放進 14 m 寬的室內走廊會把場景整個蓋掉 → 室內場景傳 0.1 之類的小值。
  markerScale?: number;
}

// 依樓高上色(對齊 3D 的 viridis 感):矮=深藍紫、高=青黃
export function footprintColor(h: number): string {
  const t = Math.max(0, Math.min(1, h / 50));
  const r = Math.round(40 + t * 180);
  const g = Math.round(50 + t * 150);
  const b = Math.round(120 - t * 60);
  return `rgb(${r},${g},${b})`;
}

export function TopDownMap({
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
}: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [dragging, setDragging] = useState<DragTarget | null>(null);
  const [tempPos, setTempPos] = useState<{ x: number; z: number } | null>(null);

  const sx = (x: number) => width - ((x - SCENE_MIN) / (SCENE_MAX - SCENE_MIN)) * width;
  const sz = (z: number) => height - ((z - SCENE_MIN) / (SCENE_MAX - SCENE_MIN)) * height;
  const invertX = (px: number) => SCENE_MIN + ((width - px) / width) * (SCENE_MAX - SCENE_MIN);
  const invertZ = (py: number) => SCENE_MIN + ((height - py) / height) * (SCENE_MAX - SCENE_MIN);

  const svgCoords = (ev: RMouseEvent<SVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, z: 0 };
    const rect = svg.getBoundingClientRect();
    return {
      x: invertX(ev.clientX - rect.left),
      z: invertZ(ev.clientY - rect.top),
    };
  };

  const handleBgClick = (ev: RMouseEvent<SVGRectElement>) => {
    onSelectObject?.(null);
    const { x, z } = svgCoords(ev);
    onAddWaypoint(x, z);
  };

  const handleDragStart =
    (target: DragTarget) =>
    (ev: RMouseEvent<SVGElement>) => {
      ev.stopPropagation();
      setDragging(target);
    };

  const handleDrag = (ev: RMouseEvent<SVGElement>) => {
    if (!dragging) return;
    const { x, z } = svgCoords(ev);

    if (dragging.type === 'waypoint') {
      // Waypoint 需要即時反應
      onMoveWaypoint(dragging.idx, x, z);
    } else {
      // Buildings、gNBs、UEs：只預覽位置，不呼叫回調
      setTempPos({ x, z });
    }
  };

  const handleDragEnd = () => {
    if (!dragging || !tempPos) {
      setDragging(null);
      setTempPos(null);
      return;
    }

    // 拖動結束時才保存到 DB
    if (dragging.type === 'building') {
      onMoveBuilding(dragging.name, tempPos.x, tempPos.z);
    } else if (dragging.type === 'gnb') {
      onMoveGnb(dragging.name, tempPos.x, tempPos.z);
    } else if (dragging.type === 'cell') {
      onMoveCell?.(dragging.gnbName, dragging.cellIdx, tempPos.x, tempPos.z);
    } else if (dragging.type === 'ue') {
      onMoveUE(dragging.name, tempPos.x, tempPos.z);
    }

    setDragging(null);
    setTempPos(null);
  };

  const handleWaypointContextMenu =
    (idx: number) =>
    (ev: RMouseEvent<SVGCircleElement>) => {
      ev.preventDefault();
      ev.stopPropagation();
      onRemoveWaypoint(idx);
    };

  const selectedUe = trajectories[selectedUEIndex] || null;

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      onMouseMove={handleDrag}
      onMouseUp={handleDragEnd}
      onMouseLeave={handleDragEnd}
      style={{
        background: '#0d0d1a',
        border: '1px solid #1a1a3e',
        borderRadius: 6,
        display: 'block',
      }}
    >
      {/* Background (clickable to add waypoints) */}
      <rect x={0} y={0} width={width} height={height} fill="transparent" onClick={handleBgClick} />

      {/* Grid and static overlays */}
      <g style={{ pointerEvents: 'none' }}>
        {/* Grid lines every 100m */}
        {[-500, -400, -300, -200, -100, 0, 100, 200, 300, 400, 500].map((v) => (
          <g key={`grid-${v}`}>
            <line x1={sx(v)} y1={0} x2={sx(v)} y2={height} stroke="#1f1f3a" strokeWidth={1} />
            <line x1={0} y1={sz(v)} x2={width} y2={sz(v)} stroke="#1f1f3a" strokeWidth={1} />
            <text x={sx(v) + 3} y={sz(0) - 3} fill="#555" fontSize={9}>
              {v === 0 ? '' : `${v}m`}
            </text>
            <text x={sx(0) + 3} y={sz(v) - 3} fill="#555" fontSize={9}>
              {v === 0 ? '' : `${v}m`}
            </text>
          </g>
        ))}

        {/* Axes */}
        <line x1={0} y1={sz(0)} x2={width} y2={sz(0)} stroke="#333" strokeWidth={1} />
        <line x1={sx(0)} y1={0} x2={sx(0)} y2={height} stroke="#333" strokeWidth={1} />
      </g>

      {/* Coverage Overlay */}
      {coverageOverlay && (() => {
        const { grid, data, opacity = 0.65 } = coverageOverlay
        const cellW = (grid.x_step / (SCENE_MAX - SCENE_MIN)) * width
        const cellH = (grid.z_step / (SCENE_MAX - SCENE_MIN)) * height
        const flat = data.flat().filter((v): v is number => v !== null)
        if (!flat.length) return null
        const minV = Math.min(...flat)
        const maxV = Math.max(...flat)
        return (
          <g opacity={opacity} style={{ pointerEvents: 'none' }}>
            {data.map((row, zi) =>
              row.map((val, xi) => {
                if (val === null) return null
                const sceneX = grid.x_range[0] + xi * grid.x_step
                const sceneZ = grid.z_range[1] - zi * grid.z_step
                return (
                  <rect
                    key={`coverage-${zi}-${xi}`}
                    x={sx(sceneX) - cellW}
                    y={sz(sceneZ)}
                    width={cellW}
                    height={cellH}
                    fill={valToColor(val, minV, maxV)}
                  />
                )
              })
            )}
          </g>
        )
      })()}

      {/* Map footprints (OSM 校園輪廓,背景層,不可互動) */}
      {mapFootprints && mapFootprints.length > 0 && (
        <g style={{ pointerEvents: 'none' }}>
          {mapFootprints.map((f, i) => (
            <polygon
              key={`fp-${i}`}
              points={f.points.map(([x, z]) => `${sx(x)},${sz(z)}`).join(' ')}
              fill={footprintColor(f.height)}
              fillOpacity={0.55}
              stroke="#1a1a2a"
              strokeWidth={0.5}
            />
          ))}
        </g>
      )}

      {/* 路徑規劃圖層:A/B 端點 + 繞過建築的規劃路線 */}
      {(pathA || pathB || (plannedPath && plannedPath.length > 1)) && (
        <g style={{ pointerEvents: 'none' }}>
          {/* 直線對照(虛線,可能穿牆) */}
          {pathA && pathB && (
            <line x1={sx(pathA[0])} y1={sz(pathA[1])} x2={sx(pathB[0])} y2={sz(pathB[1])}
                  stroke="#ef4444" strokeWidth={1.5} strokeDasharray="6 4" opacity={0.7} />
          )}
          {/* 規劃路徑 */}
          {plannedPath && plannedPath.length > 1 && (
            <>
              <polyline
                points={plannedPath.map(([x, z]) => `${sx(x)},${sz(z)}`).join(' ')}
                fill="none" stroke="#22c55e" strokeWidth={3}
                strokeLinejoin="round" strokeLinecap="round"
              />
              {plannedPath.map(([x, z], i) => (
                <circle key={`pp-${i}`} cx={sx(x)} cy={sz(z)} r={3.5}
                        fill="#22c55e" stroke="#0b1220" strokeWidth={1} />
              ))}
            </>
          )}
          {pathA && (
            <g>
              <circle cx={sx(pathA[0])} cy={sz(pathA[1])} r={7} fill="#f59e0b" stroke="#fff" strokeWidth={2} />
              <text x={sx(pathA[0]) + 10} y={sz(pathA[1]) - 8} fill="#f59e0b" fontSize={13} fontWeight="bold">A</text>
            </g>
          )}
          {pathB && (
            <g>
              <circle cx={sx(pathB[0])} cy={sz(pathB[1])} r={7} fill="#ef4444" stroke="#fff" strokeWidth={2} />
              <text x={sx(pathB[0]) + 10} y={sz(pathB[1]) - 8} fill="#ef4444" fontSize={13} fontWeight="bold">B</text>
            </g>
          )}
        </g>
      )}

      {/* Main interactive layer */}
      <g style={{ pointerEvents: 'auto' }}>
        {/* Buildings */}
        {buildings.map((b) => {
          const isBeingDragged = dragging?.type === 'building' && dragging.name === b.name;
          const bx = isBeingDragged && tempPos ? tempPos.x : b.position[0];
          const bz = isBeingDragged && tempPos ? tempPos.z : b.position[2];
          const sx_val = b.size[0];
          const sz_val = b.size[2];
          const px = sx(bx + sx_val / 2);
          const py = sz(bz + sz_val / 2);
          const pw = (sx_val / (SCENE_MAX - SCENE_MIN)) * width;
          const ph = (sz_val / (SCENE_MAX - SCENE_MIN)) * height;
          return (
            <g key={`building-${b.name}`} opacity={isBeingDragged ? 0.7 : 1}
               onClick={() => onSelectObject?.({ type: 'building', name: b.name })}
               style={{ cursor: 'pointer', pointerEvents: 'auto' }}>
              <rect x={px} y={py} width={pw} height={ph} fill="#38384a" stroke={isBeingDragged ? '#88ff88' : '#5a5a7a'} strokeWidth={isBeingDragged ? 2 : 1} />
              <text x={px + 3} y={py + ph - 3} fill="#aaa" fontSize={9}>
                {b.name}
              </text>
            </g>
          );
        })}

        {/* gNBs */}
        {gnbs.map((g) => {
          const isBeingDragged = dragging?.type === 'gnb' && dragging.name === g.name;
          const gx = isBeingDragged && tempPos ? tempPos.x : g.position[0];
          const gz = isBeingDragged && tempPos ? tempPos.z : g.position[2];
          const px = sx(gx);
          const py = sz(gz);
          const color = toRgb(g.color);
          const coverageR = (37.5 / (SCENE_MAX - SCENE_MIN)) * width;
          // AK8 UX: 為每個 sector 畫 azimuth 箭頭。Sionna 慣例 azimuth=0 沿 +X 軸；
          // 而 sx() 把 +X 鏡到螢幕左 → 0° 箭頭視覺指向螢幕左邊（與使用者觀察一致）。
          // 用 sx/sz 映射端點，自動套用同一個鏡射 + 縮放，不用手算 screen delta。
          // 每個 sector 帶自己的世界座標:有 cell.position(分散式/DAS)畫在該處且可拖;
          // 沒有(扇區模式)畫在 gNB 中心,拖曳走整站。拖曳中的 cell 用 tempPos 預覽。
          const sectors: Array<{ az: number; pci?: number; cx: number; cz: number; movable: boolean; idx: number }> =
            (g.cells && g.cells.length > 0)
              ? g.cells.map((c: any, ci: number) => {
                  const dragMe = dragging?.type === 'cell' && dragging.gnbName === g.name && dragging.cellIdx === ci;
                  const hasPos = Array.isArray(c.position) && c.position.length >= 3;
                  return {
                    az: c.azimuth_deg ?? 0, pci: c.pci, idx: ci, movable: hasPos,
                    cx: dragMe && tempPos ? tempPos.x : (hasPos ? c.position[0] : gx),
                    cz: dragMe && tempPos ? tempPos.z : (hasPos ? c.position[2] : gz),
                  };
                })
              : [{ az: g.azimuth_deg ?? 0, pci: g.pci, cx: gx, cz: gz, movable: false, idx: 0 }];
          const arrowLenM = 40; // 世界座標 40 m；視覺長度依場景縮放跟著變
          return (
            <g key={`gnb-${g.name}`} opacity={isBeingDragged ? 0.7 : 1}
               style={{ cursor: 'pointer', pointerEvents: 'auto' }}>
              {/* Coverage circle (dashed) - clickable */}
              <circle
                cx={px}
                cy={py}
                r={coverageR}
                fill={color}
                fillOpacity={0.08}
                stroke={color}
                strokeOpacity={0.5}
                strokeDasharray={isBeingDragged ? '2,2' : '4,4'}
                strokeWidth={isBeingDragged ? 2 : 1}
                onClick={() => onSelectObject?.({ type: 'gnb', name: g.name })}
                style={{ cursor: 'pointer' }}
              />
              {/* Azimuth arrows per sector — 箭頭從 sector 自身座標出發,尖端標 PCI */}
              {sectors.map((s, idx) => {
                const azRad = (s.az * Math.PI) / 180;
                const scx = sx(s.cx);
                const scy = sz(s.cz);
                const endX = s.cx + arrowLenM * Math.cos(azRad);
                const endZ = s.cz + arrowLenM * Math.sin(azRad);
                const ex = sx(endX);
                const ey = sz(endZ);
                return (
                  <g key={`gnb-${g.name}-sec-${idx}`} pointerEvents="none">
                    {/* 分散式 cell:與母站連一條淡虛線 + 可拖曳的方形圖示 */}
                    {s.movable && (
                      <>
                        <line x1={px} y1={py} x2={scx} y2={scy}
                          stroke={color} strokeWidth={1} strokeOpacity={0.35} strokeDasharray="3,4" />
                        <rect
                          x={scx - 6} y={scy - 6} width={12} height={12}
                          fill={color} fillOpacity={0.9} stroke="#fff" strokeWidth={1.5}
                          transform={`rotate(45 ${scx} ${scy})`}
                          pointerEvents="auto"
                          style={{ cursor: 'move' }}
                          onMouseDown={handleDragStart({ type: 'cell', gnbName: g.name, cellIdx: s.idx })}
                        />
                      </>
                    )}
                    <line
                      x1={scx} y1={scy} x2={ex} y2={ey}
                      stroke={color} strokeWidth={2} strokeOpacity={0.85}
                      markerEnd={`url(#az-arrow-${g.name}-${idx})`}
                    />
                    {s.pci !== undefined && (
                      <text
                        x={ex} y={ey - 4}
                        fill={color} fontSize={9} fontWeight={500}
                        textAnchor="middle"
                      >
                        pci{s.pci}
                      </text>
                    )}
                    <defs>
                      <marker
                        id={`az-arrow-${g.name}-${idx}`}
                        viewBox="0 0 10 10" refX="9" refY="5"
                        markerWidth="6" markerHeight="6" orient="auto-start-reverse"
                      >
                        <path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
                      </marker>
                    </defs>
                  </g>
                );
              })}
              {/* Center dot */}
              <circle
                cx={px}
                cy={py}
                r={isBeingDragged ? 10 : 8}
                fill={color}
                stroke={isBeingDragged ? '#ffff00' : '#fff'}
                strokeWidth={isBeingDragged ? 2 : 1}
                onClick={() => onSelectObject?.({ type: 'gnb', name: g.name })}
                style={{ cursor: 'pointer' }}
              />
              {/* Label */}
              <text x={px + 9} y={py - 6} fill={color} fontSize={10} fontWeight={600} pointerEvents="none">
                {g.name}
              </text>
            </g>
          );
        })}

        {/* All UE circles — selected gets bigger / yellow, others smaller / orange.
            Click on any UE switches both the trajectory edit target and the
            detail panel selection in one go. */}
        {ues.map((u, idx) => {
          const isSelected = idx === selectedUEIndex;
          const livePos = trajectories.find((t) => t.name === u.name)?.position;
          const pos = livePos ?? u.position;
          const px = sx(pos[0]);
          const py = sz(pos[2]);
          return (
            <g
              key={`ue-${u.name}`}
              onClick={() => {
                onSelectObject?.({ type: 'ue', name: u.name });
                onSelectUEIndex?.(idx);
              }}
              style={{ cursor: 'pointer', pointerEvents: 'auto' }}
            >
              <circle
                cx={px}
                cy={py}
                r={isSelected ? 8 : 5}
                fill={isSelected ? '#FFC107' : '#FF9800'}
                stroke="#fff"
                strokeWidth={isSelected ? 1.5 : 0.5}
              />
              <text
                x={px + (isSelected ? 10 : 8)}
                y={py + (isSelected ? 4 : 3)}
                fill={isSelected ? '#FFC107' : '#aaa'}
                fontSize={isSelected ? 11 : 9}
                fontWeight={isSelected ? 700 : 400}
              >
                {u.name}
              </text>
            </g>
          );
        })}

        {/* All UE trajectories — selected drawn solid green, others dimmed grey.
            Lets users see every UE's path at once instead of only the active one. */}
        {trajectories.map((t, idx) => {
          if (!t.waypoints || t.waypoints.length === 0) return null;
          const isSelected = idx === selectedUEIndex;
          // 每個 UE 一個固定色相,未選取也清楚可辨(舊版灰色 40% 在地圖輪廓上近乎隱形)
          const TRAJ_COLORS = ['#f59e0b', '#3b82f6', '#ec4899', '#22d3ee', '#a78bfa', '#f97316', '#84cc16'];
          const stroke = isSelected ? '#4CAF50' : TRAJ_COLORS[idx % TRAJ_COLORS.length];
          const opacity = isSelected ? 1 : 0.85;
          const polylineWidth = isSelected ? 2.5 : 1.5;
          const dash = isSelected ? '6,3' : '5,3';
          return (
            <g key={`traj-${t.name}`} opacity={opacity}>
              {t.waypoints.length > 1 && (
                <polyline
                  points={t.waypoints.map((w) => `${sx(w[0])},${sz(w[2])}`).join(' ')}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={polylineWidth}
                  strokeDasharray={dash}
                />
              )}
              {/* Leader line from UE pos to first waypoint — only for selected UE */}
              {isSelected && (
                <line
                  x1={sx(t.position[0])}
                  y1={sz(t.position[2])}
                  x2={sx(t.waypoints[0][0])}
                  y2={sz(t.waypoints[0][2])}
                  stroke={stroke}
                  strokeWidth={1}
                  strokeDasharray="2,4"
                  strokeOpacity={0.4}
                />
              )}
            </g>
          );
        })}
      </g>

      {/* Draggable waypoint handles */}
      {selectedUe &&
        selectedUe.waypoints &&
        selectedUe.waypoints.map((w, idx) => {
          const px = sx(w[0]);
          const py = sz(w[2]);
          return (
            <g key={`wp-${idx}`}>
              <circle
                cx={px}
                cy={py}
                r={8}
                fill={dragging?.type === 'waypoint' && dragging.idx === idx ? '#FFD54F' : '#4CAF50'}
                stroke="#fff"
                strokeWidth={2}
                onMouseDown={handleDragStart({ type: 'waypoint', idx })}
                onContextMenu={handleWaypointContextMenu(idx)}
                style={{ cursor: 'grab' }}
              />
              <text
                x={px}
                y={py + 3}
                textAnchor="middle"
                fill="#fff"
                fontSize={9}
                fontWeight={700}
                pointerEvents="none"
              >
                {idx + 1}
              </text>
            </g>
          );
        })}

      {/* Draggable building handles */}
      {buildings.map((b) => {
        const bx = b.position[0];
        const bz = b.position[2];
        const px = sx(bx);
        const py = sz(bz);
        return (
          <circle
            key={`drag-building-${b.name}`}
            cx={px}
            cy={py}
            r={15}
            fill="transparent"
            stroke={dragging?.type === 'building' && dragging.name === b.name ? '#88ff88' : 'transparent'}
            strokeWidth={2}
            onMouseDown={handleDragStart({ type: 'building', name: b.name })}
            style={{ cursor: 'move', pointerEvents: 'auto' }}
          />
        );
      })}

      {/* Draggable gNB handles */}
      {gnbs.map((g) => {
        const px = sx(g.position[0]);
        const py = sz(g.position[2]);
        return (
          <circle
            key={`drag-gnb-${g.name}`}
            cx={px}
            cy={py}
            r={15}
            fill="transparent"
            stroke={dragging?.type === 'gnb' && dragging.name === g.name ? '#ffff00' : 'transparent'}
            strokeWidth={2}
            onMouseDown={handleDragStart({ type: 'gnb', name: g.name })}
            style={{ cursor: 'move', pointerEvents: 'auto' }}
          />
        );
      })}

      {/* Draggable UE handles */}
      {ues.map((u) => {
        const px = sx(u.position[0]);
        const py = sz(u.position[2]);
        return (
          <circle
            key={`drag-ue-${u.name}`}
            cx={px}
            cy={py}
            r={15}
            fill="transparent"
            stroke={dragging?.type === 'ue' && dragging.name === u.name ? '#FFC107' : 'transparent'}
            strokeWidth={2}
            onMouseDown={handleDragStart({ type: 'ue', name: u.name })}
            style={{ cursor: 'move', pointerEvents: 'auto' }}
          />
        );
      })}
    </svg>
  );
}
