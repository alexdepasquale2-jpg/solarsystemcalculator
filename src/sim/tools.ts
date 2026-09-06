import { World } from "./world";
import { Field } from "./field";

/**
 * The six tools.
 *
 * Each one is a bias, not a command. None of them addresses a body. They put a number into a
 * medium and then stop existing. What happens next is the physics' business, and it may well
 * eat the change entirely — that is a legitimate outcome and the game does not apologise for it.
 */

export type ToolId =
  | "matter"    // add / take away dirt
  | "heat"      // raise / lower temperature
  | "block"     // close a path
  | "open"      // cut a path
  | "rule"      // mark a patch with a rule
  | "mark";     // leave something copyable

export type RuleKind = "barren" | "carry" | "border";

export interface ToolUse {
  tool: ToolId;
  x: number;
  y: number;
  radius: number;
  /** Signed for matter and heat: positive adds, negative takes away. */
  strength: number;
  rule?: RuleKind;
  /** For "mark": which shape you leave. Bodies will copy it wrong. */
  shape?: number;
}

/** Soft circular brush. Nothing in the tank has a hard edge except a border you insist on. */
function brush(f: Field, cx: number, cy: number, r: number, amp: number, hardEdge = false): void {
  const x0 = Math.max(0, Math.floor(cx - r)), x1 = Math.min(f.w - 1, Math.ceil(cx + r));
  const y0 = Math.max(0, Math.floor(cy - r)), y1 = Math.min(f.h - 1, Math.ceil(cy + r));
  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) {
      const d = Math.hypot(x - cx, y - cy) / r;
      if (d > 1) continue;
      const w = hardEdge ? 1 : Math.cos(d * Math.PI * 0.5) ** 2;
      f.data[y * f.w + x] += amp * w;
    }
  }
}

/** Scale a field down toward zero inside the brush, instead of pushing it through zero. */
function softenTo(f: Field, cx: number, cy: number, r: number, keep: number): void {
  const x0 = Math.max(0, Math.floor(cx - r)), x1 = Math.min(f.w - 1, Math.ceil(cx + r));
  const y0 = Math.max(0, Math.floor(cy - r)), y1 = Math.min(f.h - 1, Math.ceil(cy + r));
  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) {
      const d = Math.hypot(x - cx, y - cy) / r;
      if (d > 1) continue;
      const w = Math.cos(d * Math.PI * 0.5) ** 2;
      const i = y * f.w + x;
      f.data[i] *= keep * w + (1 - w);
    }
  }
}

export function applyTool(world: World, use: ToolUse): string {
  const { x, y, radius: r, strength: s } = use;
  let note = "";

  switch (use.tool) {
    case "matter":
      brush(world.elev, x, y, r, s * 0.35);
      // Fresh fill is loose: it gives up whatever stubbornness the ground had, and will slump
      // and wash before it settles into anything. It cannot go below bare dirt, though — the
      // erosion term treats negative hardness as a licence to pile up forever.
      softenTo(world.hydro.hardness, x, y, r, 0.6);
      note = s > 0 ? "poured" : "dug out";
      break;

    case "heat":
      brush(world.climate.heatBias, x, y, r, s * 0.5);
      note = s > 0 ? "warmed" : "chilled";
      break;

    case "block": {
      // A wall, and the ground under it made stubborn. It will still lose, eventually.
      brush(world.elev, x, y, r, Math.abs(s) * 0.55);
      brush(world.hydro.hardness, x, y, r, Math.abs(s) * 1.4);
      brush(world.wear, x, y, r, -0.6);
      note = "blocked";
      break;
    }

    case "open": {
      brush(world.elev, x, y, r, -Math.abs(s) * 0.5);
      softenTo(world.hydro.hardness, x, y, r, 0.15);
      note = "cut open";
      break;
    }

    case "rule": {
      const kind = use.rule ?? "border";
      if (kind === "barren") {
        brush(world.forage.sterile, x, y, r, Math.abs(s));
        note = "declared barren";
      } else if (kind === "carry") {
        brush(world.carry, x, y, r, Math.abs(s));
        note = "made sound carry";
      } else {
        brush(world.border, x, y, r, Math.abs(s), true);
        note = "called a border";
      }
      break;
    }

    case "mark":
      world.marks.push({
        x, y,
        shape: use.shape ?? world.rng.next(),
        strength: Math.max(0.2, Math.abs(s)),
        generation: 0,
        bornTick: world.tick,
      });
      note = "left a mark";
      break;
  }

  world.record({ tick: world.tick, tool: use.tool, x, y, radius: r, note });
  return note;
}
