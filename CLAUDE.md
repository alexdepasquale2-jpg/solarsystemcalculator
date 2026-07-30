# CLAUDE.md

Working notes for AI assistants and developers on **incgame**, a generative
incremental game. Read `README.md` first for what the game is; this file is about
how to change it without breaking it.

## The one rule

**Every seed is a different game, and no seed may be unplayable.**

Those two halves pull against each other, and almost every design decision in the
codebase is a resolution of that tension. Variety is the product, so the generator
is given wide latitude. But a generated run that soft-locks is indistinguishable
from a crash to the player, and there are two billion seeds, so latitude has to be
bounded by machine-checked invariants rather than by taste.

Concretely: **do not hand-author content, and do not special-case seeds.** If a
particular seed plays badly, the fix goes in `TUNING` or in a generation rule, and
is verified across hundreds of seeds with `python -m incgame balance`. A fix that
only helps seed 348 is not a fix.

## Quick start

No dependencies. Python 3.9+.

```bash
python -m incgame serve                      # play at http://127.0.0.1:8000
python -m incgame generate --seed 42         # print a run's content
python -m incgame simulate --seed 42         # autoplay, report pacing
python -m incgame balance --runs 400         # audit many seeds

python -m unittest discover -s tests         # 113 tests, no deps
python -m unittest tests.test_engine         # one module (fast)
```

The balance tests take ~2 minutes; everything else is a few seconds. When
iterating on generation, run `tests.test_generator` (fast, property-based) plus a
`balance --runs 100` before the full suite.

## Layout

```
incgame/
  generator.py   seed -> GameDef. Pure function of the seed. All balance in TUNING.
  model.py       frozen dataclasses + fmt_number
  engine.py      GameState + GameEngine: ticking, spending, gates, prestige
  view.py        engine -> client payload, and what is revealed yet
  balance.py     headless autoplayer + multi-seed audit
  save.py        seed + progress in; definition regenerated on load
  server.py      stdlib HTTP: JSON API + static files
  rng.py         seeded helpers: Namer, palettes, round_nice, weighted
  names.py       word pools (data only)
frontend/
  index.html; css/style.css; js/{format,api,ui,app}.js; manifest.json; icon.svg
tests/           test_{generator,engine,save,balance,server,format_parity}.py
```

Generation phases run in a fixed order and each may depend only on earlier ones:
theme → resources → actions → generators → upgrades → mechanics → prestige. If you
need a later phase's output in an earlier one, the phase order is wrong, not the
dependency.

## Architectural commitments

These are load-bearing. Changing one means changing a lot of other things.

**Zero runtime dependencies.** Engine, harness, and server are standard library
only. `git clone && python -m incgame serve` must keep working on a bare Python
install. New requirements go behind an optional extra in `pyproject.toml`, never
into the core.

**The definition is derived, never stored.** A save is a seed plus progress;
`save.py` regenerates the `GameDef` on load. Saves stay ~1KB and can never
disagree with the generator. The corollary is that **changing the generator
invalidates old saves** — `SAVE_VERSION` and `generator_version` detect the
mismatch and report it. `_compute_mods` also tolerates unknown ids, so a small
change degrades to "you lost some upgrades" rather than crashing.

**The clock is injected.** `GameEngine(game, clock=...)`. The live game, offline
catch-up, and the balance harness all run the same `advance()` path — the harness
simulates twenty minutes in about a second and nothing sleeps. Never call
`time.time()` in engine code; take it from `self.clock()`.

**Randomness inside a run is derived from the save.** `_roll()` hashes the run seed
with `state.action_count`, both persisted, so crits and cascades replay
identically. Do not introduce a `random.Random` instance into runtime code — it
would make saves non-reproducible and `_roll` runs on every click.

**The server is the only authority on the economy.** The client extrapolates
amounts between polls purely for smooth numbers; every poll overwrites the guess
and every mutating call returns fresh state. Do not move economy logic into JS.

**Nothing touches the global RNG.** Every generation function takes an explicit
`random.Random`. `tests.test_generator.test_generation_does_not_touch_global_rng`
enforces this — it is what makes a seed reproducible in a process that has done
other work.

## How to change balance

1. Edit `TUNING` in `generator.py`. Every balance number lives there.
2. `python -m incgame simulate --seed N` on a few seeds to sanity-check.
3. `python -m incgame balance --runs 400` and read the medians and failures.
4. `python -m unittest tests.test_balance`.

The current envelope, measured over 600 seeds at 20 simulated minutes:

| | median |
|---|---|
| first generator | ~6s |
| first upgrade | ~32s |
| prestige available | ~3.9 min |
| ascensions | 3 |
| upgrade tree bought | ~39% |
| healthy seeds | 521/600 (87%) |

The 13% that fall out are pacing outliers, not soft-locks — `validate_game()` makes
soft-locks impossible. Over 300 seeds the composition is: 7.7% buy their whole
tree inside the window, 3.0% stall the autoplayer for five minutes, 2.7% ascend
faster than once every two minutes. Tree exhaustion is the largest remaining gap
and is fundamentally a content-volume problem, not a tuning one.

`balance.py` reports **medians, not means**: one pathological seed must not hide
behind an average, and finding pathological seeds is the entire point.

The autoplayer is deliberately mediocre — it buys the cheapest thing that helps and
converts only surplus. If a mediocre strategy reaches prestige in reasonable time,
an attentive player certainly will; if a mediocre strategy stalls, the seed is
badly generated regardless of what an expert could extract. Two autoplayer
behaviours exist specifically to avoid false alarms, and both are load-bearing:
`_reserve()` (a player saving for an upgrade stops spending) and
`_should_prestige()` (a player resets when the run beats the last one, not the
instant it is possible). Without them every seed reports as stalled or as a
25-second treadmill, and the report becomes noise.

## Bugs the harness found, and what they teach

Each of these was invisible in whatever seed happened to be open, and each left a
permanent check behind. When adding a generation rule, ask which of these shapes it
could repeat.

**Thresholds priced in the wrong units.** Upgrade gates scaled with the *upgrade's*
tier but ignored the tier of the resource they were measured in, so a late gate
demanded 9,720 of a resource that caps at 25 and trickles in at 0.0004/s. The
upgrade hid forever and the run silently lost part of its tree. Fixed by
`_resource_gate()` pricing gates in the same per-tier units as costs.
*Lesson: any generated number compared against a resource must scale with that
resource's tier.*

**Dead content at the deep end.** `gen_rate_falloff` at 0.16 made a tier-4
generator produce one unit per forty minutes. It existed, it was buyable, it did
nothing. Now 0.22.
*Lesson: check the extremes of every generated range, not the middle.*

**A meta-loop that collapsed.** Permanent multipliers compound, so run score grows
geometrically across ascensions while the `sqrt` in `prestige_points` only halves
the exponent. Points kept climbing, the next reset stayed trivial, and one seed
ascended 84 times in twenty minutes. A *linear* surcharge lost the same race; only
geometric escalation (`prestige_escalation ** ascensions`) matches geometric
output growth. The harness had no check for this, which is why it went unnoticed —
`MIN_ASCENSION_SECONDS` exists now.
*Lesson: when the harness misses a failure mode, adding the check matters more
than the fix.*

**Upgrades that made you worse.** `jitter` around a 1.2 base yields `[0.96, 1.44]`,
so 3.6% of generated multipliers were below 1.0 — you could pay for a downgrade —
and another 3.4% were under +5%, imperceptible. Fixed by `_gain()`, which floors
every multiplier at `MIN_UPGRADE_GAIN`.
*Lesson: `jitter` around a base near 1.0 crosses 1.0. An upgrade must never be a
trap; the player assumes it and the autoplayer's cheapest-first buying relies on
it.*

**Effects aimed at content the player did not have.** A tier-0 upgrade offering
"×1.5 storage for a tier-3 resource" is not wrong, but it is unreadable and unfelt
as the *first thing a new run shows you*. `_target_for_tier()` prefers targets at
or just below the upgrade's own depth. This made upgrades roughly 40% stronger in
practice without changing a single multiplier, which is why `cost_unit_by_tier`
was raised to compensate.
*Lesson: an effect's target matters as much as its magnitude, and fixing wasted
effects is a power buff that needs a cost pass.*

## Invariants the generator must maintain

`validate_game()` runs on every `generate_game()` and raises `InvalidGame` rather
than returning a broken run. It checks: a tier-0 resource exists; a free ungated
action exists (the run must be playable in the first frame); every resource has a
producer; every cost and gate names real content; generator `cost_growth > 1`; the
upgrade requirement graph points strictly backwards in tier; prestige is
configured.

Add a check here whenever you add a generation rule that could produce a
soft-lock. `tests.test_generator.test_validator_rejects_a_broken_game` deliberately
breaks a game to prove the validator is not vacuous — keep that honest.

The property tests assert things true of *every* seed, never the output of a
specific seed. Asserting that seed 42 produces "Essence" is asserting the output of
a PRNG and breaks the moment anything improves.

## Engine gotchas

- **`OrbitState`-style duplication does not exist here, but zero-state does.**
  `_reset_run()` is called both on first construction and on prestige, so a new
  game and a post-prestige game take the same path. Keep it that way.
- **`_credit()` is the only place `amounts` grows.** That is what makes lifetime
  earnings, and therefore prestige value, impossible to double-count. Route new
  income through it.
- **Cascades are one level deep, on purpose.** Two generated actions pointing at
  each other would otherwise be an unbounded loop.
- **Reductions are floored** (`MIN_REDUCTION`) so stacking cooldown or cost
  reductions can approach but never reach zero.
- **Upkeep throttles, it does not stop.** A starved generator scales output down
  proportionally. This is the main source of mid-run tension: overbuilding a
  tier-2 farm quietly starves the tier-1 stock feeding it, and the fix is a
  decision rather than a reload.
- **Adding a field to `GameDef`** means updating `to_dict()` too, or the client
  silently loses it. Use `dataclasses.replace()` to derive modified copies —
  `GameDef` caches lookup dicts via `object.__setattr__`, so `**obj.__dict__`
  splatting picks up the caches and fails.

## Frontend gotchas

- **`keyedList` in `ui.js` is the only place list children are added or removed.**
  Re-rendering with `innerHTML` at the poll rate cancels in-progress taps, drops
  `:active` feedback, and resets the upgrade list's scroll position several times a
  second. Node identity is load-bearing.
- **`fmt_number` exists twice**, in `model.py` and `format.js`, because the client
  formats interpolated values the server never sent. `tests/test_format_parity.py`
  shells out to `node` and compares both against the same table. If you change one,
  change both.
- **Colours come from the seed.** Resource colours, `--accent`, and `--hue` are set
  from the generated theme at runtime. Do not hardcode a hue the generator owns.
  The game is dark in both colour schemes on purpose: the palette picks lightness
  in the 58–72% band for contrast against dark, and light mode would need a second
  palette and a second contrast validation per seed.
- **Mechanics are surfaced in plain language** in the Work tab. In a generated game
  the player has no genre knowledge to fall back on — they cannot know a momentum
  system exists until told — so an unexplained rule is indistinguishable from a
  bug. Any new mechanic needs a generated one-sentence description and, where it
  has live state, a readout in `view._mechanics`.
- **Locked content is revealed at `TEASE_THRESHOLD`** (35% of its gate) with the
  condition spelled out. A goal you can see is a goal; content that appears fully
  formed is a non-event.

## Known limits

Honest about scope rather than aspirational:

- **Content depth is finite.** Five upgrade tiers, one prestige layer. A long
  session exhausts the tree and hits `max_level` on permanent upgrades. Deeper
  meta-layers are not implemented, and with geometric prestige escalation a very
  long save will eventually find ascensions impractical. This is the biggest
  remaining gap: 7.7% of seeds are cleared out inside twenty minutes, and no amount
  of `TUNING` fixes that — it needs more generated content per tier, or a sixth
  tier, or a second prestige layer.
- **Deep-chain seeds sit at the fast end.** 5–6 resource chains ascend around every
  two minutes against a ~4 minute median, even after depth-scaled divisors and
  escalation. Inside the playable band, but it is the widest remaining variance.
- **~13% of seeds fall outside the pacing envelope.** None are unplayable. The
  tests bound the proportion (`test_most_runs_do_not_exhaust_their_content` allows
  up to 15%) rather than forbidding the tail, because a short seed is legitimate
  variety and forbidding it would forbid the variation that is the product.
- **The server is single-player, in-memory, unauthenticated.** Loopback by default.
  Do not expose it. Sessions are lost on restart — the client's localStorage save is
  the real persistence.
- **No sound, no animation beyond CSS, no per-resource icons.**

## Working agreements

- Develop on `claude/claude-md-docs-e91w1b`; push with `git push -u origin <branch>`.
  Do not push to `main`. Do not open a PR unless asked.
- Run `python -m unittest discover -s tests` before committing. If you touched
  generation, also run `python -m incgame balance --runs 200`.
- Balance changes go in `TUNING` with a comment explaining *why* the number moved,
  not just what it is. The existing comments in `TUNING` are the model to follow —
  several record a specific failure the number prevents.
- When you fix a generated-content bug, ask whether the harness would have caught
  it. If not, add the check. That is worth more than the fix.
