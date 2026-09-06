/** Zoom is the map. One volume, one transform, no second scene to load. */
export class Camera {
  x: number;
  y: number;
  /** Screen pixels per world cell. */
  scale: number;

  constructor(x: number, y: number, scale: number) {
    this.x = x; this.y = y; this.scale = scale;
  }

  toScreen(wx: number, wy: number, vw: number, vh: number): [number, number] {
    return [(wx - this.x) * this.scale + vw / 2, (wy - this.y) * this.scale + vh / 2];
  }

  toWorld(sx: number, sy: number, vw: number, vh: number): [number, number] {
    return [(sx - vw / 2) / this.scale + this.x, (sy - vh / 2) / this.scale + this.y];
  }

  zoomAt(sx: number, sy: number, factor: number, vw: number, vh: number, lo: number, hi: number): void {
    const [wx, wy] = this.toWorld(sx, sy, vw, vh);
    this.scale = Math.max(lo, Math.min(hi, this.scale * factor));
    const [nx, ny] = this.toWorld(sx, sy, vw, vh);
    this.x += wx - nx;
    this.y += wy - ny;
  }

  clampTo(w: number, h: number): void {
    this.x = Math.max(0, Math.min(w, this.x));
    this.y = Math.max(0, Math.min(h, this.y));
  }
}
