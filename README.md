# incgame

A generative incremental game. Every seed is a **different game** — not a different
skin on the same game. The resources, the actions, the buildings, the upgrade
trees, the rules that make the numbers interesting, the names, the colours: all
generated from one integer.

No dependencies. Clone it and play:

```bash
python -m incgame serve
# open http://127.0.0.1:8000
```

Python 3.9+. Nothing to install — the engine, the balance harness, and the HTTP
server are standard library only.

## Playing on your phone

The game needs the Python server running somewhere your phone can reach. Two ways:

**Same Wi-Fi as a computer** (easiest). On the computer:

```bash
python -m incgame serve --host 0.0.0.0
```

It prints the address to type into your phone:

```
incgame serving on http://127.0.0.1:8000/   (this machine)
                    http://192.168.1.24:8000/   (phone, same Wi-Fi)
```

Open that second URL on the phone, then **Add to Home Screen** — the manifest makes
it launch fullscreen with no browser chrome. Progress lives in the phone's
`localStorage`, so it persists across restarts and credits up to eight hours of
offline production when you come back.

`--host 0.0.0.0` listens on every interface. There is no authentication and
sessions are held in memory: fine on a home network, not on a café one.

**Entirely on the phone, no computer.** Android: install
[Termux](https://termux.dev), then `pkg install python git`, clone, and
`python -m incgame serve`. Open `http://127.0.0.1:8000` in your phone's browser.
iOS: [a-Shell](https://holzschu.github.io/a-Shell_iOS/) ships Python and works the
same way.

Note that the page is not playable offline — closing the server stops the game.
The manifest makes it installable, but there is no service worker, and the server
is the sole authority on the economy by design.

## What gets generated

Every run generates:

| | |
|---|---|
| **Resources** | 3–6, arranged into a conversion chain. Tier 0 comes from your hands; each tier above is refined from the one below. Some branch, some cap, some decay. |
| **Actions** | Free clicks and costed conversions, with their own cooldowns and ratios. |
| **Generators** | Passive producers with geometric cost growth. Some consume a lower tier to run — and *throttle* rather than stop when starved. |
| **Upgrades** | 30–60 across five cost tiers, grouped into families that lean toward different kinds of effect. |
| **Mechanics** | 2–4 emergent systems wired to *this run's* content (see below). |
| **Prestige** | A named reset currency and 6–9 permanent upgrades. |

The same seed always produces the same game, byte for byte. Different seeds
produce structurally different games — different chain depths, different numbers of
verbs, different rules.

## The mechanics

Seven kinds, 2–4 per run, each wired to randomly chosen generated content. A rule
in the abstract is not interesting; a rule pointed at *your* economy is:

- **Synergy** — every upgrade you own from one family raises something.
- **Cascade** — one action sometimes fires another for free.
- **Overflow** — production past a cap spills into another resource instead of vanishing.
- **Momentum** — consecutive actions stack a multiplier; pausing resets it.
- **Resonance** — every Nth action pays out several times over.
- **Symbiosis** — one resource's production scales with how much of another you hold.
- **Scarcity** — a resource decays. Spend it or lose it.

Combined with upkeep throttling, these interact without being told to. A run with
a decaying resource, an upkeep-hungry generator that eats it, and an overflow
mechanic pointed at it plays nothing like a run with momentum and a cascade.

## Commands

```bash
python -m incgame serve                   # play (add --seed N for a specific run)
python -m incgame generate --seed 42      # print a run's full content
python -m incgame simulate --seed 42      # autoplay it, report pacing
python -m incgame balance --runs 400      # audit many seeds for balance problems
```

`generate` is the fastest way to see what the generator does:

```
The Fractal Terrace   (seed 42)
Everything is still potential, which is to say: nothing works yet.

RESOURCES (4)
  t0  Essence                      cap 2.00K
  t1  Silent Ore                   uncapped
  t2  Crystalline Chime            cap 150
  t3  Cindered Nectar              cap 40

MECHANICS (3)
  [resonance] Bright Codex
      Every 7th action pays out x5.4.
  [cascade] Feral Calibration
      14% of the time, Unspool Silent Ore also triggers Thresh Cindered Nectar
      for free -- cost and cooldown ignored.
```

## How balance works without playtesting

A hand-authored game is balanced by playing it. Two billion seeds cannot be, so
the game plays itself: `incgame/balance.py` runs a deliberately mediocre
autoplayer at thousands of times real speed and reports pacing — time to first
upgrade, time to first building, time to prestige, longest stall, whether the
economy ever went downstream.

```
$ python -m incgame balance --runs 600 --minutes 20
audited 600 seeds at 20 simulated minutes each
  healthy: 521/600
  medians
    first_generator_at    5.9
    first_upgrade_at     32.0
    first_prestige_at   231.9
    ascensions            3.0
```

The 79 seeds it flags are not soft-locks — the validator makes those impossible —
they are pacing outliers. Measured over 300 seeds: 7.7% buy their whole upgrade
tree inside twenty minutes, 3.0% leave the autoplayer with nothing to buy for five
minutes, 2.7% ascend faster than once every two minutes.

Rebalancing means editing `TUNING` in `incgame/generator.py` and re-running the
audit — never editing a particular seed. Several real bugs were found this way and
only this way: gate thresholds that ignored resource tier and so demanded 9,720 of
a resource capped at 25; deep-tier generators producing one unit per forty
minutes; a prestige loop that collapsed to 24 seconds. None were visible in the
seed that happened to be open.

## Architecture

```
incgame/
  generator.py   seed -> GameDef. Pure function. All balance in TUNING.
  model.py       frozen dataclasses: Resource, Action, Generator, Upgrade, ...
  engine.py      GameState + GameEngine: ticking, spending, gates, prestige
  view.py        engine state -> client payload, including what's revealed yet
  balance.py     headless autoplayer and multi-seed audit
  save.py        seed + progress in, regenerated definition out
  server.py      stdlib HTTP: JSON API + static frontend
frontend/
  index.html, css/style.css, js/{format,api,ui,app}.js
tests/           112 tests, stdlib unittest (pytest-compatible)
```

Two decisions shape most of the rest:

**The definition is derived, never stored.** A save is a seed plus progress. The
content is regenerated on load, so saves are ~1KB, and a save can never disagree
with the generator.

**The clock is injected.** `GameEngine(game, clock=...)` means the live game,
offline catch-up, and the balance harness all run the same code path — the harness
simulates twenty minutes in about a second, without sleeping.

Randomness inside a run (crits, cascades) is derived from the run seed and the
saved action counter, so a save replays identically. Reproducibility survives the
random parts.

## Playing

Four tabs. **Work** is manual actions plus a plain-language list of this run's
rules — in a generated game the player has no genre knowledge to fall back on, so
an unexplained rule is indistinguishable from a bug. **Build**, **Research** and
**Ascend** are the buildings, the upgrade tree, and prestige.

Locked content appears once you are ~35% of the way to its unlock condition, with
the condition spelled out. A goal you can see is a goal; something that pops into
existence fully formed is a non-event.

Progress autosaves to `localStorage` every ten seconds and credits up to eight
hours of offline production. The menu exports and imports saves, and shows the
seed — worth copying if a run turns out well.

Mobile-first: bottom tab bar, ≥48px targets, safe-area insets, no horizontal page
scroll, installable as a PWA. On desktop, keys `1`–`9` fire actions.

## Tests

```bash
python -m unittest discover -s tests    # no dependencies
pytest                                   # if you prefer
```

The generator tests assert *properties across seeds*, not outputs of specific
seeds — every resource has a producer, every run has a free opening action, gates
reference real content, tier-0 upgrades are never probabilistic. Asserting that
seed 42 produces "Essence" would be asserting the output of a PRNG, and would
break the moment anything improved.

`test_format_parity.py` shells out to `node` to check that the Python and
JavaScript number formatters agree (the client formats interpolated values the
server never sent). It skips if node is unavailable.

## Known limits

- Content depth is finite: five upgrade tiers, one prestige layer. A long session
  eventually exhausts the tree, and permanent upgrades hit their level caps. Deeper
  meta-layers are not implemented. This is the largest remaining balance gap —
  7.7% of seeds are cleared out within twenty minutes.
- Deep-chain seeds (5–6 resources) prestige on the fast end of the envelope even
  after depth-scaling and escalation — roughly 2 minutes per ascension against a
  ~4 minute median. Fast, but inside the playable band.
- ~13% of seeds fall outside the pacing envelope in some way. None are
  unplayable (the validator rules that out), but the tail is real and the audit
  reports it rather than hiding it.
- The server is single-player and keeps sessions in memory, with no auth. It binds
  to loopback by default; don't expose it.
- No sound, no animation beyond CSS, no icons per resource.

## Licence

MIT.
