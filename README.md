# Still Tank

A case of living weather. You change one thing. You live with the next version.

`DESIGN.md` is the design. This is what it is made of and how to run it.

```
npm install
npm run dev      # http://localhost:5173
npm test         # the emergence claims, as assertions
npm run build
```

## What this is not

It is not a cellular automaton. There is no grid of cells flipping state by lookup rule, and
nothing in here is a sand game.

The dirt, water, heat, damp air and forage are **continuous fields** integrated as PDEs —
shallow water over an erodible bed, buoyancy-driven advection, logistic growth against a local
carrying capacity. The bodies are **continuous-space agents** with no grid position at all: they
read the fields by bilinear sample, sum six local pulls, and move. The two are coupled in both
directions. Nothing addresses a body by name and nothing anywhere knows the word "herd".

## Where the emergence actually is

The design doc grades emergence three ways. Each grade has a specific mechanism here, and each
one is a test in `tests/emergence.test.ts`.

**Aggregation** — bodies steer up the forage gradient, toward their own idea of a comfortable
temperature, and toward neighbours who sound familiar. Clusters, packed shorelines and grazing
fronts fall out of that. No body is told to join anything.

**Differentiation** — the same six traits produce different lives depending on where a body sat.
A body that grew up on the warm side inherits a warmth preference tuned to the warm side, copies
neighbours who share it, and its descendants stop being able to make a living on the cold side.
Same rules, different job, because of position.

**Record** — this is the one that matters, and it is three couplings:

- footfall writes into `wear`; wear attracts the next body (`roadLove`); traffic compacts the
  ground and incises it; the hollow takes water; the water finishes the cut. A body lives a few
  thousand ticks. The path it started does not care.
- habits are copied off whoever nearby looks well-fed, with per-trait Gaussian copy error. Two
  groups that stop meeting stop averaging, and their trait distributions walk apart. `shape` —
  a number with no payoff attached to it whatsoever — drifts fastest, because nothing corrects
  it. That is a dialect.
- a mark you leave on the ground is copied by passing bodies, wrong, and they re-emit their
  version. Generation 0 is your hand. Generation 4 is a custom.

## The failure modes it is built against

The doc lists five. What was done about each:

- **Script wearing a mustache** — there is no director. Nothing watches a meter and fires an
  event. `World.step` runs four subsystems in an order that lets each one's output land in the
  next one's input, and that is the entire control flow. The ledger records what *you* did so the
  camera can name it later; it never causes anything.
- **Explosion of degrees of freedom** — six traits, one body type, four media. Every readout is a
  number you can point at.
- **Frozen success** — grazing is density-dependent (a body takes a *share* of what is standing,
  not a fixed ration), so the herd overshoots, strips, disperses and recovers. Over 10,000 ticks
  the population oscillates roughly 30–200 without settling or dying out.
- **Noise success** — noise enters at exactly two places: per-body venture (scaled up by hunger)
  and copy error. Everything else is deterministic given the seed, and the whole case replays
  identically from one.
- **Player as author of everything** — the six tools write a number into a medium and stop
  existing. None of them addresses a body. The physics is free to eat the change, and often does.

## The numerics, because they bite

Three feedback loops in here will detonate if left uncapped, and all three did during
development:

- heat gradient → wind → advected heat → steeper gradient. Fixed with a hard air-speed ceiling
  and by making semi-Lagrangian advection conserve its total (backtracing quietly manufactures
  the quantity wherever the velocity field converges).
- surface slope → flow speed → erosion → steeper slope. Fixed with a flow-speed ceiling and a
  per-tick cap on how much dirt one cell may gain or lose.
- silt with nowhere to go piles into one sink forever. Fixed by exporting silt with the draining
  water and welling the same mass back up through the floor, so the case keeps its dirt but not
  its arrangement of it.

`dt` is capped at 1 inside `World.step` for the same reason. These are explicit schemes; a bigger
step does not fast-forward the case, it blows it up. Offline catch-up therefore runs real ticks
and caps how many, rather than taking coarser ones.

## Layout

```
src/sim/field.ts       scalar field: bilinear sample, gradient, diffusion, conservative advection
src/sim/rng.ts         seeded xorshift — the case must replay exactly
src/sim/climate.ts     lamp, conduction, buoyant wind, evaporation and rain as one budget
src/sim/hydrology.ts   shallow water, erosion, deposition, hillslope creep, silt export
src/sim/forage.ts      logistic growth against local carrying capacity; density-dependent grazing
src/sim/bodies.ts      continuous-space agents, spatial hash, the six local pulls
src/sim/culture.ts     traits, imitation with copy error, dialect distance, marks
src/sim/world.ts       the coupling order, the ledger, the probe
src/sim/tools.ts       the six tools, as biases
src/sim/persist.ts     the case does not reset when you blink
src/render/            zoom-as-map camera, one volume, grit at close range
src/ui/main.ts         the thin strip, the readout, the slow tick
```

## Playing it

Drag to move, wheel to zoom — there is one volume and no second map. Pick a tool, click once.
Shift-click anywhere to read what is there, including anything you did there and when.

The tick slider is the only concession to impatience. At 1 the case runs at 8 ticks a second and
a road takes an hour. The interesting sessions are the ones where you use a tool twice and spend
the rest of the time deciding whether the case is going to keep your change.

## The honest limit

Same as the doc's. This gets you dunes, banks, roads, grazing fronts, borders and drifting
habits. It does not get you anyone home inside the pattern, and nothing in here pretends
otherwise. A flock turning is not a soul.
