import { World, defaultParams } from "./world";
import { Field } from "./field";

/**
 * Saving.
 *
 * The case does not reset when you blink, so the save has to carry the media, not a summary.
 * Fields go out as base64 float arrays; bodies and the ledger go out as they are. A save also
 * carries wall-clock time, so reopening can charge you for the hours you were gone.
 */

const VERSION = 2;

function encodeField(f: Field): string {
  const bytes = new Uint8Array(f.data.buffer, f.data.byteOffset, f.data.byteLength);
  let s = "";
  const CH = 0x8000;
  for (let i = 0; i < bytes.length; i += CH) {
    s += String.fromCharCode(...bytes.subarray(i, Math.min(bytes.length, i + CH)));
  }
  return btoa(s);
}

function decodeInto(f: Field, b64: string): void {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  f.data.set(new Float32Array(bytes.buffer, 0, f.data.length));
}

const FIELDS = (w: World): Record<string, Field> => ({
  elev: w.elev,
  wear: w.wear,
  border: w.border,
  carry: w.carry,
  heat: w.climate.heat,
  moisture: w.climate.moisture,
  heatBias: w.climate.heatBias,
  water: w.hydro.water,
  sediment: w.hydro.sediment,
  hardness: w.hydro.hardness,
  biomass: w.forage.biomass,
  sterile: w.forage.sterile,
  shelter: w.shelter,
  claimSum: w.claimSum,
  claimWeight: w.claimWeight,
  flame: w.fire.flame,
  ash: w.fire.ash,
  lastBurn: w.fire.lastBurn,
  dust: w.aeolian.dust,
});

export function serialize(world: World): string {
  const fields: Record<string, string> = {};
  for (const [k, f] of Object.entries(FIELDS(world))) fields[k] = encodeField(f);
  return JSON.stringify({
    version: VERSION,
    savedAt: Date.now(),
    w: world.w,
    h: world.h,
    tick: world.tick,
    rng: world.rng.state,
    fields,
    bodies: world.pop.bodies,
    marks: world.marks,
    ledger: world.ledger,
  });
}

export interface LoadResult {
  world: World;
  /** Real seconds the case was left unattended. */
  awaySeconds: number;
}

export function deserialize(json: string): LoadResult | null {
  let data: any;
  try { data = JSON.parse(json); } catch { return null; }
  if (!data || data.version !== VERSION) return null;

  const world = new World({ width: data.w, height: data.h, params: defaultParams });
  const target = FIELDS(world);
  for (const [k, b64] of Object.entries(data.fields as Record<string, string>)) {
    if (target[k]) decodeInto(target[k], b64);
  }
  world.tick = data.tick;
  world.rng.state = data.rng;
  world.pop.bodies = data.bodies;
  world.marks = data.marks ?? [];
  world.ledger = data.ledger ?? [];
  return { world, awaySeconds: Math.max(0, (Date.now() - data.savedAt) / 1000) };
}
