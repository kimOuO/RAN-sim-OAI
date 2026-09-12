import { REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { Cell, Du, Gnb, Ru } from '@/types/registry';

const R = `${REGISTRY_API}/Radio_access_element`;
export const createGnb = (body: Partial<Gnb> & { f_scene_uuid: string }) => post<Gnb>(`${R}/GnbController/create`, body);
export const updateGnb = (gnb_uuid: string, body: Partial<Gnb>) => post<Gnb>(`${R}/GnbController/update`, { gnb_uuid, ...body });
export const deleteGnb = (gnb_uuid: string) => post<{ deleted: number }>(`${R}/GnbController/delete`, { gnb_uuid });
export const createDu = (body: Partial<Du> & { f_gnb_uuid: string }) => post<Du>(`${R}/DuController/create`, body);
export const createCell = (body: Partial<Cell> & { f_du_uuid: string }) => post<Cell>(`${R}/CellController/create`, body);
export const updateCell = (cell_uuid: string, body: Partial<Cell>) => post<Cell>(`${R}/CellController/update`, { cell_uuid, ...body });
export const deleteCell = (cell_uuid: string) => post<{ deleted: number }>(`${R}/CellController/delete`, { cell_uuid });
export const createRu = (body: Partial<Ru> & { f_cell_uuid: string }) => post<Ru>(`${R}/RuController/create`, body);
export const updateRu = (ru_uuid: string, body: Partial<Ru>) => post<Ru>(`${R}/RuController/update`, { ru_uuid, ...body });
