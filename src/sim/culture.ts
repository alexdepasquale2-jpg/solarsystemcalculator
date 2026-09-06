import { Rng } from "./rng";

/**
 * Habits, and how badly they travel.
 *
 * A body carries six numbers. It did not reason its way to them; it copied them off whoever was
 * nearby and doing well, and it copied them slightly wrong. That is the whole mechanism. Groups
 * that stop meeting stop averaging, and their numbers drift apart — which is what a dialect is,
 * before anyone writes one down.
 */
export interface Traits {
  /** Which heat this body reads as "comfortable". */
  warmth: number;
  /** Pull toward others carrying similar habits. */
  gregarious: number;
  /** How much a worn path is trusted over open ground. */
  roadLove: number;
  /** Reluctance to cross a border — a marked edge, or just deep unfamiliar wear. */
  borderFear: number;
  /** Willingness to walk off the known map. Keeps the tank from crystallising. */
  venture: number;
  /** The arbitrary part: a shape/noise with no payoff, copied for no reason but that others do. */
  shape: number;
}

export const TRAIT_KEYS: (keyof Traits)[] = [
  "warmth", "gregarious", "roadLove", "borderFear", "venture", "shape",
];

/** Per-trait copy error. `shape` drifts fastest because nothing corrects it. */
const COPY_SIGMA: Record<keyof Traits, number> = {
  warmth: 0.018,
  gregarious: 0.030,
  roadLove: 0.035,
  borderFear: 0.030,
  venture: 0.025,
  shape: 0.055,
};

const BOUNDS: Record<keyof Traits, [number, number]> = {
  warmth: [0.05, 1.6],
  gregarious: [0, 1.6],
  roadLove: [0, 2.0],
  borderFear: [0, 2.0],
  venture: [0.02, 1.2],
  shape: [0, 1],
};

export function clampTraits(t: Traits): Traits {
  for (const k of TRAIT_KEYS) {
    const [lo, hi] = BOUNDS[k];
    const v = t[k];
    t[k] = v < lo ? lo : v > hi ? hi : v;
  }
  return t;
}

export function randomTraits(rng: Rng): Traits {
  return clampTraits({
    warmth: rng.range(0.45, 0.8),
    gregarious: rng.range(0.3, 0.9),
    roadLove: rng.range(0.2, 0.8),
    borderFear: rng.range(0.1, 0.6),
    venture: rng.range(0.15, 0.55),
    shape: rng.next(),
  });
}

/**
 * Move `self` a fraction of the way toward `other`, badly.
 * `weight` is how much this particular teacher is worth listening to.
 */
export function imitate(self: Traits, other: Traits, weight: number, rng: Rng): void {
  for (const k of TRAIT_KEYS) {
    const pull = (other[k] - self[k]) * weight;
    self[k] += pull + rng.normal(COPY_SIGMA[k] * weight);
  }
  clampTraits(self);
}

/** Inheritance is imitation with a bigger error bar and no teacher to check against. */
export function inherit(parent: Traits, rng: Rng): Traits {
  const t: Traits = { ...parent };
  for (const k of TRAIT_KEYS) t[k] += rng.normal(COPY_SIGMA[k] * 2.2);
  return clampTraits(t);
}

/** How foreign two bodies sound to each other. Drives who is worth copying and who is not. */
export function dialectDistance(a: Traits, b: Traits): number {
  let s = 0;
  for (const k of TRAIT_KEYS) {
    const d = a[k] - b[k];
    s += d * d * (k === "shape" ? 3 : 1);
  }
  return Math.sqrt(s);
}

/**
 * A mark on the ground: the player's, or a copy of a copy of the player's.
 * Marks are not instructions. They are just something visible that bodies imitate when near.
 */
export interface Mark {
  x: number;
  y: number;
  shape: number;
  strength: number;
  /** 0 = the player's own hand; higher = generations of misreading. */
  generation: number;
  bornTick: number;
}

export function decayMarks(marks: Mark[], rate: number): Mark[] {
  const out: Mark[] = [];
  for (const m of marks) {
    m.strength *= rate;
    if (m.strength > 0.02) out.push(m);
  }
  return out;
}
