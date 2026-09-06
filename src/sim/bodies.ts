import { Field } from "./field";
import { Rng } from "./rng";
import { Traits, Mark, imitate, inherit, randomTraits, dialectDistance } from "./culture";

/**
 * The small bodies.
 *
 * A body reads six things within a couple of body-lengths of itself — forage, heat, wear, water,
 * borders, neighbours — and adds up the pulls. It has no destination, no plan, no knowledge that
 * a herd exists. Herds exist anyway, because a body that likes company steers toward company, and
 * company is where the last body steered.
 */
export interface Body {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  energy: number;
  age: number;
  traits: Traits;
  /** Ticks since this body last learned anything. Used only for readouts. */
  lastCopy: number;
}

export interface BodyParams {
  speed: number;
  drag: number;
  metabolism: number;
  /** Energy per unit of forage swallowed. The whole budget hangs off this number. */
  foodValue: number;
  breedEnergy: number;
  breedCost: number;
  starveAt: number;
  maxAge: number;
  perception: number;
  wearDeposit: number;
  crowding: number;
  copyRate: number;
  markCopyRate: number;
  markEmitChance: number;
}

export const defaultBodies: BodyParams = {
  speed: 0.085,
  drag: 0.80,
  metabolism: 0.0042,
  foodValue: 0.42,
  breedEnergy: 1.30,
  breedCost: 0.78,
  starveAt: 0.0,
  maxAge: 5200,
  perception: 5.0,
  wearDeposit: 0.030,
  crowding: 0.55,
  copyRate: 0.035,
  markCopyRate: 0.10,
  markEmitChance: 0.0004,
};

/** Uniform-grid neighbour lookup. Keeps the body loop near-linear as the herd grows. */
export class SpatialHash {
  private cell: number;
  private cols: number;
  private rows: number;
  private buckets: number[][];

  constructor(w: number, h: number, cell: number) {
    this.cell = cell;
    this.cols = Math.ceil(w / cell);
    this.rows = Math.ceil(h / cell);
    this.buckets = Array.from({ length: this.cols * this.rows }, () => []);
  }

  rebuild(bodies: Body[]): void {
    for (const b of this.buckets) b.length = 0;
    for (let i = 0; i < bodies.length; i++) {
      const b = bodies[i];
      const cx = Math.min(this.cols - 1, Math.max(0, (b.x / this.cell) | 0));
      const cy = Math.min(this.rows - 1, Math.max(0, (b.y / this.cell) | 0));
      this.buckets[cy * this.cols + cx].push(i);
    }
  }

  /** Indices in the 3x3 block of cells around (x, y). */
  near(x: number, y: number, out: number[]): number[] {
    out.length = 0;
    const cx = Math.min(this.cols - 1, Math.max(0, (x / this.cell) | 0));
    const cy = Math.min(this.rows - 1, Math.max(0, (y / this.cell) | 0));
    for (let j = Math.max(0, cy - 1); j <= Math.min(this.rows - 1, cy + 1); j++) {
      for (let i = Math.max(0, cx - 1); i <= Math.min(this.cols - 1, cx + 1); i++) {
        const bucket = this.buckets[j * this.cols + i];
        for (let k = 0; k < bucket.length; k++) out.push(bucket[k]);
      }
    }
    return out;
  }
}

export interface BodyContext {
  elev: Field;
  heat: Field;
  water: Field;
  wear: Field;
  border: Field;
  /** "Sound carries here": local multiplier on how readily habits pass between bodies. */
  carry: Field;
  biomass: Field;
  eat(x: number, y: number, dt: number): number;
  marks: Mark[];
  tick: number;
}

export class Population {
  bodies: Body[] = [];
  private hash: SpatialHash;
  private nextId = 1;
  private scratch: number[] = [];
  private g = { x: 0, y: 0 };
  /** Marks emitted by bodies this tick; the world folds them back in. */
  emitted: Mark[] = [];

  constructor(private w: number, private h: number, cell = 6) {
    this.hash = new SpatialHash(w, h, cell);
  }

  seed(n: number, rng: Rng, elev: Field): void {
    for (let i = 0; i < n; i++) {
      // Start low, where water and forage already are. No formation, just a plausible puddle.
      let bx = 0, by = 0, best = Infinity;
      for (let k = 0; k < 6; k++) {
        const x = rng.range(2, this.w - 3);
        const y = rng.range(2, this.h - 3);
        const e = elev.sample(x, y);
        if (e < best) { best = e; bx = x; by = y; }
      }
      this.bodies.push({
        id: this.nextId++,
        x: bx, y: by, vx: 0, vy: 0,
        energy: rng.range(0.5, 0.9),
        age: rng.int(400),
        traits: randomTraits(rng),
        lastCopy: 0,
      });
    }
  }

  step(ctx: BodyContext, p: BodyParams, rng: Rng, dt: number, cap: number): void {
    this.emitted.length = 0;
    this.hash.rebuild(this.bodies);
    const born: Body[] = [];

    for (let i = 0; i < this.bodies.length; i++) {
      const b = this.bodies[i];
      const t = b.traits;
      let ax = 0, ay = 0;

      // --- pull 1: food, straight up the gradient it can smell
      ctx.biomass.grad(b.x, b.y, this.g);
      const hunger = Math.max(0, 1.25 - b.energy);
      ax += this.g.x * 44 * hunger;
      ay += this.g.y * 44 * hunger;

      // --- pull 2: comfort. Not "go warm" — go toward this body's own idea of warm.
      ctx.heat.grad(b.x, b.y, this.g);
      const err = ctx.heat.sample(b.x, b.y) - t.warmth;
      ax -= this.g.x * err * 30;
      ay -= this.g.y * err * 30;

      // --- pull 3: the road. Wear attracts, which deepens wear, which attracts.
      ctx.wear.grad(b.x, b.y, this.g);
      ax += this.g.x * 14 * t.roadLove;
      ay += this.g.y * 14 * t.roadLove;

      // --- pull 4: water is drinkable at the edge and lethal in the middle
      const depth = ctx.water.sample(b.x, b.y);
      if (depth > 0.12) {
        ctx.water.grad(b.x, b.y, this.g);
        ax -= this.g.x * 40;
        ay -= this.g.y * 40;
        b.energy -= 0.004 * dt;
      } else if (depth < 0.02) {
        ctx.water.grad(b.x, b.y, this.g);
        ax += this.g.x * 4;
        ay += this.g.y * 4;
      }

      // --- pull 5: borders. A thing you were taught to not walk over.
      ctx.border.grad(b.x, b.y, this.g);
      const bstr = ctx.border.sample(b.x, b.y);
      ax -= this.g.x * 55 * t.borderFear * (0.2 + bstr);
      ay -= this.g.y * 55 * t.borderFear * (0.2 + bstr);

      // --- pull 6: each other, but only the ones who sound familiar
      const near = this.hash.near(b.x, b.y, this.scratch);
      let kinX = 0, kinY = 0, kinW = 0, crowdX = 0, crowdY = 0;
      let teacher = -1, teacherScore = -Infinity;
      for (let n = 0; n < near.length; n++) {
        const j = near[n];
        if (j === i) continue;
        const o = this.bodies[j];
        const dx = o.x - b.x, dy = o.y - b.y;
        const d2 = dx * dx + dy * dy;
        if (d2 > p.perception * p.perception || d2 < 1e-6) continue;
        const d = Math.sqrt(d2);
        const foreign = dialectDistance(t, o.traits);
        const familiarity = 1 / (1 + foreign * 2.5);
        kinX += (dx / d) * familiarity; kinY += (dy / d) * familiarity; kinW += familiarity;
        if (d < 1.6) { crowdX -= dx / d2; crowdY -= dy / d2; }
        // Prestige: fed, alive a while, and not too foreign to parse.
        const score = o.energy * 1.4 + Math.min(o.age, 1500) / 1500 - foreign * 1.1;
        if (score > teacherScore) { teacherScore = score; teacher = j; }
      }
      if (kinW > 0) {
        ax += (kinX / kinW) * 9 * t.gregarious;
        ay += (kinY / kinW) * 9 * t.gregarious;
      }
      ax += crowdX * p.crowding * 9;
      ay += crowdY * p.crowding * 9;

      // --- the noise floor. Without it the tank freezes into whatever it found first. A hungry
      // body wanders wider, which is the only reason a stripped patch ever gets left behind.
      const restless = t.venture * (1 + hunger * 1.6);
      ax += rng.normal(1) * 9 * restless;
      ay += rng.normal(1) * 9 * restless;

      // --- terrain cost: uphill is expensive
      ctx.elev.grad(b.x, b.y, this.g);
      ax -= this.g.x * 26;
      ay -= this.g.y * 26;

      b.vx = (b.vx + ax * p.speed * dt) * p.drag;
      b.vy = (b.vy + ay * p.speed * dt) * p.drag;
      const sp = Math.hypot(b.vx, b.vy);
      const maxSp = 0.9;
      if (sp > maxSp) { b.vx *= maxSp / sp; b.vy *= maxSp / sp; }

      b.x = Math.max(0.5, Math.min(this.w - 1.5, b.x + b.vx * dt));
      b.y = Math.max(0.5, Math.min(this.h - 1.5, b.y + b.vy * dt));

      // Walking wears the ground. This is the record grade: the body will die, the path won't.
      ctx.wear.splat(b.x, b.y, p.wearDeposit * Math.min(sp, maxSp) * dt);

      // --- eat, burn, learn
      b.energy += ctx.eat(b.x, b.y, dt) * p.foodValue;
      b.energy -= (p.metabolism + sp * 0.0032) * dt;
      b.age += dt;

      const carry = 1 + ctx.carry.sample(b.x, b.y) * 3;
      if (teacher >= 0 && rng.next() < p.copyRate * carry * dt) {
        const o = this.bodies[teacher];
        // Weight by how much better off the teacher looks. Copying down happens too, weakly.
        const w = Math.max(0.05, Math.min(0.5, (o.energy - b.energy) * 0.5 + 0.12));
        imitate(t, o.traits, w, rng);
        b.lastCopy = ctx.tick;
      }

      // --- marks: copy the shape off the ground, get it wrong, occasionally leave your version
      for (let m = 0; m < ctx.marks.length; m++) {
        const mk = ctx.marks[m];
        const dx = mk.x - b.x, dy = mk.y - b.y;
        if (dx * dx + dy * dy > 9) continue;
        if (rng.next() < p.markCopyRate * mk.strength * carry * dt) {
          t.shape += (mk.shape - t.shape) * 0.4 + rng.normal(0.05);
          b.lastCopy = ctx.tick;
        }
      }
      if (rng.next() < p.markEmitChance * dt && ctx.wear.sample(b.x, b.y) > 0.35) {
        let gen = 1;
        for (const mk of ctx.marks) {
          if ((mk.x - b.x) ** 2 + (mk.y - b.y) ** 2 < 36) gen = Math.max(gen, mk.generation + 1);
        }
        this.emitted.push({
          x: b.x, y: b.y,
          shape: t.shape + rng.normal(0.04),
          strength: 0.6,
          generation: gen,
          bornTick: ctx.tick,
        });
      }

      if (b.energy > p.breedEnergy && this.bodies.length + born.length < cap) {
        b.energy -= p.breedCost;
        born.push({
          id: this.nextId++,
          x: b.x + rng.range(-1, 1),
          y: b.y + rng.range(-1, 1),
          vx: 0, vy: 0,
          energy: p.breedCost * 0.75,
          age: 0,
          traits: inherit(t, rng),
          lastCopy: ctx.tick,
        });
      }
    }

    // Death returns matter. A herd that starves in one place fertilises that place.
    const alive: Body[] = [];
    for (const b of this.bodies) {
      if (b.energy <= p.starveAt || b.age > p.maxAge) {
        ctx.biomass.splat(b.x, b.y, 0.05);
        ctx.elev.splat(b.x, b.y, 0.0015);
      } else {
        alive.push(b);
      }
    }
    this.bodies = alive.concat(born);
  }
}
