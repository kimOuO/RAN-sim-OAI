'use client';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useEffect, useMemo, useState } from 'react';
import { MapContainer, Marker, Polygon, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import { MAP_BASEMAPS, MAP_TAIWAN, MATERIAL_COLORS, MATERIAL_LABELS } from '@/config';
import { midpoint } from '@/hooks/feature/geo';
import type { FlyTo } from '@/hooks/feature/useMapBuilder';
import type { LatLon, OsmBuilding } from '@/types/geometry';

interface Props {
  polygon: LatLon[]; drawing: LatLon[] | null; buildings: OsmBuilding[]; selected: Set<string>; flyTo: FlyTo | null;
  onPolygon: (p: LatLon[]) => void; onDrawPoint: (p: LatLon) => void; onFinishDraw: () => void; onBuilding: (id: string, additive: boolean) => void;
}

const vertexIcon = L.divIcon({ className: 'map-vertex', iconSize: [12, 12] });
const midIcon = L.divIcon({ className: 'map-vertex mid', iconSize: [10, 10] });

/** 地圖:範圍多邊形(拖頂點調整、拖邊中點插入頂點、雙擊頂點刪除)、逐點畫新範圍、範圍內建築依材質上色可點選 */
export default function MapCanvas(p: Props) {
  const [base, setBase] = useState<keyof typeof MAP_BASEMAPS>('dark');
  const bm = MAP_BASEMAPS[base];
  return (
    <div className="mapcanvas">
      <MapContainer center={[MAP_TAIWAN.lat, MAP_TAIWAN.lon]} zoom={MAP_TAIWAN.zoom} maxZoom={20} style={{ height: '100%', width: '100%' }} doubleClickZoom={false}>
        <TileLayer key={base} url={bm.url} attribution={bm.attribution} maxZoom={20} maxNativeZoom={bm.maxNativeZoom} />
        <Fly to={p.flyTo} />
        <Clicks drawing={p.drawing != null} onPoint={p.onDrawPoint} />
        {p.buildings.map((b) => <BuildingShape key={b.id} b={b} selected={p.selected.has(b.id)} onClick={p.onBuilding} />)}
        {p.drawing ? <DrawingPath pts={p.drawing} onFinish={p.onFinishDraw} /> : <AreaEditor polygon={p.polygon} onChange={p.onPolygon} />}
      </MapContainer>
      <div className="map-basemap">{(Object.keys(MAP_BASEMAPS) as (keyof typeof MAP_BASEMAPS)[]).map((k) =>
        <button key={k} className={k === base ? 'on' : ''} onClick={() => setBase(k)}>{MAP_BASEMAPS[k].label}</button>)}</div>
      {p.drawing && <div className="map-hint">點地圖加頂點;點第一個頂點或按「完成」收合({p.drawing.length} 點)</div>}
    </div>
  );
}

function Fly({ to }: { to: FlyTo | null }) {
  const map = useMap();
  useEffect(() => { if (to) map.flyTo([to.lat, to.lon], to.zoom, { duration: 1.2 }); }, [to, map]);
  return null;
}

function Clicks({ drawing, onPoint }: { drawing: boolean; onPoint: (p: LatLon) => void }) {
  const map = useMapEvents({ click: (e) => { if (drawing) onPoint([e.latlng.lat, e.latlng.lng]); } });
  useEffect(() => { map.getContainer().style.cursor = drawing ? 'crosshair' : ''; }, [drawing, map]);
  return null;
}

function AreaEditor({ polygon, onChange }: { polygon: LatLon[]; onChange: (p: LatLon[]) => void }) {
  if (polygon.length < 3) return null;
  const move = (i: number, ll: L.LatLng) => onChange(polygon.map((q, j) => (j === i ? [ll.lat, ll.lng] : q)));
  const insert = (i: number, ll: L.LatLng) => onChange([...polygon.slice(0, i + 1), [ll.lat, ll.lng], ...polygon.slice(i + 1)]);
  const remove = (i: number) => { if (polygon.length > 3) onChange(polygon.filter((_, j) => j !== i)); };
  return (
    <>
      <Polygon positions={polygon} pathOptions={{ color: '#ff8a3d', weight: 2, fillOpacity: 0.06, dashArray: '6 4' }} interactive={false} />
      {polygon.map((q, i) => (
        <Marker key={`v${i}`} position={q} icon={vertexIcon} draggable
          eventHandlers={{ drag: (e) => move(i, (e.target as L.Marker).getLatLng()), dblclick: () => remove(i) }}>
          <Tooltip direction="top" offset={[0, -6]}>拖曳移動 · 雙擊刪除</Tooltip>
        </Marker>))}
      {polygon.map((q, i) => { const n = polygon[(i + 1) % polygon.length]; return (
        <Marker key={`m${i}-${polygon.length}`} position={midpoint(q, n)} icon={midIcon} draggable
          eventHandlers={{ dragend: (e) => insert(i, (e.target as L.Marker).getLatLng()) }}>
          <Tooltip direction="top" offset={[0, -6]}>拖曳新增頂點</Tooltip>
        </Marker>); })}
    </>
  );
}

function DrawingPath({ pts, onFinish }: { pts: LatLon[]; onFinish: () => void }) {
  return (
    <>
      {pts.length > 1 && <Polyline positions={pts} pathOptions={{ color: '#ff8a3d', weight: 2, dashArray: '4 4' }} />}
      {pts.map((q, i) => <Marker key={i} position={q} icon={vertexIcon} eventHandlers={i === 0 && pts.length >= 3 ? { click: onFinish } : {}} />)}
    </>
  );
}

function BuildingShape({ b, selected, onClick }: { b: OsmBuilding; selected: boolean; onClick: (id: string, additive: boolean) => void }) {
  const color = MATERIAL_COLORS[b.material] ?? '#9e9e99';
  const positions = useMemo(() => [b.outer, ...b.inner], [b.outer, b.inner]);
  return (
    <Polygon positions={positions}
      pathOptions={b.excluded ? { color: '#5b6778', weight: 1, dashArray: '3 3', fillOpacity: 0.05 }
        : { color: selected ? '#4fd1ff' : color, weight: selected ? 3 : 1, fillColor: color, fillOpacity: selected ? 0.75 : 0.5 }}
      eventHandlers={{ click: (e) => { L.DomEvent.stopPropagation(e); const oe = e.originalEvent as MouseEvent; onClick(b.id, oe.shiftKey || oe.ctrlKey || oe.metaKey); } }}>
      <Tooltip sticky>{b.name} · {MATERIAL_LABELS[b.material] ?? b.material} · {b.height_m} m{b.height_known ? '' : '(預設)'}{b.excluded ? ' · 已排除' : ''}</Tooltip>
    </Polygon>
  );
}
