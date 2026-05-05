import { omniverseApiClient } from '@/services/api/omniverse';
import type { PlaybackSession, PlaybackFrame } from '@/types';

export const listSessions = async (): Promise<PlaybackSession[]> => {
  try {
    const response = await omniverseApiClient.post<{ success: boolean; data: { sessions: PlaybackSession[] } }>(
      '/api/v0.1/RAN/SimSession/PlaybackController/list',
      {}
    );
    console.log('[playback.listSessions] success, count:', response?.data?.data?.sessions?.length || 0);
    return response?.data?.data?.sessions || [];
  } catch (err: any) {
    console.error('[playback.listSessions] failed:', err.response?.data || err.message);
    return [];
  }
};

export const readSession = async (sessionUuid: string, frameIndex: number): Promise<PlaybackFrame> => {
  try {
    const response = await omniverseApiClient.post<{ success: boolean; data: PlaybackFrame }>(
      '/api/v0.1/RAN/SimSession/PlaybackController/read',
      { session_uuid: sessionUuid, frame_index: frameIndex }
    );
    const frame = response.data.data || { tick: frameIndex, ues: [] };
    console.log('[playback.readSession] frame loaded:', { tick: frame.tick, ues_count: frame.ues?.length || 0 });
    return frame;
  } catch (err: any) {
    console.error('[playback.readSession] failed:', err.response?.data || err.message);
    return { tick: frameIndex, ues: [] };
  }
};
