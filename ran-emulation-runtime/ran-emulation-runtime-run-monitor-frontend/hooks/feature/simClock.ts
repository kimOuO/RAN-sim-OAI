/** Interpolate only between observed simulation times; never invent future ticks. */
export interface SimAnchor { from: number; to: number; wall: number; duration: number }
export const readSimAnchor = (a: SimAnchor, wall: number) =>
  a.from + (a.to - a.from) * Math.max(0, Math.min(1, (wall - a.wall) / Math.max(1, a.duration)));
export function advanceSimAnchor(a: SimAnchor, sim: number, wall: number, duration: number): SimAnchor {
  const from = readSimAnchor(a, wall);
  return { from, to: Math.max(from, sim), wall, duration };
}
