import { Field } from "./field";

/**
 * Heat and damp air.
 *
 * Heat comes in from a lamp above the case, leaves through the glass, and gets pushed around by
 * air that moves because heat moved it. Moisture is evaporated water; it rides the same wind and
 * falls out where the air is cold. Nothing here names a climate zone. Bands and shadows are what
 * the coupling does on a lumpy floor.
 */
export interface ClimateParams {
  ambient: number;        // baseline temperature of the room the case sits in
  lampPower: number;      // energy in at the brightest point
  lampSpread: number;     // how wide the lamp's pool is, in cells
  lapse: number;          // cooling per unit elevation
  loss: number;           // heat lost through the glass per tick
  conduct: number;        // conduction through dirt and air
  buoyancy: number;       // how strongly a heat gradient becomes wind
  windDrag: number;       // wind retained per tick
  maxWind: number;        // hard ceiling on air speed, in cells per tick
  evapRate: number;       // standing water -> air moisture, scaled by heat
  condense: number;       // air moisture -> ground water, once the air is over its limit
  /** How much damp warm air can hold before it has to drop it. */
  saturationBase: number;
  saturationSlope: number;
  /** Constant drizzle, so a saturated sky is not the only way to get weather. */
  drizzle: number;
}

export const defaultClimate: ClimateParams = {
  ambient: 0.30,
  lampPower: 0.80,
  lampSpread: 0.55,
  lapse: 0.55,
  loss: 0.012,
  conduct: 0.16,
  buoyancy: 1.5,
  windDrag: 0.86,
  maxWind: 0.45,
  evapRate: 0.020,
  condense: 0.09,
  saturationBase: 0.06,
  saturationSlope: 0.30,
  drizzle: 0.004,
};

export class Climate {
  heat: Field;
  moisture: Field;
  windX: Field;
  windY: Field;
  /** Player-added or player-removed heat, persistent until the physics eats it. */
  heatBias: Field;

  private g = { x: 0, y: 0 };

  constructor(w: number, h: number) {
    this.heat = new Field(w, h, 0.4);
    this.moisture = new Field(w, h, 0.1);
    this.windX = new Field(w, h, 0);
    this.windY = new Field(w, h, 0);
    this.heatBias = new Field(w, h, 0);
  }

  step(elev: Field, water: Field, p: ClimateParams, dt: number): void {
    const { w, h } = elev;
    const heat = this.heat, moist = this.moisture;
    // Height is measured against the floor's own average, so the lapse rate tracks relief
    // rather than whatever absolute number the dirt happens to sit at after a century of silt.
    const elevMean = elev.mean();
    const cx = (w - 1) * 0.5, cy = (h - 1) * 0.42;
    const sx = p.lampSpread * w, sy = p.lampSpread * h;

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        // Lamp: a soft pool, not a uniform sky. Corners are structurally colder.
        const dx = (x - cx) / sx, dy = (y - cy) / sy;
        const lamp = p.lampPower * Math.exp(-(dx * dx + dy * dy));
        // Standing water takes longer to warm and longer to cool.
        const inertia = 1 / (1 + water.data[i] * 2.5);
        const target = p.ambient + lamp - p.lapse * (elev.data[i] - elevMean) + this.heatBias.data[i];
        heat.data[i] += ((target - heat.data[i]) * p.loss * 6 - p.loss * (heat.data[i] - p.ambient * 0.5)) * dt * inertia;
      }
    }

    heat.diffuse(p.conduct * dt);

    // Wind: air slides from hot to cold. The wind then carries the heat that made it, which is
    // why a warm corner does not stay a tidy circle.
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        heat.gradAt(x, y, this.g);
        this.windX.data[i] = (this.windX.data[i] - this.g.x * p.buoyancy * dt) * p.windDrag;
        this.windY.data[i] = (this.windY.data[i] - this.g.y * p.buoyancy * dt) * p.windDrag;
        // A hard speed limit. Without it a warm patch steepens its own gradient, which drives
        // faster air, which steepens it further, and the case boils in about three hundred ticks.
        const sp = Math.hypot(this.windX.data[i], this.windY.data[i]);
        if (sp > p.maxWind) {
          const k = p.maxWind / sp;
          this.windX.data[i] *= k;
          this.windY.data[i] *= k;
        }
      }
    }

    heat.advect(this.windX, this.windY, dt);
    moist.advect(this.windX, this.windY, dt);

    // Evaporation and rain are two directions of one budget. Warm air holds more; air that goes
    // over its limit — because it cooled, or because it drifted uphill — has to put it down. That
    // is why the cold rim of the case is wet and the lamp's pool is not, without anyone saying so.
    for (let i = 0; i < moist.data.length; i++) {
      const t = heat.data[i];
      const sat = Math.max(0.02, p.saturationBase + p.saturationSlope * Math.max(0, t));
      const headroom = Math.max(0, 1 - moist.data[i] / sat);
      const evap = p.evapRate * Math.max(0, t) * Math.min(water.data[i], 1) * headroom * dt;
      water.data[i] -= evap;
      moist.data[i] += evap;
      const excess = Math.max(0, moist.data[i] - sat);
      const fall = (p.condense * excess + p.drizzle * moist.data[i]) * dt;
      moist.data[i] -= fall;
      water.data[i] += fall;
    }

    moist.diffuse(0.08 * dt);
    moist.clamp(0, 3);
    heat.clamp(-0.5, 1.8);
    // The player's thumb on the thermostat fades. Slowly — slow enough to leave a scar.
    this.heatBias.scale(0.9994);
  }
}
