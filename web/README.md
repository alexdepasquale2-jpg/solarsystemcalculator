# Standalone build

`play.html` is the whole game in one file, with the generator and engine ported
from Python to JavaScript so it runs from a URL with no server. Open it directly
(`file://`), host it anywhere static, or add it to a phone's home screen.

## Why this exists

The Python build needs a server. That is fine on a laptop and awkward on a phone:
you need a machine on the same Wi-Fi, or Termux, and the game stops when the
server does. This build has no such requirement.

## What it costs

**The engine now exists twice.** `incgame/{generator,engine}.py` and the `<script>`
in `play.html` implement the same rules, and nothing enforces that they agree. If
you change generation or economy logic in one, change it in the other, or they
drift. This is the same trade already made for `fmt_number` (`model.py` /
`format.js`) — but that one is forty lines guarded by `tests/test_format_parity.py`,
and this one is closer to a thousand with no equivalent guard.

If the duplication ever becomes a real maintenance problem, the way out is to run
the Python engine in the browser under Pyodide and delete the JS port, rather than
to keep hand-syncing two copies.

**Seeds are not portable between builds.** The two use different PRNGs (mulberry32
here, Mersenne Twister in Python), so seed 42 is a different world in each. Within
either build a seed is fully reproducible, which is the property a player cares
about. Saves are likewise not interchangeable.

**No balance harness.** `incgame/balance.py` audits hundreds of seeds against the
Python generator. The numbers here are copied from the audited `TUNING`, so the
balance should match, but nothing verifies it. Changing a number here without
changing it there means it is unverified.

## What is faithful

Structure, phase order, and every `TUNING` value follow the Python source,
including the fixes the harness found:

- gates priced in per-tier units, so a late gate cannot demand 9,720 of a resource
  that caps at 25
- `gen_rate_falloff` at 0.22, so deep-tier generators are not dead content
- upgrade multipliers floored at 1.08, so an upgrade is never a downgrade
- effect targets biased to the player's own depth, with costs raised to match
- geometric prestige escalation, so the meta-loop does not collapse to seconds
- upkeep throttling, capped overflow, one-level cascades, deterministic crit rolls
  derived from the seed and the action counter

A browser check across 400 seeds confirms all of them generate and validate, and
that the property invariants from `tests/test_generator.py` hold: every run has a
free opening action, no tier-0 upgrade is probabilistic, no multiplier is below
1.0, no tier-0 resource decays.

## Saves

`localStorage` under `incgame.standalone.save`: a seed plus progress, with the
content regenerated on load — the same design as `save.py`. Up to eight hours of
offline production is credited when you come back. Unknown ids from an older build
are dropped rather than crashing the run.
