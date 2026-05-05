'use client';

import { useState, useMemo } from 'react';
import type { UsdAsset, Building, SceneConfig } from '@/types';
import {
  EDITABLE_FIELDS_BY_TYPE,
  getRecommendedBandwidth,
  isFrequencyValidForMaterials,
  isMaterialValidForFrequencies,
  formatRangesForMaterial,
} from '@/config/fieldDefinitions';
import styles from './ObjectForm.module.css';

interface ObjectFormProps {
  type: 'building' | 'gnb' | 'ue' | 'obstacle';
  assets: UsdAsset[];
  sceneConfig?: SceneConfig | null;
  onSubmit: (data: any) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

export function ObjectForm({
  type,
  assets,
  sceneConfig,
  onSubmit,
  onCancel,
  isLoading = false,
}: ObjectFormProps) {
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [formData, setFormData] = useState<Record<string, any>>({});

  // 过滤该类型的资产
  const filteredAssets = useMemo(
    () => assets.filter((a) => a.object_type === type),
    [assets, type]
  );

  // 获取选中的资产
  const selectedAsset = useMemo(
    () => filteredAssets.find((a) => a.asset_uuid === selectedAssetId),
    [filteredAssets, selectedAssetId]
  );

  // 可编辑字段定义
  const editableFields = EDITABLE_FIELDS_BY_TYPE[type] || [];

  // 場景目前已存在的 gNB 頻率與建物/障礙物材質,用來決定哪些下拉選項該被禁用。
  // 例:已有一個 gNB 用 0.617 GHz (n71),那 concrete/brick/metal 三種材質就不能再選,
  // 因為它們的 ITU 有效範圍下限都是 1 GHz,送到後端會被 SceneFrequencyMismatch 擋掉。
  const existingFrequencies = useMemo<number[]>(() => {
    const gnbs = sceneConfig?.gnbs || [];
    return gnbs.map(g => g.frequency_ghz).filter((f): f is number => typeof f === 'number');
  }, [sceneConfig?.gnbs]);

  const existingMaterials = useMemo<string[]>(() => {
    const buildings = sceneConfig?.buildings || [];
    const obstacles = (sceneConfig as any)?.obstacles || [];
    const out: string[] = [];
    for (const b of buildings) {
      const m = (b as any).material;
      if (typeof m === 'string' && m) out.push(m);
    }
    for (const o of obstacles) {
      const m = (o as any).material;
      if (typeof m === 'string' && m) out.push(m);
    }
    return Array.from(new Set(out));
  }, [sceneConfig?.buildings, sceneConfig]);

  // 选择资产时初始化表单
  const handleAssetSelect = (assetId: string) => {
    setSelectedAssetId(assetId);
    const asset = filteredAssets.find((a) => a.asset_uuid === assetId);
    if (asset) {
      const newData: Record<string, any> = { name: '' };

      // 从资产设置默认值
      if (asset.default_size) {
        newData.size = asset.default_size;
      }
      if (asset.default_color) {
        newData.color = asset.default_color;
      }
      if ((asset as any).default_rotation) {
        newData.rotation_xyz_deg = (asset as any).default_rotation;
      }

      setFormData(newData);
    }
  };

  const handleInputChange = (fieldName: string, value: any) => {
    setFormData((prev) => ({ ...prev, [fieldName]: value }));

    // GNB: 当改变频率时，自动设置推荐带宽
    if (type === 'gnb' && fieldName === 'frequency_ghz') {
      const recommendedBw = getRecommendedBandwidth(value);
      setFormData((prev) => ({ ...prev, bandwidth_mhz: recommendedBw }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // 验证必填字段
    for (const field of editableFields) {
      if (field.required && !formData[field.name]) {
        alert(`${field.label} is required`);
        return;
      }
    }

    // 必須選擇asset
    if (!selectedAsset) {
      alert('必須選擇一個 asset');
      return;
    }

    const submitData: any = {
      ...formData,
      preset_id: selectedAsset.preset_id,
    };

    // 从选中的asset中添加USD模型信息
    if (selectedAsset.usd_path) {
      submitData.usd_path = selectedAsset.usd_path;
    }
    if (selectedAsset.default_scale) {
      submitData.scale = selectedAsset.default_scale;
    }

    // 對於建築物，提醒用戶如果沒有USD
    if (type === 'building' && !selectedAsset.usd_path) {
      const confirm = window.confirm(
        `警告：選擇的 asset 沒有複雜 USD 配置。\n\n` +
        `建築物 "${formData.name}" 將被渲染為簡單立方體。\n\n` +
        `確認繼續嗎？`
      );
      if (!confirm) return;
    }

    await onSubmit(submitData);
  };

  // 类型标签
  const typeLabels: Record<string, string> = {
    building: '🏢 Building',
    gnb: '📡 gNB',
    ue: '📱 User Equipment',
    obstacle: '🚧 Obstacle',
  };

  return (
    <div className={styles.modalOverlay} onClick={onCancel}>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>Add {typeLabels[type]}</h2>
          <button className={styles.closeBtn} onClick={onCancel}>×</button>
        </div>

        {/* Step 1: 选择物体 */}
        {!selectedAssetId ? (
          <div className={styles.assetSelectionStep}>
            <p className={styles.stepLabel}>Step 1: Select {typeLabels[type]}</p>

            {filteredAssets.length === 0 ? (
              <p className={styles.noAssets}>
                No {type} presets available. Please add assets first.
              </p>
            ) : (
              <div className={styles.assetGrid}>
                {filteredAssets.map((asset) => (
                  <button
                    key={asset.asset_uuid}
                    className={styles.assetCard}
                    onClick={() => handleAssetSelect(asset.asset_uuid)}
                    type="button"
                    disabled={isLoading}
                  >
                    <div className={styles.assetLabel}>{asset.label}</div>
                    <div className={styles.assetDescription}>
                      {asset.description || '(no description)'}
                    </div>
                    <div className={styles.assetPath}>
                      {asset.usd_path}
                    </div>
                  </button>
                ))}
              </div>
            )}

            <button
              className={styles.btnCancel}
              onClick={onCancel}
              disabled={isLoading}
            >
              Cancel
            </button>
          </div>
        ) : (
          /* Step 2: 编辑字段 */
          <form onSubmit={handleSubmit} className={styles.form}>
            <p className={styles.stepLabel}>
              Step 2: Configure {selectedAsset?.label}
            </p>

            {editableFields.map((field) => (
              <div key={field.name} className={styles.formGroup}>
                <label htmlFor={field.name}>
                  {field.label}
                  {field.required && <span className={styles.required}>*</span>}
                </label>

                {field.type === 'text' && (
                  <input
                    id={field.name}
                    type="text"
                    value={formData[field.name] || ''}
                    onChange={(e) => handleInputChange(field.name, e.target.value)}
                    placeholder={field.label}
                  />
                )}

                {field.type === 'number' && (
                  <input
                    id={field.name}
                    type="number"
                    step="0.1"
                    min={field.min}
                    max={field.max}
                    value={formData[field.name] !== undefined ? formData[field.name] : ''}
                    onChange={(e) => handleInputChange(field.name, parseFloat(e.target.value))}
                  />
                )}

                {field.type === 'vector3' && (
                  <div className={styles.vector3Input}>
                    {['x', 'y', 'z'].map((axis, idx) => (
                      <input
                        key={axis}
                        type="number"
                        step="0.1"
                        placeholder={axis.toUpperCase()}
                        value={
                          Array.isArray(formData[field.name])
                            ? formData[field.name][idx] || ''
                            : ''
                        }
                        onChange={(e) => {
                          const arr = formData[field.name] || [0, 0, 0];
                          const newArr = [...arr];
                          newArr[idx] = parseFloat(e.target.value) || 0;
                          handleInputChange(field.name, newArr);
                        }}
                      />
                    ))}
                  </div>
                )}

                {field.type === 'color' && (
                  <div className={styles.colorInput}>
                    {['r', 'g', 'b'].map((channel, idx) => (
                      <div key={channel} className={styles.colorChannel}>
                        <label>{channel.toUpperCase()}</label>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.01"
                          value={
                            Array.isArray(formData[field.name])
                              ? formData[field.name][idx] || 0.5
                              : 0.5
                          }
                          onChange={(e) => {
                            const arr = formData[field.name] || [0.5, 0.5, 0.5];
                            const newArr = [...arr];
                            newArr[idx] = parseFloat(e.target.value);
                            handleInputChange(field.name, newArr);
                          }}
                        />
                        <span>
                          {Array.isArray(formData[field.name])
                            ? formData[field.name][idx]?.toFixed(2) || '0.50'
                            : '0.50'}
                        </span>
                      </div>
                    ))}
                    {Array.isArray(formData[field.name]) && (
                      <div
                        className={styles.colorPreview}
                        style={{
                          backgroundColor: `rgb(${Math.round(
                            (formData[field.name][0] || 0) * 255
                          )}, ${Math.round(
                            (formData[field.name][1] || 0) * 255
                          )}, ${Math.round((formData[field.name][2] || 0) * 255)})`,
                        }}
                      />
                    )}
                  </div>
                )}

                {field.type === 'select' && (() => {
                  // 對 material / frequency_ghz 做場景級交叉驗證。
                  // 不相容的選項顯示為 disabled,並在 label 後標出原因。
                  const isMaterialField = field.name === 'material';
                  const isFrequencyField = field.name === 'frequency_ghz';
                  const incompatibleOptions: { value: string | number; reason: string }[] = [];
                  return (
                    <>
                      <select
                        id={field.name}
                        value={formData[field.name] || ''}
                        onChange={(e) => handleInputChange(field.name,
                          field.options?.find(o => String(o.value) === e.target.value)?.value || e.target.value
                        )}
                      >
                        <option value="">-- Select --</option>
                        {field.options?.map((option) => {
                          let disabled = false;
                          let reason = '';
                          if (isMaterialField && existingFrequencies.length > 0) {
                            if (!isMaterialValidForFrequencies(String(option.value), existingFrequencies)) {
                              disabled = true;
                              reason = `不支援目前場景的頻率 (${formatRangesForMaterial(String(option.value))})`;
                            }
                          }
                          if (isFrequencyField && existingMaterials.length > 0) {
                            const f = Number(option.value);
                            if (!isFrequencyValidForMaterials(f, existingMaterials)) {
                              disabled = true;
                              reason = `${f} GHz 超出場景材質 (${existingMaterials.join(', ')}) 的 ITU 有效範圍`;
                            }
                          }
                          if (disabled) {
                            incompatibleOptions.push({ value: option.value, reason });
                          }
                          return (
                            <option
                              key={option.value}
                              value={option.value}
                              disabled={disabled}
                              title={disabled ? reason : undefined}
                            >
                              {option.label}
                              {option.isDefault ? ' (default)' : ''}
                              {disabled ? ' ⚠ 不相容' : ''}
                            </option>
                          );
                        })}
                      </select>
                      {incompatibleOptions.length > 0 && (
                        <div style={{ fontSize: '11px', color: '#b26a00', marginTop: '4px' }}>
                          {isMaterialField && existingFrequencies.length > 0 && (
                            <span>場景已有頻率: {existingFrequencies.map(f => `${f} GHz`).join(', ')}</span>
                          )}
                          {isFrequencyField && existingMaterials.length > 0 && (
                            <span>場景已有材質: {existingMaterials.join(', ')}</span>
                          )}
                        </div>
                      )}
                    </>
                  );
                })()}

                {field.type === 'checkbox' && (
                  <input
                    id={field.name}
                    type="checkbox"
                    checked={formData[field.name] || false}
                    onChange={(e) => handleInputChange(field.name, e.target.checked)}
                  />
                )}

                {field.type === 'cells' && (
                  <div className={styles.cellsInput}>
                    <label>Number of cells</label>
                    <select
                      value={(formData[field.name] || []).length || 1}
                      onChange={(e) => {
                        const n = parseInt(e.target.value, 10);
                        const cells = Array.from({ length: n }, (_, i) => {
                          const existing = (formData[field.name] || [])[i];
                          return existing || {
                            pci: i,
                            azimuth_deg: i > 0 ? (i * 360) / n : 0
                          };
                        });
                        handleInputChange(field.name, cells);
                      }}
                    >
                      <option value="1">1</option>
                      <option value="2">2</option>
                      <option value="3">3</option>
                      <option value="4">4</option>
                      <option value="6">6</option>
                    </select>
                    {(formData[field.name] || []).map((cell: any, i: number) => (
                      <div key={i} className={styles.cellRow}>
                        <label>Cell {i}</label>
                        <div className={styles.cellInputs}>
                          <input
                            type="number"
                            placeholder="PCI (0-1007)"
                            min={0}
                            max={1007}
                            value={cell.pci ?? ''}
                            onChange={(e) => {
                              const cells = formData[field.name];
                              cells[i].pci = parseInt(e.target.value, 10);
                              handleInputChange(field.name, [...cells]);
                            }}
                          />
                          <input
                            type="number"
                            placeholder="Azimuth (°, 0-359)"
                            min={0}
                            max={359}
                            step={1}
                            value={cell.azimuth_deg ?? ''}
                            onChange={(e) => {
                              const cells = formData[field.name];
                              cells[i].azimuth_deg = parseFloat(e.target.value);
                              handleInputChange(field.name, [...cells]);
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}

            <div className={styles.formActions}>
              <button
                type="button"
                className={styles.btnBack}
                onClick={() => setSelectedAssetId('')}
                disabled={isLoading}
              >
                ← Back
              </button>
              <button
                type="submit"
                className={styles.btnSubmit}
                disabled={isLoading || !selectedAssetId}
              >
                {isLoading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
