'use client';

import styles from './PlaybackControls.module.css';

interface Props {
  frameIndex: number;
  frameCount: number;
  isPlaying: boolean;
  onPlayPause: () => void;
  onFrameChange: (idx: number) => void;
}

export function PlaybackControls({
  frameIndex,
  frameCount,
  isPlaying,
  onPlayPause,
  onFrameChange,
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
    </div>
  );
}
