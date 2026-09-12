'use client';

import React from 'react';
import styles from './TrajectoryCanvas.module.css';

interface Props {
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  onClick: (e: React.MouseEvent<HTMLCanvasElement>) => void;
  onMouseDown?: (e: React.MouseEvent<HTMLCanvasElement>) => void;
  onMouseUp?: (e: React.MouseEvent<HTMLCanvasElement>) => void;
}

export function TrajectoryCanvas({ canvasRef, onClick, onMouseDown, onMouseUp }: Props) {
  return (
    <div className={styles.canvasContainer}>
      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        onClick={onClick}
        onMouseDown={onMouseDown}
        onMouseUp={onMouseUp}
        className={styles.canvas}
      />
    </div>
  );
}
