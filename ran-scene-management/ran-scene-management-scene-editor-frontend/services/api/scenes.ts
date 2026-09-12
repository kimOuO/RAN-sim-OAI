import { REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { Scene, SceneTree } from '@/types/registry';

export const listScenes = () => post<Scene[]>(`${REGISTRY_API}/Scene_layout/SceneReader/read`, {});
export const getScene = (scene_uuid: string) => post<Scene>(`${REGISTRY_API}/Scene_layout/SceneReader/read`, { scene_uuid });
export const getSceneTree = (scene_uuid: string) => post<SceneTree>(`${REGISTRY_API}/Scene_layout/SceneReader/read_full_tree`, { scene_uuid });
export const createScene = (body: Partial<Scene>) => post<Scene>(`${REGISTRY_API}/Scene_layout/SceneController/create`, body);
export const updateScene = (scene_uuid: string, body: Partial<Scene>) => post<Scene>(`${REGISTRY_API}/Scene_layout/SceneController/update`, { scene_uuid, ...body });
export const deleteScene = (scene_uuid: string) => post<{ deleted: number }>(`${REGISTRY_API}/Scene_layout/SceneController/delete`, { scene_uuid });
