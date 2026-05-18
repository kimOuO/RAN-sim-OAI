'use client';

import { useState, useCallback, useEffect } from 'react';
import { listSessions, readSession } from '@/services/api/playback';
import { batchMoveUEs, clearScene, ingestScene } from '@/services/api/omniverse';
import type { PlaybackSession, PlaybackFrame } from '@/types';

export function usePlaybackPage() {
  const [sessions, setSessions] = useState<PlaybackSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<PlaybackSession | null>(null);
  const [currentFrame, setCurrentFrame] = useState<PlaybackFrame | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sceneSnapshot, setSceneSnapshot] = useState<any>(null);
  const [enable3DReplay, setEnable3DReplay] = useState(true);
  const [sceneRestoring, setSceneRestoring] = useState(false);

  useEffect(() => {
    const loadSessions = async () => {
      try {
        setLoading(true);
        const data = await listSessions();
        setSessions(data);
        // 2026-05-17: 先挑有 frames 的;沒有就挑最近一筆「有 scene_snapshot」的,
        // 讓「重建 3D 場景」按鈕至少能用,即使還沒累積 frame_count > 0。
        const hasSnapshot = (s: PlaybackSession) =>
          !!s.scene_snapshot &&
          ((s.scene_snapshot.buildings?.length ?? 0) > 0 ||
           (s.scene_snapshot.gnbs?.length ?? 0) > 0);
        const auto = data.find((s) => s.frame_count > 0) || data.find(hasSnapshot);
        if (auto) {
          setSelectedSession(auto);
          if (auto.frame_count > 0) {
            loadFrame(auto.session_uuid, 0);
          }
          if (hasSnapshot(auto)) {
            setSceneSnapshot(auto.scene_snapshot);
          }
        }
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sessions');
      } finally {
        setLoading(false);
      }
    };
    loadSessions();
  }, []);

  const loadFrame = useCallback(async (sessionUuid: string, idx: number) => {
    try {
      const frame = await readSession(sessionUuid, idx);
      // 將扁平 {x, y, z} 轉換為 position array
      const normalizedFrame = {
        ...frame,
        ues: (frame.ues ?? []).map((ue: any) => ({
          ...ue,
          position: ue.position ?? (
            ue.x !== undefined ? ([ue.x, ue.y ?? 0, ue.z ?? 0] as [number, number, number]) : undefined
          ),
        })),
      };
      setCurrentFrame(normalizedFrame);
      setFrameIndex(idx);
      const snap = normalizedFrame.scene_snapshot;
      if (snap && ((snap.buildings?.length ?? 0) > 0 || (snap.gnbs?.length ?? 0) > 0)) {
        setSceneSnapshot(snap);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load frame');
    }
  }, []);

  useEffect(() => {
    if (!selectedSession || !isPlaying) return;

    const timer = setInterval(() => {
      setFrameIndex((prev) => {
        const next = prev + 1;
        if (next >= (selectedSession?.frame_count || 0)) {
          setIsPlaying(false);
          return prev;
        }
        loadFrame(selectedSession.session_uuid, next);
        return next;
      });
    }, 500);

    return () => clearInterval(timer);
  }, [isPlaying, selectedSession, loadFrame]);

  // 3D Replay: push UE positions + signals when frame changes
  useEffect(() => {
    if (!enable3DReplay || !currentFrame || !currentFrame.ues) return;

    const uesWithData = currentFrame.ues
      .filter((ue: any) => ue.x !== undefined)
      .map((ue: any) => ({
        name: ue.name ?? ue.ue_name ?? '',
        x: ue.x,
        y: ue.y ?? 0,
        z: ue.z,
        rsrp_dbm: ue.rsrp_dbm,
        sinr_db: ue.sinr_db,
        serving_cell: ue.serving_cell,
        serving_gnb: ue.serving_gnb,
        serving_pci: ue.serving_pci,
        serving_cell_id: ue.serving_cell_id,
      }));

    if (uesWithData.length > 0) {
      batchMoveUEs(uesWithData).catch((e) => console.warn('3D replay push failed:', e));
    }
  }, [enable3DReplay, currentFrame]);

  const restoreScene = useCallback(async (sceneId: string, snapshot: any) => {
    setSceneRestoring(true);
    try {
      await clearScene();
      await ingestScene(sceneId, snapshot);
    } catch (e) {
      console.warn('3D scene restore failed:', e);
    } finally {
      setSceneRestoring(false);
    }
  }, []);

  const handleSessionChange = useCallback((session: PlaybackSession) => {
    setSelectedSession(session);
    setFrameIndex(0);
    setIsPlaying(false);
    setCurrentFrame(null);
    if (session.scene_snapshot &&
        ((session.scene_snapshot.buildings?.length ?? 0) > 0 ||
         (session.scene_snapshot.gnbs?.length ?? 0) > 0)) {
      setSceneSnapshot(session.scene_snapshot);
    } else {
      setSceneSnapshot(null);
    }
    if (session.frame_count > 0) {
      loadFrame(session.session_uuid, 0);
    }
  }, [loadFrame]);

  const handlePlayPause = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  const handleFrameChange = useCallback(
    (idx: number) => {
      if (selectedSession) {
        setFrameIndex(idx);
        setIsPlaying(false);
        loadFrame(selectedSession.session_uuid, idx);
      }
    },
    [selectedSession, loadFrame]
  );

  return {
    sessions,
    selectedSession,
    currentFrame,
    frameIndex,
    isPlaying,
    loading,
    error,
    sceneSnapshot,
    enable3DReplay,
    setEnable3DReplay,
    sceneRestoring,
    restoreScene,
    handleSessionChange,
    handlePlayPause,
    handleFrameChange,
  };
}
