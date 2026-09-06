/**
 * A scalar field on a regular grid, sampled continuously.
 *
 * The bodies live in continuous space; the medium lives here. Everything the bodies can
 * perceive locally — heat, water, forage, wear — is one of these. Nothing in this file knows
 * what any particular field means.
 */
export class Field {
  readonly w: number;
  readonly h: number;
  data: Float32Array;
  private scratch: Float32Array;

  constructor(w: number, h: number, fill = 0) {
    this.w = w;
    this.h = h;
    this.data = new Float32Array(w * h).fill(fill);
    this.scratch = new Float32Array(w * h);
  }

  idx(x: number, y: number): number {
    const cx = x < 0 ? 0 : x >= this.w ? this.w - 1 : x;
    const cy = y < 0 ? 0 : y >= this.h ? this.h - 1 : y;
    return cy * this.w + cx;
  }

  at(x: number, y: number): number {
    return this.data[this.idx(x | 0, y | 0)];
  }

  set(x: number, y: number, v: number): void {
    this.data[this.idx(x | 0, y | 0)] = v;
  }

  add(x: number, y: number, v: number): void {
    this.data[this.idx(x | 0, y | 0)] += v;
  }

  /** Bilinear read at world coordinates. Bodies never see a cell boundary. */
  sample(x: number, y: number): number {
    const fx = Math.max(0, Math.min(this.w - 1.001, x));
    const fy = Math.max(0, Math.min(this.h - 1.001, y));
    const x0 = fx | 0, y0 = fy | 0;
    const tx = fx - x0, ty = fy - y0;
    const d = this.data, w = this.w;
    const i = y0 * w + x0;
    const a = d[i], b = d[i + 1], c = d[i + w], e = d[i + w + 1];
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + e * tx) * ty;
  }

  /** Spread a value over the four cells it falls between, so deposits don't alias to a grid. */
  splat(x: number, y: number, v: number): void {
    const fx = Math.max(0, Math.min(this.w - 1.001, x));
    const fy = Math.max(0, Math.min(this.h - 1.001, y));
    const x0 = fx | 0, y0 = fy | 0;
    const tx = fx - x0, ty = fy - y0;
    const d = this.data, w = this.w;
    const i = y0 * w + x0;
    d[i] += v * (1 - tx) * (1 - ty);
    d[i + 1] += v * tx * (1 - ty);
    d[i + w] += v * (1 - tx) * ty;
    d[i + w + 1] += v * tx * ty;
  }

  /** Central-difference gradient. This is what a body follows when it "goes uphill". */
  grad(x: number, y: number, out: { x: number; y: number }): void {
    out.x = (this.sample(x + 1, y) - this.sample(x - 1, y)) * 0.5;
    out.y = (this.sample(x, y + 1) - this.sample(x, y - 1)) * 0.5;
  }

  /**
   * Gradient at integer cell coordinates, straight out of the array.
   *
   * Same quantity as `grad`, without the four bilinear samples — the whole-grid loops call this
   * once per cell per tick, and the sampling version costs about four times as much.
   */
  gradAt(x: number, y: number, out: { x: number; y: number }): void {
    const { w, h, data } = this;
    const xl = x > 0 ? x - 1 : 0, xr = x < w - 1 ? x + 1 : w - 1;
    const yl = y > 0 ? y - 1 : 0, yr = y < h - 1 ? y + 1 : h - 1;
    const row = y * w;
    out.x = (data[row + xr] - data[row + xl]) * (xr - xl === 2 ? 0.5 : 1);
    out.y = (data[yr * w + x] - data[yl * w + x]) * (yr - yl === 2 ? 0.5 : 1);
  }

  /** Explicit diffusion. rate must stay under 0.25 or the field oscillates instead of spreading. */
  diffuse(rate: number): void {
    const { w, h, data } = this;
    const out = this.scratch;
    for (let y = 0; y < h; y++) {
      const yl = y > 0 ? y - 1 : 0;
      const yr = y < h - 1 ? y + 1 : h - 1;
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        const xl = x > 0 ? x - 1 : 0;
        const xr = x < w - 1 ? x + 1 : w - 1;
        const lap = data[y * w + xl] + data[y * w + xr] + data[yl * w + x] + data[yr * w + x] - 4 * data[i];
        out[i] = data[i] + rate * lap;
      }
    }
    this.scratch = data;
    this.data = out;
  }

  /**
   * Semi-Lagrangian advection by a velocity field. Wind carries heat; heat makes wind.
   *
   * Backtracing is stable but not conservative: where the velocity field converges it copies the
   * same source value into several cells and quietly manufactures the quantity. Left alone that
   * feeds straight back into the wind that caused it and the whole climate runs away. So the
   * total is restored afterwards — transport moves heat, it does not create it.
   */
  advect(vx: Field, vy: Field, dt: number): void {
    const { w, h } = this;
    const out = this.scratch;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        out[i] = this.sample(x - vx.data[i] * dt, y - vy.data[i] * dt);
      }
    }
    let before = 0, after = 0;
    for (let i = 0; i < out.length; i++) { before += this.data[i]; after += out[i]; }
    // Spread the discrepancy evenly rather than rescaling: these fields can go negative, and a
    // ratio correction flips sign the moment the total passes through zero.
    const fix = (before - after) / out.length;
    if (fix !== 0) for (let i = 0; i < out.length; i++) out[i] += fix;
    this.scratch = this.data;
    this.data = out;
  }

  /** Exponential relaxation toward a target field — insolation, regrowth, forgetting. */
  relaxToward(target: Field, rate: number): void {
    const d = this.data, t = target.data;
    for (let i = 0; i < d.length; i++) d[i] += (t[i] - d[i]) * rate;
  }

  scale(k: number): void {
    const d = this.data;
    for (let i = 0; i < d.length; i++) d[i] *= k;
  }

  clamp(lo: number, hi: number): void {
    const d = this.data;
    for (let i = 0; i < d.length; i++) d[i] = d[i] < lo ? lo : d[i] > hi ? hi : d[i];
  }

  sum(): number {
    let s = 0;
    for (let i = 0; i < this.data.length; i++) s += this.data[i];
    return s;
  }

  mean(): number { return this.sum() / this.data.length; }

  minmax(): [number, number] {
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < this.data.length; i++) {
      const v = this.data[i];
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    return [lo, hi];
  }

  copyFrom(other: Field): void { this.data.set(other.data); }
}
