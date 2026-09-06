/** Deterministic RNG. The tank must replay identically from a seed, or "scar" means nothing. */
export class Rng {
  private s: number;

  constructor(seed: number) {
    this.s = (seed >>> 0) || 0x9e3779b9;
  }

  /** xorshift32 — cheap, adequate, and reproducible across machines. */
  next(): number {
    let x = this.s;
    x ^= x << 13; x >>>= 0;
    x ^= x >>> 17;
    x ^= x << 5; x >>>= 0;
    this.s = x;
    return x / 4294967296;
  }

  range(lo: number, hi: number): number {
    return lo + (hi - lo) * this.next();
  }

  /** Box-Muller, one half discarded. Used for copy error, so the tail matters. */
  normal(sigma = 1): number {
    const u = Math.max(1e-9, this.next());
    const v = this.next();
    return sigma * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  int(n: number): number {
    return Math.min(n - 1, Math.floor(this.next() * n));
  }

  get state(): number { return this.s; }
  set state(v: number) { this.s = (v >>> 0) || 0x9e3779b9; }
}
