import { REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { Building, Cell, Du, Gnb, Ru, Ue, UeTraffic } from '@/types/registry';

const R = `${REGISTRY_API}/Equipment_ran`; const L = `${REGISTRY_API}/Field_scene`; const U = `${REGISTRY_API}/Equipment_ue`;
export const createGnb = (body: Partial<Gnb> & { f_scene_uuid: string }) => post<Gnb>(`${R}/GnbController/create`, body);
export const updateGnb = (gnb_uuid: string, body: Partial<Gnb>) => post<Gnb>(`${R}/GnbController/update`, { gnb_uuid, ...body });
export const deleteGnb = (gnb_uuid: string) => post<{ deleted: number }>(`${R}/GnbController/delete`, { gnb_uuid });
export const createDu = (body: Partial<Du> & { f_gnb_uuid: string }) => post<Du>(`${R}/DuController/create`, body);
export const updateDu = (du_uuid: string, body: Partial<Du>) => post<Du>(`${R}/DuController/update`, { du_uuid, ...body });
export const createCell = (body: Partial<Cell> & { f_du_uuid: string }) => post<Cell>(`${R}/CellController/create`, body);
export const updateCell = (cell_uuid: string, body: Partial<Cell>) => post<Cell>(`${R}/CellController/update`, { cell_uuid, ...body });
export const deleteCell = (cell_uuid: string) => post<{ deleted: number }>(`${R}/CellController/delete`, { cell_uuid });
export const createRu = (body: Partial<Ru> & { f_cell_uuid: string }) => post<Ru>(`${R}/RuController/create`, body);
export const updateRu = (ru_uuid: string, body: Partial<Ru>) => post<Ru>(`${R}/RuController/update`, { ru_uuid, ...body });
export const createBuilding = (body: Partial<Building> & { f_scene_uuid: string }) => post<Building>(`${L}/BuildingController/create`, body);
export const updateBuilding = (building_uuid: string, body: Partial<Building>) => post<Building>(`${L}/BuildingController/update`, { building_uuid, ...body });
export const deleteBuilding = (building_uuid: string) => post<{ deleted: number }>(`${L}/BuildingController/delete`, { building_uuid });
export const createUe = (body: Partial<Ue> & { f_scene_uuid: string }) => post<Ue>(`${U}/UeController/create`, body);
export const updateUe = (ue_uuid: string, body: Partial<Ue>) => post<Ue>(`${U}/UeController/update`, { ue_uuid, ...body });
export const deleteUe = (ue_uuid: string) => post<{ deleted: number }>(`${U}/UeController/delete`, { ue_uuid });
export const createUeWaypoint = (body: { f_ue_uuid: string; ord: number; t_sec: number; x: number; y: number; z: number }) => post<unknown>(`${U}/UeWaypointController/create`, body);
export interface UeWaypointRow { ue_waypoint_uuid: string; ord: number; t_sec: number; x: number; y: number; z: number; }
export const listUeWaypoints = (f_ue_uuid: string) => post<UeWaypointRow[]>(`${U}/UeWaypointReader/read`, { f_ue_uuid });
export const updateUeWaypoint = (ue_waypoint_uuid: string, body: { t_sec?: number; x?: number; y?: number; z?: number }) => post<unknown>(`${U}/UeWaypointController/update`, { ue_waypoint_uuid, ...body });
export const createUeTraffic = (body: { f_ue_uuid: string; pattern: string; rate_mbps: number; schedule: number[][] | null; bearer_id: number }) => post<UeTraffic>(`${U}/UeTrafficController/create`, body);
export const updateUeTraffic = (ue_traffic_uuid: string, body: Partial<UeTraffic>) => post<UeTraffic>(`${U}/UeTrafficController/update`, { ue_traffic_uuid, ...body });
export interface UeActiveWindowRow { ue_active_window_uuid: string; t0_sec: number; t1_sec: number; f_ue_uuid: string; }
export const listUeActiveWindows = (f_ue_uuid: string) => post<UeActiveWindowRow[]>(`${U}/UeActiveWindowReader/read`, { f_ue_uuid });
export const createUeActiveWindow = (body: { f_ue_uuid: string; t0_sec: number; t1_sec: number }) => post<UeActiveWindowRow>(`${U}/UeActiveWindowController/create`, body);
export const deleteUeActiveWindow = (ue_active_window_uuid: string) => post<{ deleted: number }>(`${U}/UeActiveWindowController/delete`, { ue_active_window_uuid });
