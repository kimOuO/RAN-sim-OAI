'use client';

import styles from './PlaybackControls.module.css';

const PLAYBACK_SPEED_OPTIONS = [1, 2, 4, 10];

interface Props {
  frameIndex: number;
  frameCount: number;
  isPlaying: boolean;
  onPlayPause: () => void;
  onFrameChange: (idx: number) => void;
  playbackSpeed?: number;
  onPlaybackSpeedChange?: (speed: number) => void;
}

export function PlaybackControls({
  frameIndex,
  frameCount,
  isPlaying,
  onPlayPause,
  onFrameChange,
  playbackSpeed = 1,
  onPlaybackSpeedChange,
}: Props) {
  return (
    <div className={styles.controls}>
      <button className="btn-primary" onClick={onPlayPause}>
        {isPlaying ? 'Pause' : 'Play'}
      </button>

      <div className={styles.scrubber}>
        <input
          type="range"
          min="0"
          max={Math.max(0, frameCount - 1)}
          value={frameIndex}
          onChange={(e) => onFrameChange(parseInt(e.target.value))}
          className={styles.slider}
        />
      </div>

      <span className={styles.counter}>
        Frame {frameIndex + 1} / {frameCount}
      </span>

      {onPlaybackSpeedChange && (
        <label
          title="Playback frame advance rate (frontend only)"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
        >
          <span style={{ color: '#94a3b8' }}>Speed</span>
          <select
            value={playbackSpeed}
            onChange={(e) => onPlaybackSpeedChange(parseInt(e.target.value, 10))}
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              border: '1px solid #334155',
              background: '#0f172a',
              color: '#e5e7eb',
              fontSize: '12px',
              cursor: 'pointer',
            }}
          >
            {PLAYBACK_SPEED_OPTIONS.map((s) => (
              <option key={s} value={s}>{s}x</option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
