# Soul Harvest

An incremental soul-harvesting clicker merge game for Android. Harvest souls from increasingly bizarre planets, merge reapers, compete on simulated leaderboards, and ascend through the Void.

**Influences:** Egg Inc (incremental/automation), Tap Tap Heroes 2 (hero merge/tap combat), World of Warcraft Classic (class system, fantasy aesthetic).

## Game Features

- **Tap to Harvest** — Click the planet orb to collect souls
- **9 Bizarre Planets** — From Terra Mortis to the Void Palace, each with unique soul types
- **Reaper Merge System** — Summon and merge reapers through 10 tiers (Wisp → Void Reaper)
- **WoW-Inspired Classes** — Soul Warlock, Necromancer, Death Knight, Soul Priest
- **Upgrade Tree** — Tap mastery, soul magnets, merge catalysts, and more
- **Void Ascension** — Prestige system for permanent multipliers
- **Simulated .io Multiplayer** — 50 AI players on leaderboards, global chat, and rotating world events
- **Offline Progress** — Earn souls while away (up to 8 hours)

## Tech Stack

- TypeScript + Vite (web game engine)
- Capacitor 6 (Android native wrapper with haptics)
- Mobile-first responsive UI with WoW/cosmic dark theme

## Development

```bash
npm install
npm run dev        # Play in browser at http://localhost:5173
npm run build      # Production build
npm test           # Run unit tests
```

## Android Build

Requires Android Studio with SDK 34+:

```bash
npm install
npm run build
npx cap add android    # First time only
npx cap sync android
npx cap open android   # Opens Android Studio
```

Build APK from Android Studio: **Build → Build Bundle(s) / APK(s) → Build APK(s)**

## Project Structure

```
src/
  game/
    engine.ts          # Core game state & logic
    planets.ts         # Planet definitions
    reapers.ts         # Reaper tiers, classes, merge logic
    upgrades.ts        # Upgrade tree
    simulatedWorld.ts  # Fake .io multiplayer
  styles/
    main.css           # Mobile game UI
  utils/
    format.ts          # Number formatting
  main.ts              # UI rendering & event binding
```

## License

MIT
