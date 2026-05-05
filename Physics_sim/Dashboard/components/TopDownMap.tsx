'use client';

import React, { useRef, useState, type MouseEvent as RMouseEvent } from 'react';
import type { Building, UE } from '@/types';

const SCENE_MIN = -500;
const SCENE_MAX = 500;

function toRgb(c: number[] | undefined): string {
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

function valToColor(val: number, min: number, max: number): string {
  const t = max > min ? Math.max(0, Math.min(1, (val - min) / (max - min))) : 0.5
  if (t < 0.5) {
    const s = t * 2
    return `rgb(0,${Math.round(s * 255)},${Math.round((1 - s) * 255)})`
  }
  const s = (t - 0.5) * 2
  return `rgb(${Math.round(s * 255)},${Math.round((1 - s) * 255)},0)`
}

type DragTarget =
  | { type: 'waypoint'; idx: number }
  | { type: 'building'; name: string }
  | { type: 'gnb'; name: string }
  | { type: 'ue'; name: string };

interface Props {
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
  onMoveUE: (name: string, x: number, z: number) => void;
  onSelectObject?: (obj: { type: 'building' | 'gnb' | 'ue'; name: string } | null) => void;
  onSelectUEIndex?: (idx: number) => void;
  coverageOverlay?: CoverageOverlayData;
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
  onMoveUE,
  onSelectObject,
  onSelectUEIndex,
  coverageOverlay,
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
          const stroke = isSelected ? '#4CAF50' : '#9E9E9E';
          const opacity = isSelected ? 1 : 0.4;
          const polylineWidth = isSelected ? 2 : 1;
          const dash = isSelected ? '6,3' : '4,4';
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
