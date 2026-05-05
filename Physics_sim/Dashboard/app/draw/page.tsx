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

        <div style={{ background: 'white', padding: '16px', borderRadius: '8px' }}>
          <h3>UEs</h3>
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

          {trajectories[selectedUEIndex] && (
            <div style={{ marginTop: '24px' }}>
              <label>
                <div style={{ marginBottom: '8px', fontWeight: '500' }}>Speed (m/s)</div>
                <input
                  type="number"
                  value={trajectories[selectedUEIndex].speed_mps}
                  onChange={(e) => handleSpeedChange(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
              </label>
              <p style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
                Waypoints: {trajectories[selectedUEIndex].waypoints?.length || 0}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
