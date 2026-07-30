# CLAUDE.md

Guidance for building a fully generative, emergent incremental mobile game.

## Project Vision

**Generative Incremental Engine** — A procedurally generated incremental mobile game where **every session is unique**. Each play session generates:

- Unique resource types, actions, and mechanics
- Emergent gameplay from system interactions (not hand-coded)
- Unique UI, narrative framing, progression paths
- Unique upgrade trees, prestige mechanics, meta-progression
- Unique names, descriptions, flavor text

The game should feel like a different game every time you play, yet always follow the **incremental genre core**: accumulate resources, buy upgrades, reset for bonuses, repeat. Everything else emerges from the generated systems.

## Architecture

**Backend (Python):**
- Game engine and state management
- Procedural generation (resources, mechanics, interactions)
- Action resolution and tick processing
- Save/load serialization
- API for the frontend

**Frontend (HTML5/JavaScript):**
- Real-time UI rendering
- Click handlers and input processing
- Mobile-optimized layout
- WebSocket or fetch communication with backend
- Local caching of game state

**Communication:**
- REST API or WebSocket for real-time updates
- Frontend sends actions (click, buy, prestige, etc.)
- Backend returns new state, resources gained, notifications
- Minimal latency (aim for <100ms round-trip on good connection)

```
backend/
  game/
    __init__.py
    engine.py              Main GameEngine; tick loop, state management
    generator.py           Procedural generation (resources, actions, upgrades)
    emergence.py           Interaction systems; how mechanics affect each other
    serializer.py          Save/load game state
    world.py               World state; current resources, owned upgrades, etc.
  resources/
    base.py                Resource class; rate, caps, conversions
    generator.py           Generate unique resource types
  actions/
    base.py                Action class; cost, reward, effects
    generator.py           Generate unique action types
  upgrades/
    base.py                Upgrade class; effects on resources/actions
    generator.py           Generate tech trees, prestige multipliers
  mechanics/
    base.py                Mechanic base class
    synergy.py             Interactions between mechanics (emergence)
    generator.py           Generate unique mechanical systems
  api/
    server.py              FastAPI or Flask web server
    routes.py              /state, /action, /save, /prestige, etc.
  config.py                Game tuning parameters (generation seeds, balance)

frontend/
  index.html               Single-page app shell
  css/
    mobile.css             Mobile-first responsive design
    generated.css          Dynamically injected styles (generated colors, themes)
  js/
    app.js                 Main app logic, state sync
    ui.js                  Render and update UI
    api.js                 API calls to backend
    storage.js             LocalStorage caching
  assets/
    icons/                 (generated or placeholder)
    sounds/                (optional sfx)
```

## Core Concepts

### 1. Resource (Procedurally Generated)

Every game generates 3–8 unique resource types. Each has:
- **Name** (generated: "Essence," "Chronons," "Whimsy")
- **Rate** (base production per tick: 0.1/s, 5/s, etc.)
- **Cap** (max stored before overflow; can be increased by upgrades)
- **Display format** (raw number, exponential, custom)
- **Flavor** (description, icon color, associated mechanical theme)
- **Decay** (optional: resource slowly decays, encouraging spending)
- **Conversion** (optional: converts into other resources at a ratio)

Example generated resource:
```python
Resource(
    id="luminescence",
    name="Luminescence",
    rate=0.5,  # per second
    cap=1000,
    color="#FFD700",  # generated
    description="A shimmering essence that fuels reality.",
    conversions={"ethereal_charge": 0.1}  # 1 luminescence → 0.1 ethereal charge
)
```

### 2. Action (Procedurally Generated)

Actions are things the player can do repeatedly (or hold down). Examples:
- "Click the Void" (generates resource A)
- "Commune with the Zeitgeist" (generates resource B, costs resource A)
- "Resonate" (passive; generates if you own upgrade X)

Each action has:
- **Name** (generated)
- **Cost** (0 or more resource types)
- **Reward** (generates 0 or more resources)
- **Cooldown** (optional; can only be used once per N seconds)
- **Scaling** (reward grows with upgrades or owned count)
- **Flavor** (description, animation cue)

```python
Action(
    id="commune_zeitgeist",
    name="Commune with the Zeitgeist",
    cost={"luminescence": 10},
    reward={"temporal_echo": 5},
    cooldown=0.5,  # 500ms between clicks
    description="Bridge the gap between moments.",
)
```

### 3. Upgrade (Procedurally Generated)

Upgrades modify the game. They appear in a tech tree and can have prerequisites. Examples:
- "+10% Luminescence production"
- "Unlock new action: Transcend"
- "Luminescence no longer decays"
- "Every 5 clicks, double your next reward"

Each upgrade has:
- **Name** (generated)
- **Cost** (resources or prestige currency)
- **Effect** (a function or rule that modifies game state)
- **Prerequisite** (which other upgrades must be bought first)
- **Tier** (early/mid/late game)
- **Flavor** (description)

```python
Upgrade(
    id="luminescence_production_v1",
    name="Resonant Amplification",
    cost={"temporal_echo": 50},
    effect=UpgradeEffect(
        type="multiply_resource_rate",
        resource="luminescence",
        multiplier=1.1
    ),
    prerequisite=None,
    tier="early",
    description="Attune to the underlying harmonics.",
)
```

### 4. Prestige (Meta-progression)

When the player can no longer progress, they prestige:
- Reset all resources to 0
- Reset all non-prestige upgrades
- Gain prestige currency based on total resources ever earned
- Prestige currency buys permanent multipliers that persist across runs

This is the **meta-game loop**. Each prestige run should feel different because new upgrades become available and new mechanics emerge.

## Procedural Generation Strategy

### Seeding

Every game session has a **seed** (can be user-provided or random). All generation is deterministic from the seed:
```python
def generate_game(seed: int) -> Game:
    rng = random.Random(seed)
    resources = generate_resources(rng)
    actions = generate_actions(rng, resources)
    upgrades = generate_upgrades(rng, actions, resources)
    mechanics = generate_mechanics(rng, resources, actions, upgrades)
    return Game(resources, actions, upgrades, mechanics, seed=seed)
```

### Generation Phases

**Phase 1: Base Resources (3–8 types)**
- Pick names from a word pool (nouns, adjectives, suffixes)
- Assign base rates (0.1–10 per second)
- Assign caps (1000–100,000)
- Assign colors and themes

**Phase 2: Base Actions (5–12 types)**
- Some cost resources, some are passive
- Costs and rewards vary; ensure some feedback loops (action A generates resource B, which fuels action C)
- Mix of high-reward-high-cost and low-reward-no-cost

**Phase 3: Upgrades (30–60 types, in tiers)**
- Early game: unlock actions, basic multipliers
- Mid game: resource caps, new mechanics, conversion options
- Late game: exponential multipliers, prestige mechanics

**Phase 4: Mechanics (3–5 emergent systems)**
- **Synergy:** "If you own 5+ upgrades from the X tree, gains from Y increase"
- **Cascades:** "Whenever you click action A, there's a 5% chance to trigger action B"
- **Scarcity:** Some resources decay; encourages spending
- **Gating:** Certain upgrades become available only after you hit a resource threshold
- **Feedback loops:** Action A generates resource B, resource B unlocks upgrades that boost action A

### Emergence Through Interaction

The magic happens when systems interact. Don't hard-code synergies; let them emerge:

```python
# Example: Emergent synergy
# If the generation picks:
# - Resource A with decay
# - Action X that converts A → B
# - Upgrade "Halt Decay" for A
# Then emergent strategy: buy "Halt Decay" to prevent loss, build up A, then mass-convert to B
```

Emergence is achieved by:
1. **Asymmetric resources** — Different rates, caps, conversions
2. **Scaling** — Upgrades apply multipliers to action rewards or resource rates
3. **Gating** — Unlocking new actions as you reach thresholds
4. **Feedback loops** — Earlier actions feed into later ones
5. **Randomized costs and rewards** — Creates unique trade-offs each run

## Game Loop

### Backend Tick Loop

```python
class GameEngine:
    def __init__(self, game_state):
        self.state = game_state
        self.last_tick = time.time()
    
    def tick(self):
        """Called ~10x per second; process passive generation."""
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now
        
        # Update passive actions (they generate automatically)
        for action in self.state.actions:
            if action.is_passive:
                reward = action.calculate_reward(self.state) * dt
                self.state.add_resource(action.reward_resource, reward)
        
        # Apply decay
        for resource in self.state.resources:
            if resource.decay > 0:
                self.state.resources[resource.id] *= (1 - resource.decay * dt)
        
        # Check for gated upgrades becoming available
        for upgrade in self.state.upgrades:
            if not upgrade.unlocked and self._check_gate(upgrade):
                upgrade.unlocked = True
        
        return self.state
    
    def player_action(self, action_id: str):
        """Player clicks or activates an action."""
        action = self.state.actions[action_id]
        if action.can_use(self.state):
            self.state.spend_resources(action.cost)
            reward = action.calculate_reward(self.state)
            self.state.add_resource(action.reward_resource, reward)
            return {"success": True, "reward": reward}
        else:
            return {"success": False, "reason": "Cannot afford"}
    
    def buy_upgrade(self, upgrade_id: str):
        """Player buys an upgrade."""
        upgrade = self.state.upgrades[upgrade_id]
        if upgrade.can_buy(self.state):
            self.state.spend_resources(upgrade.cost)
            upgrade.apply(self.state)
            return {"success": True}
        else:
            return {"success": False, "reason": "Cannot afford"}
    
    def prestige(self):
        """Player resets and enters prestige mode."""
        prestige_points = calculate_prestige_reward(self.state)
        self.state.prestige_currency += prestige_points
        self.state.reset()
        return {"prestige_earned": prestige_points}
```

### Frontend Communication

```javascript
// app.js
class GameClient {
    async initialize() {
        const response = await fetch('/api/new-game');
        this.state = await response.json();
        this.render();
    }
    
    async playerAction(actionId) {
        const response = await fetch('/api/action', {
            method: 'POST',
            body: JSON.stringify({ action_id: actionId })
        });
        const result = await response.json();
        if (result.success) {
            this.state = result.state;
            this.showNotification(`+${result.reward.toFixed(1)} resources`);
            this.render();
        }
    }
    
    async buyUpgrade(upgradeId) {
        const response = await fetch('/api/buy-upgrade', {
            method: 'POST',
            body: JSON.stringify({ upgrade_id: upgradeId })
        });
        const result = await response.json();
        if (result.success) {
            this.state = result.state;
            this.render();
        }
    }
    
    async prestige() {
        const response = await fetch('/api/prestige', { method: 'POST' });
        const result = await response.json();
        this.state = result.state;
        this.render();
    }
    
    render() {
        // Update UI from this.state
        // Dynamically render resources, actions, upgrades based on generated names
    }
    
    tick() {
        // Request updated state every 100ms or so
        this.playerAction('passive-tick');
    }
}
```

## Key Design Constraints

### Balance

- **Early game:** Should be fun immediately. Clicking should give quick feedback.
- **Mid game:** Progression slows; upgrades become essential. Strategy emerges.
- **Late game:** Exponential scaling; players prepare for prestige.
- **Prestige:** Reset feels like progress (multiplier upgrades make the next run faster).

To ensure balance in a generative game:
1. **Resource sinks** — Ensure players have reasons to spend resources
2. **Pacing** — Time between meaningful upgrades should be 30 seconds to 5 minutes
3. **Thresholds** — Milestone rewards (reach 1M resources, buy 10 upgrades, etc.)
4. **Soft caps** — Decay, cooldowns, caps that make progress non-linear

### Mobile-First

- **Touch targets:** Buttons ≥48px
- **No scroll requirement:** All critical UI visible without scrolling
- **Minimal bandwidth:** Fetch only deltas, not full state
- **Offline-friendly:** Game continues ticking in localStorage while closed
- **No ads:** Pure gameplay focus

### Emergent, Not Random

**Bad:** Randomly assign resource names and hope they make sense.
**Good:** Generate interconnected systems where player choices matter and strategies arise naturally.

Example of emergence:
- Resource A has no passive generation
- Action X converts A → B
- Upgrade "A Production" unlocks if you own 3 B-related upgrades
- Player discovers: "I need to mass-convert A to B, then use B to unlock A production"

## Development Workflow

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e ".[dev]"  # pytest, black, ruff, mypy

cd frontend
npm install
npm run dev
```

### Running

```bash
# Terminal 1: Backend
python -m incremental_engine serve --port 5000

# Terminal 2: Frontend dev server
cd frontend && npm run dev

# Visit http://localhost:3000
```

### Testing Generative Systems

```bash
# Test that generation is deterministic
python -m incremental_engine generate-game --seed 42 > game1.json
python -m incremental_engine generate-game --seed 42 > game2.json
diff game1.json game2.json  # Should be identical

# Test balance across multiple generated games
python scripts/test_generation.py --runs 100 --log results.csv
# Analyze: prestige timing, progression curves, resource flows
```

### Code Quality

```bash
black .
ruff check . --fix
mypy backend/
pytest tests/ --cov=backend
```

## Testing Generative Systems

**Unit tests:**
- Resource generation produces valid resources
- Actions can be executed (cost checking, reward calculation)
- Upgrades apply effects correctly
- Prestige math is correct

**Integration tests:**
- Full game loop: generate → tick → player action → state update
- Multiple prestige runs; state persists correctly
- Emergence detection: verify that generated systems have interesting interactions

**Generative tests:**
- Seed reproducibility (same seed → same game)
- Balance analysis across 100+ generated games (prestige point curves, upgrade counts, resource flow graphs)
- Emergence metrics (how many upgrade combinations exist? how many are useful?)

Example balance test:
```python
def test_balance_across_seeds():
    for seed in range(1, 101):
        game = generate_game(seed)
        
        # Simulate ~5 min of play
        state = simulate_game(game, ticks=30000)
        
        # Check: player should have unlocked 5–15 upgrades, not stuck
        assert 5 <= len(state.bought_upgrades) <= 15
        
        # Check: prestige shouldn't be instant or impossible
        prestige_points = calculate_prestige(state)
        assert 10 <= prestige_points <= 1000000
    
    print("All 100 seeds balanced ✓")
```

## Saving & Loading

Save format: JSON with full game state.

```json
{
  "seed": 12345,
  "timestamp": "2025-01-15T10:30:00Z",
  "resources": {
    "luminescence": 5000.5,
    "temporal_echo": 150
  },
  "bought_upgrades": [
    "luminescence_production_v1",
    "unlock_commune_zeitgeist"
  ],
  "prestige_currency": 42,
  "total_earned": 50000,
  "playtime_seconds": 600
}
```

On load: regenerate the game structure from seed, apply all bought upgrades, restore resource counts.

## Distribution

**Web:**
- Host frontend as static files (Netlify, GitHub Pages)
- Run backend on a cheap cloud server (Railway, Fly.io, Heroku)
- Or: backend in WASM (Pyodide) so everything runs in browser

**Mobile (web app):**
- Add `manifest.json` for PWA install
- Support offline (service worker, localStorage sync)

**Desktop (future):**
- Tauri or Electron wrapper around HTML5 frontend

## Working Agreements

1. **Generation is law.** If it's possible to generate, don't hard-code it.
2. **Test every seed.** Generative systems must be tested across dozens of seeds, not just default.
3. **Emergence over hand-craft.** Let mechanics interact naturally; don't force every synergy.
4. **Mobile first.** Every UI decision should consider <5" screens and touch.
5. **Balance with data.** Run generative tests frequently; tweak generation parameters, not individual games.
6. **Seed preservation.** Always save and display the seed. Reproducibility is a feature.

## Success Metrics

A successful run feels like:
- ✓ New aesthetic and names every game
- ✓ Surprising strategy emerges (not obvious what to do)
- ✓ Clear prestige point; player knows when to reset
- ✓ Prestige multipliers make the next run feel different
- ✓ 5–30 minute play loop is satisfying
- ✓ Mobile layout is responsive and fun to play

## Next Steps

1. Build the generator framework (`Generator` class with seeded RNG)
2. Implement resource, action, upgrade generation
3. Build the game engine tick loop and state management
4. Create a minimal frontend (hardcoded resources/actions first)
5. Test balance across 50+ seeds
6. Add prestige mechanics
7. Iterate on emergence and fun factor
8. Polish mobile UI
9. Ship it

Start with a working, boring game (hand-coded resources/actions). Once the engine is solid, plug in the generator and watch it emerge.
