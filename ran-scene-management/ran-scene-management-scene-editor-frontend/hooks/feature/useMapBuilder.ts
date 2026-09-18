'use client';
import { useCallback, useMemo, useState } from 'react';
import { MAX_MAP_AREA_M2 } from '@/config';
import { landmarkHalfSize, polygonAreaM2, squareAround } from '@/hooks/feature/geo';
import { buildOsmScene, geocodeLandmark, previewOsmArea } from '@/services/api/geometry';
import type { GeocodeResult, LatLon, OsmBuildResult, OsmBuilding } from '@/types/geometry';

type Busy = 'geocode' | 'preview' | 'build' | null;
export interface FlyTo { lat: number; lon: number; zoom: number; key: number }

/** 從地圖建立場景:搜尋地標 → 自動框一版 → 使用者調整多邊形 → 讀範圍內建築 → 逐棟設定材質 / 高度 / 排除 → 產生場景 */
export function useMapBuilder(sceneUuid: string, onBuilt: (r: OsmBuildResult) => void) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [polygon, setPolygonRaw] = useState<LatLon[]>([]);
  const [drawing, setDrawing] = useState<LatLon[] | null>(null);   // 非 null = 正在逐點畫新多邊形
  const [buildings, setBuildings] = useState<OsmBuilding[]>([]);
  const [previewedFor, setPreviewedFor] = useState<string>('');     // 讀建築時的多邊形,改過範圍就提示重讀
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [flyTo, setFlyTo] = useState<FlyTo | null>(null);

  const run = useCallback(async <T,>(b: Busy, fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(b); setError(null);
    try { return await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); return undefined; } finally { setBusy(null); }
  }, []);

  const search = () => run('geocode', async () => { const r = await geocodeLandmark(query); setResults(r); if (r[0]) pick(r[0]); else setError('找不到這個地標'); });
  /** 選定地標:飛過去,以地標為中心自動框一個正方形(半邊 100–300 m) */
  const pick = (g: GeocodeResult) => {
    setPolygonRaw(squareAround(g.lat, g.lon, landmarkHalfSize(g.bbox)));
    setDrawing(null); setBuildings([]); setSelected(new Set());
    setFlyTo({ lat: g.lat, lon: g.lon, zoom: 17, key: Date.now() });
  };
  const setPolygon = (p: LatLon[]) => setPolygonRaw(p);
  const startDraw = () => { setDrawing([]); setBuildings([]); setSelected(new Set()); };
  const addDrawPoint = (p: LatLon) => setDrawing((d) => (d ? [...d, p] : d));
  const finishDraw = () => { if (drawing && drawing.length >= 3) setPolygonRaw(drawing); setDrawing(null); };
  const cancelDraw = () => setDrawing(null);

  const area = useMemo(() => polygonAreaM2(polygon), [polygon]);
  const polyKey = JSON.stringify(polygon);
  const stale = buildings.length > 0 && previewedFor !== polyKey;
  const preview = () => run('preview', async () => {
    const r = await previewOsmArea(polygon);
    setBuildings(r.buildings); setSelected(new Set()); setPreviewedFor(JSON.stringify(polygon));
    if (!r.buildings.length) setError('範圍內沒有 OSM 建築資料');
  });

  /** 點建築:一般點 = 只選這棟;加按 Shift / Ctrl = 加入或移出選取 */
  const toggle = (id: string, additive: boolean) => setSelected((s) => {
    if (!additive) return s.size === 1 && s.has(id) ? new Set() : new Set([id]);
    const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n;
  });
  const selectAll = () => setSelected(new Set(buildings.filter((b) => !b.excluded).map((b) => b.id)));
  const selectByMaterial = (m: string) => setSelected(new Set(buildings.filter((b) => b.material === m && !b.excluded).map((b) => b.id)));
  const clearSelection = () => setSelected(new Set());
  const patchSelected = (f: Partial<OsmBuilding>) => setBuildings((bs) => bs.map((b) => (selected.has(b.id) ? { ...b, ...f } : b)));

  const counts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const b of buildings) if (!b.excluded) m[b.material] = (m[b.material] ?? 0) + 1;
    return m;
  }, [buildings]);
  const included = buildings.filter((b) => !b.excluded);
  const blocked = polygon.length < 3 ? '先搜尋地標或畫一個範圍'
    : area > MAX_MAP_AREA_M2 ? `範圍 ${(area / 1e6).toFixed(2)} km² 超過上限 ${MAX_MAP_AREA_M2 / 1e6} km²`
    : !buildings.length ? '先讀取範圍內建築' : stale ? '範圍改過了,請重新讀取建築' : !included.length ? '所有建築都被排除了' : null;
  const build = (name: string) => run('build', async () => {
    const r = await buildOsmScene({ scene_uuid: sceneUuid, name, polygon, buildings: included });
    onBuilt(r);
  });

  return {
    query, setQuery, results, search, pick, busy, error, polygon, setPolygon, drawing, startDraw, addDrawPoint, finishDraw, cancelDraw,
    area, buildings, stale, preview, selected, toggle, selectAll, selectByMaterial, clearSelection, patchSelected, counts, included, blocked, build, flyTo,
  };
}
export type MapBuilder = ReturnType<typeof useMapBuilder>;
