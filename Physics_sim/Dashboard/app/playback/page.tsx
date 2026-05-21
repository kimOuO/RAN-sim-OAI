'use client';

import { usePlaybackPage } from '@/hooks/feature/usePlaybackPage';
import { PlaybackControls } from '@/components/PlaybackControls';
import { SignalTable } from '@/components/SignalTable';
import { ControlActionList } from '@/components/ControlActionList';
import { CellStatePanel } from '@/components/CellStatePanel';
import { TopDownMap } from '@/components/TopDownMap';

export default function PlaybackPage() {
  const {
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
    playbackSpeed,
    setPlaybackSpeed,
  } = usePlaybackPage();

  if (loading) return <div className="loading">Loading sessions...</div>;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <h1>Playback</h1>

      {error && <div className="error">{error}</div>}

      <div style={{ marginBottom: '24px' }}>
        <label>
          <div style={{ marginBottom: '8px', fontWeight: '500' }}>Select Session</div>
          <select
            value={selectedSession?.session_uuid || ''}
            onChange={(e) => {
              const session = sessions.find((s) => s.session_uuid === e.target.value);
              if (session) handleSessionChange(session);
            }}
            style={{ width: '100%', padding: '8px' }}
          >
            {sessions.map((session) => (
              <option key={session.session_uuid} value={session.session_uuid}>
                {session.mode === 'fast_cached' ? '⚡ ' : ''}
                {session.scene_id} — {new Date(session.timestamp).toLocaleString()}
                {session.mode === 'fast_cached' && session.time_compression_ratio
                  ? ` (${session.time_compression_ratio}x ${session.scenario_id})`
                  : ''}
              </option>
            ))}
          </select>
        </label>
        {selectedSession?.mode === 'fast_cached' && (
          <div style={{
            marginTop: 8, padding: '6px 10px', background: '#1e3a8a', color: '#dbeafe',
            borderRadius: 4, fontSize: 12, display: 'inline-block',
          }}>
            ⚡ Fast-replay session · scenario={selectedSession.scenario_id} · {selectedSession.time_compression_ratio}x compressed
          </div>
        )}
      </div>

      {selectedSession && (
        <>
          {sceneSnapshot && currentFrame && (
            <div style={{ marginBottom: '24px' }}>
              <TopDownMap
                width={900}
                height={700}
                buildings={sceneSnapshot.buildings || []}
                gnbs={sceneSnapshot.gnbs || []}
                ues={(currentFrame.ues ?? []).map((ue: any) => ({
                  name: ue.name || ue.ue_name,
                  position: ue.x !== undefined && ue.y !== undefined && ue.z !== undefined
                    ? [ue.x, ue.y, ue.z]
                    : [0, 0, 0],
                  color: [1.0, 0.6, 0.2],
                }))}
                selectedUEIndex={-1}
                trajectories={[]}
                onAddWaypoint={() => {}}
                onMoveWaypoint={() => {}}
                onRemoveWaypoint={() => {}}
                onMoveBuilding={() => {}}
                onMoveGnb={() => {}}
                onMoveUE={() => {}}
              />
            </div>
          )}

          <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '16px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                checked={enable3DReplay}
                onChange={(e) => setEnable3DReplay(e.target.checked)}
              />
              同步 3D Omniverse
            </label>
            {enable3DReplay && sceneSnapshot && selectedSession && (
              <button
                onClick={() => restoreScene(selectedSession.scene_id, sceneSnapshot)}
                disabled={sceneRestoring}
                style={{
                  padding: '6px 12px',
                  backgroundColor: sceneRestoring ? '#475569' : '#3b82f6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: sceneRestoring ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                }}
              >
                {sceneRestoring ? '重建中...' : '重建 3D 場景'}
              </button>
            )}
          </div>

          <PlaybackControls
            frameIndex={frameIndex}
            frameCount={selectedSession.frame_count}
            isPlaying={isPlaying}
            onPlayPause={handlePlayPause}
            onFrameChange={handleFrameChange}
            playbackSpeed={playbackSpeed}
            onPlaybackSpeedChange={setPlaybackSpeed}
          />

          {currentFrame && (
            <>
              <SignalTable
                data={currentFrame.ues ?? []}
                handovers={currentFrame.handovers ?? []}
              />
              <CellStatePanel cells={currentFrame.cell_states ?? []} />
              <ControlActionList actions={currentFrame.control_actions ?? []} />
            </>
          )}
        </>
      )}
    </div>
  );
}
