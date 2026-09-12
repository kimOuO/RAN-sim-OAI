'use client';

import { useDrawPage } from '@/hooks/feature/useDrawPage';
import { TrajectoryCanvas } from '@/components/TrajectoryCanvas';

export default function DrawPage() {
  const {
    canvasRef,
    sceneConfig,
    selectedUEIndex,
    setSelectedUEIndex,
    trajectories,
    trafficProfiles,
    setTrafficProfile,
    loading,
    error,
    handleCanvasClick,
    handleCanvasMouseDown,
    handleCanvasMouseUp,
    handleClearTrajectory,
    handleSpeedChange,
    handleSubmit,
    handleBuild,
    handleClear,
  } = useDrawPage();

  if (loading) return <div className="loading">Loading...</div>;

  if (!trajectories.length) {
    return (
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px' }}>
        <h1>⚠️ No User Equipment Found</h1>
        <p>You need to create at least one UE on the Scene Initialization page before setting trajectories.</p>
        <button
          onClick={() => window.location.href = '/'}
          style={{
            padding: '12px 24px',
            background: '#0066cc',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          ← Back to Scene Initialization
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <h1>Trajectory Editor</h1>

      {error && <div className="error">{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '24px' }}>
        <div>
          <TrajectoryCanvas
            canvasRef={canvasRef}
            onClick={handleCanvasClick}
            onMouseDown={handleCanvasMouseDown}
            onMouseUp={handleCanvasMouseUp}
          />
          <div style={{ marginTop: '16px', display: 'flex', gap: '12px', flexDirection: 'column' }}>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn-secondary" onClick={() => handleBuild()} disabled={loading}>
                🏗️ Build Scene
              </button>
              <button className="btn-secondary" onClick={handleClear} disabled={loading}>
                🗑️ Clear Scene
              </button>
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn-danger" onClick={handleClearTrajectory}>
                Clear Trajectory
              </button>
              <button className="btn-primary" onClick={handleSubmit} style={{ flex: 1 }} disabled={loading}>
                {loading ? 'Processing...' : 'Next'}
              </button>
            </div>
          </div>
        </div>

        <div style={{ background: '#111827', padding: '16px', borderRadius: '8px', border: '1px solid #374151' }}>
          <h3 style={{ color: '#f3f4f6' }}>UEs</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {trajectories.map((ue, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedUEIndex(idx)}
                className="btn-secondary"
                style={{
                  opacity: idx === selectedUEIndex ? 1 : 0.6,
                  fontWeight: idx === selectedUEIndex ? 'bold' : 'normal',
                }}
              >
                {ue.name}
              </button>
            ))}
          </div>

          {trajectories[selectedUEIndex] && (() => {
            const ue = trajectories[selectedUEIndex];
            // Default = CBR 5 Mbps (沒設過的 UE, build 時會自動 inject 5Mbps).
            // 想停 traffic 就把 dropdown 切成 Idle.
            const profile = trafficProfiles[ue.name] || {
              pattern: 'cbr' as const, rate_mbps: 5, sdu_size: 1500, bearer_id: 1,
            };
            const onPatternChange = (pattern: 'idle' | 'cbr' | 'bursty') => {
              if (pattern === 'idle') {
                setTrafficProfile(ue.name, { pattern: 'idle' });
              } else if (pattern === 'cbr') {
                setTrafficProfile(ue.name, {
                  pattern: 'cbr',
                  rate_mbps: profile.rate_mbps ?? 5,
                  sdu_size: profile.sdu_size ?? 1500,
                  bearer_id: profile.bearer_id ?? 1,
                });
              }
            };
            const onRateChange = (rate: number) => {
              setTrafficProfile(ue.name, {
                ...profile,
                pattern: 'cbr',
                rate_mbps: rate,
                sdu_size: profile.sdu_size ?? 1500,
                bearer_id: profile.bearer_id ?? 1,
              });
            };
            return (
              <div style={{ marginTop: '20px' }}>
                {/* ── Traffic Profile 放最上面, 最顯眼 ────── */}
                <div style={{
                  background: '#0f172a',
                  border: '2px solid #2563eb',
                  borderRadius: '8px',
                  padding: '12px',
                  marginBottom: '16px',
                }}>
                  <div style={{
                    fontWeight: '600',
                    marginBottom: '8px',
                    color: '#60a5fa',
                    fontSize: '14px',
                  }}>
                    📡 Traffic Profile (DL)
                  </div>
                  <select
                    value={profile.pattern}
                    onChange={(e) => onPatternChange(e.target.value as any)}
                    style={{
                      width: '100%',
                      background: '#1f2937',
                      color: '#f3f4f6',
                      border: '1px solid #374151',
                      padding: '8px',
                      borderRadius: '4px',
                      fontSize: '14px',
                    }}
                  >
                    <option value="idle">Idle (no traffic)</option>
                    <option value="cbr">CBR (constant rate)</option>
                  </select>

                  {profile.pattern === 'cbr' && (
                    <label style={{ marginTop: '10px', display: 'block' }}>
                      <div style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>
                        Rate (Mbps DL)
                      </div>
                      <input
                        type="number"
                        step="0.5"
                        min="0.1"
                        max="100"
                        value={profile.rate_mbps ?? 5}
                        onChange={(e) => onRateChange(parseFloat(e.target.value))}
                        style={{
                          width: '100%',
                          background: '#1f2937',
                          color: '#f3f4f6',
                          border: '1px solid #374151',
                          padding: '6px 8px',
                          borderRadius: '4px',
                        }}
                      />
                    </label>
                  )}

                  <p style={{ fontSize: '11px', color: '#94a3b8', marginTop: '8px', lineHeight: '1.4' }}>
                    Default = CBR 5 Mbps. Build 後生效, UE container 自動注 SDU 進 DU,
                    KPM throughput / volume / delay 會跳起來.
                  </p>
                </div>

                {/* ── Speed + Waypoints ────────────────────── */}
                <label>
                  <div style={{ marginBottom: '6px', fontWeight: '500' }}>Speed (m/s)</div>
                  <input
                    type="number"
                    value={ue.speed_mps}
                    onChange={(e) => handleSpeedChange(parseFloat(e.target.value))}
                    style={{ width: '100%' }}
                  />
                </label>
                <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '6px' }}>
                  Waypoints: {ue.waypoints?.length || 0}
                </p>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
