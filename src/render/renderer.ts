import { World } from "../sim/world";
import { Camera } from "./camera";

export type Overlay = "none" | "heat" | "water" | "wear" | "forage" | "border";

/**
 * Drawing.
 *
 * The ground is painted once per few ticks into an offscreen buffer at field resolution, then
 * scaled by the camera. Bodies are drawn on top at whatever size the zoom implies: at range they
 * stop being animals and become density, which is the correct thing to see at that scale.
 */
export class Renderer {
  private buf: HTMLCanvasElement;
  private bctx: CanvasRenderingContext2D;
  private img: ImageData;
  private lastPaint = -1;

  constructor(private world: World) {
    this.buf = document.createElement("canvas");
    this.buf.width = world.w;
    this.buf.height = world.h;
    const c = this.buf.getContext("2d");
    if (!c) throw new Error("no 2d context");
    this.bctx = c;
    this.img = this.bctx.createImageData(world.w, world.h);
  }

  paintGround(overlay: Overlay): void {
    const w = this.world;
    const px = this.img.data;
    const [elo, ehi] = w.elev.minmax();
    const espan = Math.max(1e-4, ehi - elo);

    for (let y = 0; y < w.h; y++) {
      for (let x = 0; x < w.w; x++) {
        const i = y * w.w + x;
        const e = (w.elev.data[i] - elo) / espan;

        // Hillshade: the only reason a ridge reads as a ridge instead of a colour.
        const gx = w.elev.data[w.elev.idx(x + 1, y)] - w.elev.data[w.elev.idx(x - 1, y)];
        const gy = w.elev.data[w.elev.idx(x, y + 1)] - w.elev.data[w.elev.idx(x, y - 1)];
        const shade = Math.max(0.48, Math.min(1.34, 1 - (gx * 2.6 + gy * 2.0) * 4.2));

        const bio = Math.min(1, w.forage.biomass.data[i]);
        // Everything is damp; only standing water should read as water.
        const wet = Math.max(0, Math.min(1, (w.hydro.water.data[i] - 0.11) / 0.30));
        const worn = Math.min(1, w.wear.data[i] * 1.6);

        // Dirt, greened by what grows on it, browned back down by what walks on it.
        const green = Math.min(1, bio / 0.75);
        // Dirt goes pale and dry as it rises; green sits on top of it rather than replacing it.
        let r = (52 + e * 104) * (1 - green * 0.34) + 30 * worn;
        let g = (46 + e * 92) * (1 - green * 0.06) + green * 62 - 12 * worn;
        let b = (40 + e * 76) * (1 - green * 0.40) - 10 * worn;

        if (wet > 0.02) {
          const t = Math.min(0.88, wet);
          r = r * (1 - t) + 30 * t;
          g = g * (1 - t) + (64 + 34 * (1 - wet)) * t;
          b = b * (1 - t) + (104 + 52 * (1 - wet)) * t;
        }

        r *= shade; g *= shade; b *= shade;

        switch (overlay) {
          case "heat": {
            const t = Math.max(0, Math.min(1, w.climate.heat.data[i] / 1.3));
            r = r * 0.35 + 255 * t * 0.75;
            g = g * 0.35 + 90 * (1 - Math.abs(t - 0.5) * 2) * 0.9;
            b = b * 0.35 + 235 * (1 - t) * 0.6;
            break;
          }
          case "water": {
            const t = Math.min(1, w.hydro.water.data[i] * 3.2);
            r = r * (1 - t); g = g * (1 - t) + 120 * t; b = b * (1 - t) + 255 * t;
            break;
          }
          case "wear": {
            const t = Math.min(1, w.wear.data[i] * 1.4);
            r = r * (1 - t) + 246 * t; g = g * (1 - t) + 196 * t; b = b * (1 - t) + 92 * t;
            break;
          }
          case "forage": {
            const t = Math.min(1, w.forage.capacity.data[i]);
            r = r * (1 - t) + 90 * t; g = g * (1 - t) + 235 * t; b = b * (1 - t) + 110 * t;
            break;
          }
          case "border": {
            const t = Math.min(1, w.border.data[i]);
            const s = Math.min(1, w.forage.sterile.data[i]);
            const c = Math.min(1, w.carry.data[i]);
            r = r * (1 - t * 0.8) + 250 * t; g = g * (1 - t * 0.8) + 60 * t + 200 * c;
            b = b * (1 - t * 0.8) + 90 * t + 60 * s;
            break;
          }
          default: break;
        }

        const o = i * 4;
        px[o] = clamp255(r); px[o + 1] = clamp255(g); px[o + 2] = clamp255(b); px[o + 3] = 255;
      }
    }
    this.bctx.putImageData(this.img, 0, 0);
    this.lastPaint = this.world.tick;
  }

  draw(
    ctx: CanvasRenderingContext2D,
    cam: Camera,
    vw: number,
    vh: number,
    overlay: Overlay,
    repaint: boolean,
  ): void {
    const w = this.world;
    if (repaint || this.lastPaint < 0) this.paintGround(overlay);

    ctx.fillStyle = "#07080b";
    ctx.fillRect(0, 0, vw, vh);

    // Smooth when magnifying (the field is a sample of a continuum, not a tilemap), sharp when
    // shrinking so a ridge does not blur away at range.
    ctx.imageSmoothingEnabled = cam.scale > 1.2;
    const [ox, oy] = cam.toScreen(0, 0, vw, vh);
    ctx.drawImage(this.buf, ox, oy, w.w * cam.scale, w.h * cam.scale);

    // Close in, the ground gets grit: a fixed per-cell speckle so dirt reads as dirt instead of
    // a smooth colour ramp. It carries no information — it is texture, and it admits as much.
    if (cam.scale > 5) {
      const [wx0, wy0] = cam.toWorld(0, 0, vw, vh);
      const [wx1, wy1] = cam.toWorld(vw, vh, vw, vh);
      const gx0 = Math.max(0, Math.floor(wx0)), gx1 = Math.min(w.w - 1, Math.ceil(wx1));
      const gy0 = Math.max(0, Math.floor(wy0)), gy1 = Math.min(w.h - 1, Math.ceil(wy1));
      const grit = Math.min(0.30, (cam.scale - 5) / 40);
      for (let y = gy0; y <= gy1; y++) {
        for (let x = gx0; x <= gx1; x++) {
          const i = y * w.w + x;
          const dry = 1 - Math.min(1, w.hydro.water.data[i] * 6);
          if (dry < 0.15) continue;
          const [sx, sy] = cam.toScreen(x, y, vw, vh);
          for (let k = 0; k < 5; k++) {
            const keep = hash3(x + 5, y + 11, k);
            if (keep < 0.42) continue; // uneven counts, or the grit reads as a halftone screen
            const n = hash3(x, y, k);
            const m = hash3(y, x, k + 7);
            const size = cam.scale * (0.07 + hash3(x + 3, y + 9, k) * 0.16);
            const dark = hash3(x + 31, y + 17, k) > 0.45;
            ctx.fillStyle = dark
              ? `rgba(0,0,0,${grit * dry * 0.70})`
              : `rgba(228,214,190,${grit * dry * 0.28})`;
            ctx.fillRect(sx + n * cam.scale, sy + m * cam.scale, size, size);
          }
        }
      }
    }

    // Bodies. Below ~1.2 px per cell they are dots of density, not creatures.
    const r = Math.max(0.6, cam.scale * 0.34);
    const detailed = cam.scale > 3.5;
    for (const b of w.pop.bodies) {
      const [sx, sy] = cam.toScreen(b.x, b.y, vw, vh);
      if (sx < -8 || sy < -8 || sx > vw + 8 || sy > vh + 8) continue;
      // Colour by habit, so a dialect split is visible as two colours drifting apart.
      const hue = 12 + b.traits.shape * 300;
      const light = 42 + Math.min(1, b.energy) * 26;
      ctx.fillStyle = `hsl(${hue} 70% ${light}%)`;
      ctx.beginPath();
      ctx.arc(sx, sy, r, 0, Math.PI * 2);
      ctx.fill();
      if (detailed) {
        ctx.strokeStyle = `hsl(${hue} 70% ${light + 18}%)`;
        ctx.lineWidth = Math.max(0.5, cam.scale * 0.08);
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(sx + b.vx * cam.scale * 2.2, sy + b.vy * cam.scale * 2.2);
        ctx.stroke();
      }
    }

    // Marks: the player's in white, copies dimmer and further from the shape they started as.
    for (const m of w.marks) {
      const [sx, sy] = cam.toScreen(m.x, m.y, vw, vh);
      if (sx < -20 || sy < -20 || sx > vw + 20 || sy > vh + 20) continue;
      const size = Math.max(2.5, cam.scale * 1.1);
      const fade = Math.max(0.1, m.strength) / (1 + m.generation * 0.5);
      ctx.strokeStyle = m.generation === 0
        ? `rgba(255,255,255,${0.85 * m.strength})`
        : `hsla(${12 + m.shape * 300} 80% 72% / ${fade})`;
      ctx.lineWidth = 1.2;
      drawGlyph(ctx, sx, sy, size, m.shape);
    }
  }
}

/** A shape with no meaning. That is the point of it. */
function drawGlyph(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, shape: number): void {
  const sides = 3 + Math.floor(shape * 5.99);
  const rot = shape * Math.PI * 2;
  ctx.beginPath();
  for (let i = 0; i <= sides; i++) {
    const a = rot + (i / sides) * Math.PI * 2;
    const px = x + Math.cos(a) * s, py = y + Math.sin(a) * s;
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }
  ctx.stroke();
}

/** Stable per-cell noise, so the grit does not crawl while you look at it. */
function hash3(x: number, y: number, k: number): number {
  let n = (x * 374761393 + y * 668265263 + k * 2147483647) | 0;
  n = (n ^ (n >>> 13)) * 1274126177;
  return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
}

function clamp255(v: number): number {
  return v < 0 ? 0 : v > 255 ? 255 : v | 0;
}
