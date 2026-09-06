import { World } from "./world";
import { Kind } from "./bodies";
import { Field } from "./field";

/**
 * Reading the case.
 *
 * Everything in this file is read-only. Nothing here is allowed to write to a field, move a body,
 * or be imported by anything in the simulation — and nothing in the simulation imports it. That
 * separation is the whole point: the design doc's failure mode is a hidden director, and the way
 * to be sure there isn't one is that the part which recognises "a road" cannot cause a road.
 *
 * What it does is what the camera does. It finds connected runs of worn ground and calls them
 * paths. It finds clumps of bodies and calls them herds. It notices that a stretch of ground is
 * claimed by habits far from its neighbour's and calls the line between them a border. Those are
 * descriptions of arrangements that were already there, in the same sense that "dune" is.
 */

export interface Region {
  /** Cells in the region. */
  size: number;
  cx: number;
  cy: number;
  /** Longest extent in cells, and how elongated it is. A road is long and thin; a camp is not. */
  span: number;
  elongation: number;
  peak: number;
}

export interface Herd {
  size: number;
  cx: number;
  cy: number;
  meanShape: number;
  spread: number;
  hunters: number;
  lineages: number;
}

export interface Structures {
  paths: Region[];
  channels: Region[];
  camps: Region[];
  burns: Region[];
  herds: Herd[];
  frontiers: number;
}

/** Flood-fill connected components over a mask, largest first. */
function components(w: number, h: number, mask: Uint8Array, value: Float32Array, min: number): Region[] {
  const seen = new Uint8Array(w * h);
  const stack: number[] = [];
  const out: Region[] = [];
  for (let start = 0; start < mask.length; start++) {
    if (!mask[start] || seen[start]) continue;
    stack.length = 0;
    stack.push(start);
    seen[start] = 1;
    let size = 0, sx = 0, sy = 0, peak = 0;
    let x0 = w, x1 = 0, y0 = h, y1 = 0;
    while (stack.length) {
      const i = stack.pop()!;
      const x = i % w, y = (i / w) | 0;
      size++;
      sx += x; sy += y;
      if (value[i] > peak) peak = value[i];
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
      if (x > 0 && mask[i - 1] && !seen[i - 1]) { seen[i - 1] = 1; stack.push(i - 1); }
      if (x < w - 1 && mask[i + 1] && !seen[i + 1]) { seen[i + 1] = 1; stack.push(i + 1); }
      if (y > 0 && mask[i - w] && !seen[i - w]) { seen[i - w] = 1; stack.push(i - w); }
      if (y < h - 1 && mask[i + w] && !seen[i + w]) { seen[i + w] = 1; stack.push(i + w); }
    }
    if (size < min) continue;
    const bw = x1 - x0 + 1, bh = y1 - y0 + 1;
    const span = Math.max(bw, bh);
    // Area over bounding box: a winding line fills little of its box, a blob fills most of it.
    const fill = size / (bw * bh);
    out.push({ size, cx: sx / size, cy: sy / size, span, elongation: 1 / Math.max(0.08, fill), peak });
  }
  return out.sort((a, b) => b.size - a.size);
}

function maskOf(f: Field, threshold: number): Uint8Array {
  const m = new Uint8Array(f.data.length);
  for (let i = 0; i < f.data.length; i++) m[i] = f.data[i] > threshold ? 1 : 0;
  return m;
}

export function structures(world: World, limit = 6): Structures {
  const { w, h } = world;

  const paths = components(w, h, maskOf(world.wear, 0.34), world.wear.data, 14).slice(0, limit);
  const camps = components(w, h, maskOf(world.shelter, 0.09), world.shelter.data, 5).slice(0, limit);

  // A channel is not "deep water", it is water that is going somewhere.
  const flow = new Float32Array(w * h);
  const fmask = new Uint8Array(w * h);
  for (let i = 0; i < flow.length; i++) {
    const sp = Math.hypot(world.hydro.vx.data[i], world.hydro.vy.data[i]);
    flow[i] = sp * world.hydro.water.data[i];
    fmask[i] = flow[i] > 0.012 ? 1 : 0;
  }
  const channels = components(w, h, fmask, flow, 12).slice(0, limit);

  // Ground that burned recently enough to still be worth eating.
  const bmask = new Uint8Array(w * h);
  for (let i = 0; i < bmask.length; i++) {
    const t = world.fire.lastBurn.data[i];
    bmask[i] = t >= 0 && world.tick - t < 2200 ? 1 : 0;
  }
  const burns = components(w, h, bmask, world.fire.ash.data, 20).slice(0, limit);

  return {
    paths,
    channels,
    camps,
    burns,
    herds: herds(world, limit),
    frontiers: frontierLength(world),
  };
}

/** Single-link clustering over the bodies. No body knows it is in one of these. */
export function herds(world: World, limit = 6, radius = 6): Herd[] {
  const bodies = world.pop.bodies;
  const n = bodies.length;
  const label = new Int32Array(n).fill(-1);
  const stack: number[] = [];
  const found: Herd[] = [];
  const r2 = radius * radius;

  for (let s = 0; s < n; s++) {
    if (label[s] >= 0) continue;
    stack.length = 0;
    stack.push(s);
    label[s] = found.length;
    const members: number[] = [];
    while (stack.length) {
      const i = stack.pop()!;
      members.push(i);
      const a = bodies[i];
      for (let j = 0; j < n; j++) {
        if (label[j] >= 0) continue;
        const b = bodies[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        if (dx * dx + dy * dy <= r2) { label[j] = label[s]; stack.push(j); }
      }
    }
    if (members.length < 5) continue;
    let sx = 0, sy = 0, ss = 0, hunters = 0;
    const lineages = new Set<number>();
    for (const i of members) {
      const b = bodies[i];
      sx += b.x; sy += b.y; ss += b.traits.shape;
      lineages.add(b.lineage);
      if (b.kind === Kind.Hunter) hunters++;
    }
    const cx = sx / members.length, cy = sy / members.length;
    let spread = 0;
    for (const i of members) spread += Math.hypot(bodies[i].x - cx, bodies[i].y - cy);
    found.push({
      size: members.length,
      cx, cy,
      meanShape: ss / members.length,
      spread: spread / members.length,
      hunters,
      lineages: lineages.size,
    });
  }
  return found.sort((a, b) => b.size - a.size).slice(0, limit);
}

/**
 * How much of the case is a line between two different claims.
 *
 * A frontier cell is one whose neighbours' habits disagree with its own by more than bodies
 * tolerate. Nobody drew it, and it is not stored anywhere — it is recomputed from whose feet
 * have been where.
 */
export function frontierLength(world: World, tolerance = 0.16): number {
  const { w, h } = world;
  const sum = world.claimSum.data, wt = world.claimWeight.data;
  let count = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      if (wt[i] < 0.02) continue;
      const mine = sum[i] / wt[i];
      for (const j of [i - 1, i + 1, i - w, i + w]) {
        if (wt[j] < 0.02) continue;
        if (Math.abs(sum[j] / wt[j] - mine) > tolerance) { count++; break; }
      }
    }
  }
  return count;
}

/** Plain sentences about what is in view. Descriptions, never narration. */
export function describe(s: Structures): string[] {
  const lines: string[] = [];
  const road = s.paths.find((p) => p.elongation > 2.4 && p.span > 12);
  if (road) {
    lines.push(`a path ${road.span} cells long runs through ${road.cx.toFixed(0)}, ${road.cy.toFixed(0)}`);
  } else if (s.paths.length) {
    lines.push(`${s.paths.length} worn patches, none of them a road yet`);
  }
  if (s.camps.length) {
    const c = s.camps[0];
    lines.push(`built ground at ${c.cx.toFixed(0)}, ${c.cy.toFixed(0)} (${c.size} cells)`);
  }
  if (s.channels.length) {
    const ch = s.channels[0];
    lines.push(`water running ${ch.span} cells at ${ch.cx.toFixed(0)}, ${ch.cy.toFixed(0)}`);
  }
  if (s.burns.length) {
    const b = s.burns[0];
    lines.push(`${b.size} cells of recent burn at ${b.cx.toFixed(0)}, ${b.cy.toFixed(0)}`);
  }
  if (s.herds.length) {
    const parts = s.herds.slice(0, 3).map(
      (hd) => `${hd.size}${hd.hunters ? `+${hd.hunters}` : ""} at ${hd.cx.toFixed(0)},${hd.cy.toFixed(0)}`,
    );
    lines.push(`herds: ${parts.join(" · ")}`);
  }
  if (s.frontiers > 40) lines.push(`${s.frontiers} cells of frontier between claims`);
  if (!lines.length) lines.push("nothing here has taken a shape yet");
  return lines;
}

// ---------------------------------------------------------------------------------------------

export interface ChronicleEntry {
  tick: number;
  text: string;
}

/**
 * The chronicle.
 *
 * A running record of what the case has already done. It is written by looking, on a slow
 * interval, and comparing what is there now to what was there last time. It cannot cause any of
 * what it reports — which is exactly why it is allowed to name things.
 */
export class Chronicle {
  entries: ChronicleEntry[] = [];
  private last: {
    tick: number;
    population: number;
    lineages: number;
    roads: number;
    camps: number;
    burning: number;
    split: boolean;
  } | null = null;

  /** Call on a slow interval. Cheap enough at a few hundred ticks apart, too slow to be free. */
  sample(world: World): void {
    const st = world.stats();
    const s = structures(world, 8);
    const roads = s.paths.filter((p) => p.elongation > 2.4 && p.span > 12).length;
    const camps = s.camps.length;
    const split = st.dialectSplit > 0.16;

    const prev = this.last;
    if (prev) {
      const dp = st.population - prev.population;
      if (prev.population > 20 && st.population < prev.population * 0.55) {
        this.write(st.tick, `the herd fell from ${prev.population} to ${st.population}`);
      } else if (prev.population > 0 && dp > prev.population * 0.8 && dp > 25) {
        this.write(st.tick, `the herd doubled to ${st.population}`);
      }
      if (roads > prev.roads) this.write(st.tick, `a worn patch became a road (${roads} now)`);
      if (roads < prev.roads && roads === 0) this.write(st.tick, "the last road faded out");
      if (camps > prev.camps) this.write(st.tick, `something was built at a ${camps}${camps === 1 ? "st" : "th"} site`);
      if (st.lineages < prev.lineages) {
        this.write(st.tick, `${prev.lineages - st.lineages} lineage${prev.lineages - st.lineages > 1 ? "s" : ""} ended`);
      }
      if (st.burning > 4 && prev.burning <= 4) this.write(st.tick, "something caught");
      if (st.burning <= 0.5 && prev.burning > 4) this.write(st.tick, "the fire went out");
      if (split && !prev.split) this.write(st.tick, "the habits split in two");
      if (!split && prev.split) this.write(st.tick, "the two habits ran back together");
      if (st.hunters === 0 && prev.population > 0) {
        const had = this.entries.some((e) => e.text === "the last hunter died");
        if (!had) this.write(st.tick, "the last hunter died");
      }
    } else {
      this.write(st.tick, `inherited: ${st.population} bodies, ${st.lineages} lineages`);
    }

    this.last = {
      tick: st.tick,
      population: st.population,
      lineages: st.lineages,
      roads,
      camps,
      burning: st.burning,
      split,
    };
  }

  private write(tick: number, text: string): void {
    this.entries.push({ tick, text });
    if (this.entries.length > 120) this.entries.shift();
  }
}
