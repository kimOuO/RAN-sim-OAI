'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSceneEditor } from '@/hooks/feature/useSceneEditor';
import { useDrawPage } from '@/hooks/feature/useDrawPage';
import { useSimPage } from '@/hooks/feature/useSimPage';
import { TopDownMap } from '@/components/TopDownMap';
import { ObjectForm } from '@/components/ObjectForm';
import { SignalTable } from '@/components/SignalTable';
import { SignalChart } from '@/components/SignalChart';
import { MimoSettingsPanel } from '@/components/MimoSettingsPanel';
import * as omniverseApi from '@/services/api/omniverse';
import { computeCoverage, type CoverageResponse } from '@/services/api/coverage';
import type { SceneAntennaConfig } from '@/types';

export default function SceneEditor() {
  const router = useRouter();
  const editor = useSceneEditor();
  const draw = useDrawPage();
  const { simRunning, signalData, chartData, handleStartSim, handleStopSim } = useSimPage({
    onUpdateUEPositions: draw.updateUEPositions,
  });

  const [showForm, setShowForm] = useState(false);
  const [formType, setFormType] = useState<'building' | 'gnb' | 'ue' | 'obstacle'>('building');
  const [selectedObject, setSelectedObject] = useState<{
    type: 'building' | 'gnb' | 'ue';
    name: string;
  } | null>(null);
  const [retryLoading, setRetryLoading] = useState(false);
  const [retryMessage, setRetryMessage] = useState<string>('');
  const [editValues, setEditValues] = useState<Record<string, any>>({});
  const [coverageMode, setCoverageMode] = useState(false);
  const [coverageData, setCoverageData] = useState<CoverageResponse | null>(null);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [selectedCoverageGnb, setSelectedCoverageGnb] = useState<string | null>(null);
  const [coverageMetric, setCoverageMetric] = useState<'rsrp' | 'sinr'>('rsrp');
  const [mimoConfig, setMimoConfig] = useState<SceneAntennaConfig>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = window.localStorage.getItem('ran-sim:mimo');
        if (saved) return JSON.parse(saved);
      } catch {}
    }
    return {
      gnb_array_rows: 1, gnb_array_cols: 1, gnb_polarization: 'V',
      ue_array_rows: 1, ue_array_cols: 1, ue_polarization: 'V',
    };
  });
  const updateMimoConfig = (next: SceneAntennaConfig) => {
    setMimoConfig(next);
    try { window.localStorage.setItem('ran-sim:mimo', JSON.stringify(next)); } catch {}
  };

  const handleOpenForm = (type: 'building' | 'gnb' | 'ue' | 'obstacle') => {
    setFormType(type);
    setShowForm(true);
  };

  const handleFormSubmit = async (data: any) => {
    try {
      const { position, ...cleanData } = data;
      const submitData = {
        position: position ?? [0, 0, 0],
        ...cleanData,
      };

      switch (formType) {
        case 'building':
          await editor.createBuilding(submitData);
          break;
        case 'ue':
          await editor.createUE(submitData);
          break;
        case 'gnb':
          await editor.createGNB(submitData);
          break;
        case 'obstacle':
          await editor.createObstacle(submitData);
          break;
      }
      setShowForm(false);
      await draw.refreshScene();
    } catch (err) {
      console.error(`Failed to create ${formType}`, err);
    }
  };

  const clearUETrajectory = async () => {
    setRetryLoading(true);
    setRetryMessage('正在清空...');
    try {
      // 清空選中 UE 的軌跡
      draw.handleClearTrajectory();
      setRetryMessage('✅ 已清空 UE 軌跡');
    } catch (err) {
      setRetryMessage(`❌ 清空失敗: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRetryLoading(false);
    }
  };

  const handleComputeCoverage = async () => {
    setCoverageLoading(true);
    try {
      const result = await computeCoverage({
        scene_id: 'default',
        grid: {
          x_range: [-500, 500],
          x_step: 11,
          z_range: [-500, 500],
          z_step: 11,
          sample_height_m: 1.5,
        },
        include_sinr: true,
        max_depth: 2,
        null_threshold_dbm: -120,
      });
      setCoverageData(result);
      setCoverageMode(true);
      setSelectedCoverageGnb(result.gnbs[0]?.gnb_name ?? null);
    } catch (err) {
      alert(`Coverage 計算失敗: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setCoverageLoading(false);
    }
  };

  const handleDeleteObject = async () => {
    if (!selectedObject) return;
    const confirmed = confirm(`確定刪除 ${selectedObject.name}?`);
    if (!confirmed) return;

    try {
      switch (selectedObject.type) {
        case 'building':
          await editor.deleteBuilding(selectedObject.name);
          break;
        case 'gnb':
          await editor.deleteGNB(selectedObject.name);
          break;
        case 'ue':
          await editor.deleteUE(selectedObject.name);
          break;
      }
      setSelectedObject(null);
      await draw.refreshScene();
    } catch (err) {
      console.error(`Failed to delete ${selectedObject.type}`, err);
      alert(`刪除失敗: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  if (draw.loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <p>Loading scene...</p>
      </div>
    );
  }

  const selectedGnbCoverage = coverageData?.gnbs.find(g => g.gnb_name === selectedCoverageGnb);
  const coverageOverlay = selectedGnbCoverage && coverageData && coverageMode
    ? {
        grid: coverageData.grid,
        data: coverageMetric === 'rsrp'
          ? selectedGnbCoverage.rsrp_dbm
          : (selectedGnbCoverage.sinr_db ?? selectedGnbCoverage.rsrp_dbm),
      }
    : undefined;

  return (
    <div style={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: selectedObject ? '280px 1fr 300px' : '280px 1fr', gap: 0 }}>
      {/* 左側侧边栏 */}
      <div style={{
        background: '#f5f5f5',
        borderRight: '1px solid #ddd',
        padding: '24px',
        overflowY: 'auto',
        maxHeight: '100vh'
      }}>
        <h2 style={{ fontSize: '18px', fontWeight: '600', margin: '0 0 20px 0' }}>
          Scene Editor
        </h2>

        {/* Create 按鈕組 */}
        <div style={{ marginBottom: '32px' }}>
          <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#666', marginBottom: '12px' }}>
            ADD OBJECTS
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <button
              onClick={() => handleOpenForm('building')}
              disabled={editor.isCreating}
              style={{
                padding: '10px 12px',
                background: '#0066cc',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: editor.isCreating ? 0.6 : 1,
              }}
            >
              + Building
            </button>
            <button
              onClick={() => handleOpenForm('gnb')}
              disabled={editor.isCreating}
              style={{
                padding: '10px 12px',
                background: '#ff6b35',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: editor.isCreating ? 0.6 : 1,
              }}
            >
              + gNB
            </button>
            <button
              onClick={() => handleOpenForm('ue')}
              disabled={editor.isCreating}
              style={{
                padding: '10px 12px',
                background: '#00a86b',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: editor.isCreating ? 0.6 : 1,
              }}
            >
              + User Equipment
            </button>
            <button
              onClick={() => handleOpenForm('obstacle')}
              disabled={editor.isCreating}
              style={{
                padding: '10px 12px',
                background: '#888',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: editor.isCreating ? 0.6 : 1,
              }}
            >
              + Obstacle
            </button>
          </div>
        </div>

        {/* MIMO 全域設定 */}
        <div style={{ marginBottom: '32px' }}>
          <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#666', marginBottom: '12px' }}>
            MIMO ANTENNA
          </h3>
          <MimoSettingsPanel config={mimoConfig} onChange={updateMimoConfig} />
        </div>

        {/* 物件列表 */}
        <div style={{ marginBottom: '32px' }}>
          <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#666', marginBottom: '12px' }}>
            OBJECTS ({(draw.sceneConfig?.buildings?.length || 0) + (draw.sceneConfig?.gnbs?.length || 0) + (draw.sceneConfig?.ues?.length || 0)})
          </h3>

          {/* Buildings */}
          {draw.sceneConfig?.buildings && draw.sceneConfig.buildings.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '11px', color: '#999', fontWeight: '600', marginBottom: '8px' }}>
                🏢 BUILDINGS ({draw.sceneConfig.buildings.length})
              </div>
              {draw.sceneConfig.buildings.map((b) => (
                <div
                  key={b.name}
                  style={{
                    padding: '10px',
                    background: 'white',
                    border: '1px solid #e0e0e0',
                    borderRadius: '6px',
                    marginBottom: '6px',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>{b.name}</div>
                  <div style={{ color: '#666', fontSize: '11px', marginBottom: '6px' }}>
                    Pos: [{b.position[0]?.toFixed(1)}, {b.position[2]?.toFixed(1)}]
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        await editor.deleteBuilding(b.name);
                        await draw.refreshScene();
                      } catch (err) {
                        console.error('Failed to delete building', err);
                      }
                    }}
                    disabled={editor.isDeleting}
                    style={{
                      fontSize: '11px',
                      padding: '4px 8px',
                      background: '#ffebee',
                      color: '#c62828',
                      border: 'none',
                      borderRadius: '3px',
                      cursor: 'pointer',
                    }}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* gNBs */}
          {draw.sceneConfig?.gnbs && draw.sceneConfig.gnbs.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '11px', color: '#999', fontWeight: '600', marginBottom: '8px' }}>
                📡 gNBs ({draw.sceneConfig.gnbs.length})
              </div>
              {draw.sceneConfig.gnbs.map((g) => (
                <div
                  key={g.name}
                  style={{
                    padding: '10px',
                    background: 'white',
                    border: '1px solid #e0e0e0',
                    borderRadius: '6px',
                    marginBottom: '6px',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>{g.name}</div>
                  <div style={{ color: '#666', fontSize: '11px', marginBottom: '6px' }}>
                    Pos: [{g.position[0]?.toFixed(1)}, {g.position[2]?.toFixed(1)}]
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        await editor.deleteGNB(g.name);
                        await draw.refreshScene();
                      } catch (err) {
                        console.error('Failed to delete gNB', err);
                      }
                    }}
                    disabled={editor.isDeleting}
                    style={{
                      fontSize: '11px',
                      padding: '4px 8px',
                      background: '#ffebee',
                      color: '#c62828',
                      border: 'none',
                      borderRadius: '3px',
                      cursor: 'pointer',
                    }}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* UEs */}
          {draw.trajectories && draw.trajectories.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '11px', color: '#999', fontWeight: '600', marginBottom: '8px' }}>
                📱 USER EQUIPMENT ({draw.trajectories.length})
              </div>
              {draw.trajectories.map((u, idx) => (
                <div
                  key={u.name}
                  onClick={() => draw.setSelectedUEIndex(idx)}
                  style={{
                    padding: '10px',
                    background: draw.selectedUEIndex === idx ? '#f0fdf4' : 'white',
                    border: draw.selectedUEIndex === idx ? '2px solid #00a86b' : '1px solid #e0e0e0',
                    borderRadius: '6px',
                    marginBottom: '6px',
                    fontSize: '12px',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                    {u.name}
                    {draw.selectedUEIndex === idx && ' ✓'}
                  </div>
                  <div style={{ color: '#666', fontSize: '11px', marginBottom: '4px' }}>
                    Speed: {u.speed_mps} m/s
                  </div>
                  <div style={{ color: '#666', fontSize: '11px', marginBottom: '6px' }}>
                    Waypoints: {u.waypoints?.length || 0}
                  </div>
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      try {
                        await editor.deleteUE(u.name);
                        await draw.refreshScene();
                      } catch (err) {
                        console.error('Failed to delete UE', err);
                      }
                    }}
                    disabled={editor.isDeleting}
                    style={{
                      fontSize: '11px',
                      padding: '4px 8px',
                      background: '#ffebee',
                      color: '#c62828',
                      border: 'none',
                      borderRadius: '3px',
                      cursor: 'pointer',
                    }}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}

          {!editor.buildings.data?.length && !editor.gnbs.data?.length && !draw.trajectories?.length && (
            <p style={{ fontSize: '12px', color: '#999', margin: 0 }}>
              No objects created yet.
            </p>
          )}
        </div>
      </div>

      {/* 右側：Canvas + 控制按鈕 */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {/* Canvas 區域 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '24px', background: 'white' }}>
          <h1 style={{ margin: '0 0 16px 0', fontSize: '24px', fontWeight: '600' }}>
            Scene Layout
          </h1>

          {draw.error && (
            <div style={{
              background: '#ffebee',
              color: '#c62828',
              padding: '12px',
              borderRadius: '6px',
              marginBottom: '16px',
              fontSize: '13px'
            }}>
              {draw.error}
            </div>
          )}

          {/* Coverage Mode Toggle */}
          {coverageData && (
            <div style={{
              display: 'flex', gap: '10px', alignItems: 'center',
              marginBottom: '12px', padding: '8px 12px',
              background: '#f0f0f0', borderRadius: '6px', border: '1px solid #ddd',
              flexWrap: 'wrap',
            }}>
              <label style={{ fontSize: '12px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input
                  type="checkbox"
                  checked={coverageMode}
                  onChange={(e) => setCoverageMode(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                Coverage Mode
              </label>
              {coverageMode && (
                <>
                  <select
                    value={selectedCoverageGnb ?? ''}
                    onChange={e => setSelectedCoverageGnb(e.target.value)}
                    style={{ padding: '4px 8px', background: '#fff', border: '1px solid #ccc', borderRadius: '4px', fontSize: '11px' }}
                  >
                    {coverageData.gnbs.map(g => (
                      <option key={g.gnb_name} value={g.gnb_name}>{g.gnb_name}</option>
                    ))}
                  </select>
                  {['rsrp', 'sinr'].map(m => (
                    <button
                      key={m}
                      onClick={() => setCoverageMetric(m as 'rsrp' | 'sinr')}
                      style={{
                        padding: '4px 10px', fontSize: '11px', border: 'none', borderRadius: '4px', cursor: 'pointer',
                        background: coverageMetric === m ? '#0066cc' : '#ddd',
                        color: coverageMetric === m ? '#fff' : '#333',
                      }}
                    >
                      {m.toUpperCase()}
                    </button>
                  ))}
                  <button
                    onClick={() => { setCoverageData(null); setCoverageMode(false); setSelectedCoverageGnb(null) }}
                    style={{ marginLeft: 'auto', padding: '4px 8px', background: '#fff', border: '1px solid #ccc', color: '#333', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' }}
                  >
                    ✕ Clear
                  </button>
                </>
              )}
            </div>
          )}

          <TopDownMap
            buildings={draw.sceneConfig?.buildings ?? []}
            gnbs={draw.sceneConfig?.gnbs ?? []}
            ues={draw.sceneConfig?.ues ?? []}
            selectedUEIndex={draw.selectedUEIndex}
            trajectories={draw.trajectories}
            onAddWaypoint={draw.handleAddWaypoint}
            onMoveWaypoint={draw.handleMoveWaypoint}
            onRemoveWaypoint={draw.handleRemoveWaypoint}
            onMoveBuilding={draw.handleMoveBuilding}
            onMoveGnb={draw.handleMoveGnb}
            onMoveUE={draw.handleMoveUE}
            onSelectObject={setSelectedObject}
            onSelectUEIndex={draw.setSelectedUEIndex}
            coverageOverlay={coverageOverlay}
          />

          {/* Live Signal Metrics */}
          <div style={{ marginTop: '24px', borderTop: '1px solid #ddd', paddingTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: '600' }}>Live Signal Metrics</h3>
              <span style={{ fontSize: '12px', color: simRunning ? '#4caf50' : '#999' }}>
                {simRunning ? '🟢 Running' : '⚫ Stopped'}
              </span>
            </div>
            <div style={{ marginBottom: '16px' }}>
              <SignalChart data={chartData} height={200} />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <SignalTable data={signalData} />
            </div>
          </div>

          {/* UE 速度調整 */}
          {draw.trajectories[draw.selectedUEIndex] && (
            <div style={{ marginTop: '16px', padding: '12px', background: '#f9f9f9', borderRadius: '6px' }}>
              <label>
                <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '6px' }}>
                  Speed for {draw.trajectories[draw.selectedUEIndex].name} (m/s)
                </div>
                <input
                  type="number"
                  value={draw.trajectories[draw.selectedUEIndex].speed_mps ?? 1.0}
                  onChange={(e) => draw.handleSpeedChange(parseFloat(e.target.value) || 1.0)}
                  step={0.1}
                  style={{
                    width: '100%',
                    padding: '8px',
                    fontSize: '13px',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                  }}
                />
              </label>
            </div>
          )}
        </div>

        {/* 底部控制按鈕 */}
        <div style={{
          background: '#f5f5f5',
          borderTop: '1px solid #ddd',
          padding: '16px 24px',
          display: 'flex',
          gap: '12px',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <button
            onClick={clearUETrajectory}
            disabled={retryLoading || !draw.trajectories[draw.selectedUEIndex]?.waypoints?.length}
            style={{
              padding: '8px 16px',
              background: draw.trajectories[draw.selectedUEIndex]?.waypoints?.length ? '#ff6b6b' : '#999',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: draw.trajectories[draw.selectedUEIndex]?.waypoints?.length ? 'pointer' : 'not-allowed',
              fontSize: '12px',
              fontWeight: '500',
            }}
          >
            {retryLoading ? '⏳ 清空中...' : '🗑️ 清空 UE 路徑'}
          </button>
          {retryMessage && (
            <div style={{
              fontSize: '11px',
              color: retryMessage.startsWith('✅') ? '#4caf50' : '#f44336',
              whiteSpace: 'pre-wrap',
              maxWidth: '300px',
            }}>
              {retryMessage}
            </div>
          )}
          <div style={{ display: 'flex', gap: '12px', marginLeft: 'auto' }}>
            <button
              onClick={draw.handleClear}
              disabled={draw.loading}
              style={{
                padding: '10px 20px',
                background: '#fff',
                border: '1px solid #ddd',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: draw.loading ? 0.6 : 1,
              }}
            >
              🗑️ Clear Scene
            </button>
            <button
              onClick={() => draw.handleBuild(mimoConfig)}
              disabled={draw.loading}
              style={{
                padding: '10px 20px',
                background: '#ff9500',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: draw.loading ? 0.6 : 1,
              }}
            >
              🏗️ Build Scene
            </button>
            {!simRunning ? (
              <button
                onClick={handleStartSim}
                disabled={draw.loading}
                style={{
                  padding: '10px 20px',
                  background: '#22c55e',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: '500',
                  opacity: draw.loading ? 0.6 : 1,
                }}
              >
                ▶️ Start Sim
              </button>
            ) : (
              <button
                onClick={handleStopSim}
                disabled={draw.loading}
                style={{
                  padding: '10px 20px',
                  background: '#ef4444',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: '500',
                  opacity: draw.loading ? 0.6 : 1,
                }}
              >
                ⏹️ Stop Sim
              </button>
            )}
            <button
              onClick={handleComputeCoverage}
              disabled={coverageLoading}
              style={{
                padding: '10px 20px',
                background: '#8b5cf6',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: coverageLoading ? 0.6 : 1,
              }}
            >
              {coverageLoading ? '⏳ Computing...' : '🗺️ Coverage'}
            </button>
            <span style={{ marginLeft: '12px', lineHeight: '40px', fontWeight: 'bold', fontSize: '13px' }}>
              {simRunning ? '🟢 Running' : '⚫ Stopped'}
            </span>
          </div>
        </div>
      </div>

      {/* Detail Panel */}
      {selectedObject && (
        <div style={{
          background: '#1a1a2e',
          color: '#eee',
          padding: '20px',
          overflowY: 'auto',
          borderLeft: '1px solid #333',
          maxHeight: '100vh',
          fontSize: '13px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ margin: 0, color: '#fff', fontSize: '15px', fontWeight: '600' }}>
              {selectedObject.type === 'building' ? '🏢' :
               selectedObject.type === 'gnb' ? '📡' : '📱'} {selectedObject.name}
            </h3>
            <button
              onClick={() => setSelectedObject(null)}
              style={{
                background: 'none',
                border: 'none',
                color: '#aaa',
                cursor: 'pointer',
                fontSize: '18px',
              }}
            >
              ✕
            </button>
          </div>

          {/* Building Details */}
          {selectedObject.type === 'building' && (() => {
            const building = draw.sceneConfig?.buildings.find(b => b.name === selectedObject.name);
            if (!building) return null;
            const key = `${selectedObject.name}-pos`;
            const pos = editValues[key] || building.position;
            return (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>POSITION</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '20px' }}>X:</span>
                      <input type="number" value={pos[0]?.toFixed(1)} onChange={(e) => setEditValues({ ...editValues, [key]: [parseFloat(e.target.value), pos[1], pos[2]] })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      <span>m</span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '20px' }}>Y:</span>
                      <input type="number" value={pos[1]?.toFixed(1)} onChange={(e) => setEditValues({ ...editValues, [key]: [pos[0], parseFloat(e.target.value), pos[2]] })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      <span>m</span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '20px' }}>Z:</span>
                      <input type="number" value={pos[2]?.toFixed(1)} onChange={(e) => setEditValues({ ...editValues, [key]: [pos[0], pos[1], parseFloat(e.target.value)] })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      <span>m</span>
                    </div>
                  </div>
                </div>
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>SIZE</div>
                  <div style={{ fontSize: '12px' }}>
                    Width: {building.size[0]?.toFixed(1)} m<br />
                    Height: {building.size[1]?.toFixed(1)} m<br />
                    Depth: {building.size[2]?.toFixed(1)} m
                  </div>
                </div>
                {building.color && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>COLOR</div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <div style={{
                        width: '20px',
                        height: '20px',
                        background: `rgb(${Math.round(building.color[0] * 255)},${Math.round(building.color[1] * 255)},${Math.round(building.color[2] * 255)})`,
                        borderRadius: '3px',
                        border: '1px solid #555',
                      }} />
                      <span style={{ fontSize: '12px' }}>
                        RGB({(building.color[0] * 255).toFixed(0)}, {(building.color[1] * 255).toFixed(0)}, {(building.color[2] * 255).toFixed(0)})
                      </span>
                    </div>
                  </div>
                )}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>SIZE</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '20px' }}>W:</span>
                      <input type="number" value={editValues[`${selectedObject.name}-sizeW`] ?? building.size[0]} onChange={(e) => setEditValues({ ...editValues, [`${selectedObject.name}-sizeW`]: parseFloat(e.target.value) })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      <span>m</span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '20px' }}>H:</span>
                      <input type="number" value={editValues[`${selectedObject.name}-sizeH`] ?? building.size[1]} onChange={(e) => setEditValues({ ...editValues, [`${selectedObject.name}-sizeH`]: parseFloat(e.target.value) })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      <span>m</span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '20px' }}>D:</span>
                      <input type="number" value={editValues[`${selectedObject.name}-sizeD`] ?? building.size[2]} onChange={(e) => setEditValues({ ...editValues, [`${selectedObject.name}-sizeD`]: parseFloat(e.target.value) })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      <span>m</span>
                    </div>
                  </div>
                </div>
                {building.color && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>COLOR (RGB)</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
                      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        <span style={{ width: '20px' }}>R:</span>
                        <input type="number" min="0" max="255" value={Math.round((editValues[`${selectedObject.name}-colorR`] ?? building.color[0]) * 255)} onChange={(e) => setEditValues({ ...editValues, [`${selectedObject.name}-colorR`]: parseFloat(e.target.value) / 255 })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      </div>
                      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        <span style={{ width: '20px' }}>G:</span>
                        <input type="number" min="0" max="255" value={Math.round((editValues[`${selectedObject.name}-colorG`] ?? building.color[1]) * 255)} onChange={(e) => setEditValues({ ...editValues, [`${selectedObject.name}-colorG`]: parseFloat(e.target.value) / 255 })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      </div>
                      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        <span style={{ width: '20px' }}>B:</span>
                        <input type="number" min="0" max="255" value={Math.round((editValues[`${selectedObject.name}-colorB`] ?? building.color[2]) * 255)} onChange={(e) => setEditValues({ ...editValues, [`${selectedObject.name}-colorB`]: parseFloat(e.target.value) / 255 })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      </div>
                    </div>
                  </div>
                )}
                {building.usd_path && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>USD ASSET</div>
                    <div style={{ fontSize: '12px', color: '#bbb', wordBreak: 'break-all' }}>
                      {building.usd_path}
                    </div>
                  </div>
                )}
                {building.preset_type && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>PRESET</div>
                    <div style={{ fontSize: '12px' }}>
                      {building.preset_type}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {/* gNB Details */}
          {selectedObject.type === 'gnb' && (() => {
            const gnb = draw.sceneConfig?.gnbs.find(g => g.name === selectedObject.name);
            if (!gnb) return null;
            const posKey = `${selectedObject.name}-pos`;
            const freqKey = `${selectedObject.name}-freq`;
            const bwKey = `${selectedObject.name}-bw`;
            const powerKey = `${selectedObject.name}-power`;
            const pos = editValues[posKey] || gnb.position;
            const freq = editValues[freqKey] ?? gnb.freq_mhz;
            const bw = editValues[bwKey] ?? (gnb.bw_hz / 1e6);
            const power = editValues[powerKey] ?? gnb.power_dbm;
            return (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>POSITION</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '20px' }}>X:</span>
                      <input type="number" value={pos[0]?.toFixed(1)} onChange={(e) => setEditValues({ ...editValues, [posKey]: [parseFloat(e.target.value), pos[1], pos[2]] })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      <span>m</span>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <span style={{ width: '20px' }}>Z:</span>
                      <input type="number" value={pos[2]?.toFixed(1)} onChange={(e) => setEditValues({ ...editValues, [posKey]: [pos[0], pos[1], parseFloat(e.target.value)] })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }} />
                      <span>m</span>
                    </div>
                  </div>
                </div>
                {gnb.freq_mhz !== undefined && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>FREQUENCY</div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center', fontSize: '12px' }}>
                      <input type="number" value={freq?.toFixed(0)} onChange={(e) => setEditValues({ ...editValues, [freqKey]: parseFloat(e.target.value) })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px' }} />
                      <span>MHz</span>
                    </div>
                  </div>
                )}
                {gnb.bw_hz !== undefined && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>BANDWIDTH</div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center', fontSize: '12px' }}>
                      <input type="number" value={bw?.toFixed(1)} onChange={(e) => setEditValues({ ...editValues, [bwKey]: parseFloat(e.target.value) })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px' }} />
                      <span>MHz</span>
                    </div>
                  </div>
                )}
                {gnb.power_dbm !== undefined && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>POWER</div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center', fontSize: '12px' }}>
                      <input type="number" value={power?.toFixed(1)} onChange={(e) => setEditValues({ ...editValues, [powerKey]: parseFloat(e.target.value) })} style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px' }} />
                      <span>dBm</span>
                    </div>
                  </div>
                )}
                {gnb.active !== undefined && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>STATUS</div>
                    <div style={{ fontSize: '12px' }}>
                      {gnb.active ? '✅ Active' : '❌ Inactive'}
                    </div>
                  </div>
                )}
                {gnb.color && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>COLOR</div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <div style={{
                        width: '20px',
                        height: '20px',
                        background: `rgb(${Math.round(gnb.color[0] * 255)},${Math.round(gnb.color[1] * 255)},${Math.round(gnb.color[2] * 255)})`,
                        borderRadius: '3px',
                        border: '1px solid #555',
                      }} />
                      <span style={{ fontSize: '12px' }}>
                        RGB({(gnb.color[0] * 255).toFixed(0)}, {(gnb.color[1] * 255).toFixed(0)}, {(gnb.color[2] * 255).toFixed(0)})
                      </span>
                    </div>
                  </div>
                )}
                {gnb.cells && gnb.cells.length > 0 && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>CELLS</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <select
                        value={(editValues[`${selectedObject.name}-cells`] || gnb.cells).length}
                        onChange={(e) => {
                          const n = parseInt(e.target.value, 10);
                          const existing = editValues[`${selectedObject.name}-cells`] || gnb.cells || [];
                          const cells = Array.from({ length: n }, (_, i) => existing[i] || { pci: i, azimuth_deg: i > 0 ? (i * 360) / n : 0 });
                          setEditValues({ ...editValues, [`${selectedObject.name}-cells`]: cells });
                        }}
                        style={{ padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px', fontSize: '12px' }}
                      >
                        <option value="1">1 cell</option>
                        <option value="2">2 cells</option>
                        <option value="3">3 cells</option>
                        <option value="4">4 cells</option>
                        <option value="6">6 cells</option>
                      </select>
                      {(editValues[`${selectedObject.name}-cells`] || gnb.cells || []).map((cell: any, i: number) => (
                        <div key={i} style={{ display: 'flex', gap: '4px', alignItems: 'center', fontSize: '12px' }}>
                          <span style={{ width: '50px', color: '#999' }}>Cell {i}</span>
                          <input
                            type="number"
                            placeholder="PCI"
                            min={0}
                            max={1007}
                            value={cell.pci ?? ''}
                            onChange={(e) => {
                              const cells = editValues[`${selectedObject.name}-cells`] || [...gnb.cells];
                              cells[i].pci = parseInt(e.target.value, 10);
                              setEditValues({ ...editValues, [`${selectedObject.name}-cells`]: cells });
                            }}
                            style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px' }}
                          />
                          <input
                            type="number"
                            placeholder="Azimuth °"
                            min={0}
                            max={359}
                            step={1}
                            value={cell.azimuth_deg ?? ''}
                            onChange={(e) => {
                              const cells = editValues[`${selectedObject.name}-cells`] || [...gnb.cells];
                              cells[i].azimuth_deg = parseFloat(e.target.value);
                              setEditValues({ ...editValues, [`${selectedObject.name}-cells`]: cells });
                            }}
                            style={{ flex: 1, padding: '4px', background: '#2a2a3e', color: '#eee', border: '1px solid #444', borderRadius: '3px' }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {/* UE Details */}
          {selectedObject.type === 'ue' && (() => {
            const ue = draw.trajectories.find(u => u.name === selectedObject.name);
            if (!ue) return null;
            return (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>POSITION</div>
                  <div style={{ fontSize: '12px' }}>
                    X: {ue.position[0]?.toFixed(1)} m<br />
                    Y: {ue.position[1]?.toFixed(1)} m<br />
                    Z: {ue.position[2]?.toFixed(1)} m
                  </div>
                </div>
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>SPEED</div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <input
                      type="number"
                      value={ue.speed_mps || 1.0}
                      onChange={(e) => {
                        const newSpeed = parseFloat(e.target.value) || 1.0;
                        omniverseApi.updateUe(ue.name, { speed_mps: newSpeed }).catch(err => {
                          console.error('Failed to update UE speed:', err);
                        });
                      }}
                      step={0.1}
                      min={0.1}
                      style={{
                        flex: 1,
                        padding: '6px',
                        fontSize: '12px',
                        background: '#2a2a3e',
                        color: '#eee',
                        border: '1px solid #444',
                        borderRadius: '4px',
                      }}
                    />
                    <span style={{ fontSize: '12px', color: '#bbb' }}>m/s</span>
                  </div>
                </div>
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>WAYPOINTS</div>
                  <div style={{ fontSize: '12px' }}>
                    {ue.waypoints?.length || 0} points
                  </div>
                </div>
                {ue.waypoints && ue.waypoints.length > 0 && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ color: '#999', fontSize: '11px', fontWeight: '600', marginBottom: '4px' }}>WAYPOINT LIST</div>
                    <div style={{ fontSize: '11px', maxHeight: '150px', overflowY: 'auto' }}>
                      {ue.waypoints.map((w, idx) => (
                        <div key={idx} style={{ marginBottom: '4px', color: '#bbb' }}>
                          {idx + 1}. ({w[0]?.toFixed(1)}, {w[1]?.toFixed(1)}, {w[2]?.toFixed(1)})
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Detail Panel Action Buttons */}
          <div style={{ marginTop: '32px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <button
              onClick={async () => {
                if (!selectedObject) return;
                try {
                  if (selectedObject.type === 'building') {
                    const posKey = `${selectedObject.name}-pos`;
                    const sizeWKey = `${selectedObject.name}-sizeW`;
                    const sizeHKey = `${selectedObject.name}-sizeH`;
                    const sizeDKey = `${selectedObject.name}-sizeD`;
                    const colorRKey = `${selectedObject.name}-colorR`;
                    const colorGKey = `${selectedObject.name}-colorG`;
                    const colorBKey = `${selectedObject.name}-colorB`;
                    const updateData: any = {};
                    if (editValues[posKey]) updateData.position = editValues[posKey];
                    if (editValues[sizeWKey] !== undefined || editValues[sizeHKey] !== undefined || editValues[sizeDKey] !== undefined) {
                      const building = draw.sceneConfig?.buildings.find(b => b.name === selectedObject.name);
                      updateData.size = [
                        editValues[sizeWKey] ?? building?.size[0] ?? 10,
                        editValues[sizeHKey] ?? building?.size[1] ?? 10,
                        editValues[sizeDKey] ?? building?.size[2] ?? 10,
                      ];
                    }
                    if (editValues[colorRKey] !== undefined || editValues[colorGKey] !== undefined || editValues[colorBKey] !== undefined) {
                      const building = draw.sceneConfig?.buildings.find(b => b.name === selectedObject.name);
                      updateData.color = [
                        editValues[colorRKey] ?? building?.color[0] ?? 0.5,
                        editValues[colorGKey] ?? building?.color[1] ?? 0.5,
                        editValues[colorBKey] ?? building?.color[2] ?? 0.5,
                      ];
                    }
                    if (Object.keys(updateData).length > 0) {
                      await omniverseApi.updateBuilding(selectedObject.name, updateData);
                    }
                  } else if (selectedObject.type === 'gnb') {
                    const posKey = `${selectedObject.name}-pos`;
                    const freqKey = `${selectedObject.name}-freq`;
                    const bwKey = `${selectedObject.name}-bw`;
                    const powerKey = `${selectedObject.name}-power`;
                    const cellsKey = `${selectedObject.name}-cells`;
                    const updateData: any = {};
                    if (editValues[posKey]) updateData.position = editValues[posKey];
                    if (editValues[freqKey] !== undefined) updateData.frequency_ghz = editValues[freqKey] / 1000;
                    if (editValues[bwKey] !== undefined) updateData.bandwidth_mhz = editValues[bwKey];
                    if (editValues[powerKey] !== undefined) updateData.power_dbm = editValues[powerKey];
                    if (editValues[cellsKey]) updateData.cells = editValues[cellsKey];
                    if (Object.keys(updateData).length > 0) {
                      await omniverseApi.updateGnb(selectedObject.name, updateData);
                    }
                  } else if (selectedObject.type === 'ue') {
                    const posKey = `${selectedObject.name}-pos`;
                    const pos = editValues[posKey];
                    if (pos) {
                      await omniverseApi.updateUe(selectedObject.name, { position: pos });
                    }
                  }
                  setEditValues({});
                  alert('✅ 已更新');
                  await draw.refreshScene();
                } catch (err) {
                  alert(`❌ 更新失敗: ${err instanceof Error ? err.message : String(err)}`);
                }
              }}
              style={{
                padding: '10px',
                background: '#4caf50',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: '500',
              }}
            >
              💾 Update {selectedObject?.type === 'building' ? 'Building' : selectedObject?.type === 'gnb' ? 'gNB' : 'UE'}
            </button>
            <button
              onClick={handleDeleteObject}
              style={{
                padding: '10px',
                background: '#f44336',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: '500',
              }}
            >
              🗑️ Delete {selectedObject?.type === 'building' ? 'Building' : selectedObject?.type === 'gnb' ? 'gNB' : 'UE'}
            </button>
          </div>
        </div>
      )}

      {/* ObjectForm Modal */}
      {showForm && (
        <ObjectForm
          type={formType}
          assets={editor.assets.data || []}
          sceneConfig={draw.sceneConfig}
          onSubmit={handleFormSubmit}
          onCancel={() => setShowForm(false)}
          isLoading={editor.isCreating}
        />
      )}
    </div>
  );
}
