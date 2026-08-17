# Soul Harvest

An incremental soul-harvesting clicker merge game for **phones**. Harvest souls from bizarre planets, merge reapers, loot relics into a backpack, and ascend through the Void.

Play it as an installable home-screen app (PWA) on iPhone and Android, or wrap it as a native app with Capacitor.

**Influences:** Egg Inc (incremental/automation), Tap Tap Heroes 2 (hero merge/tap combat), World of Warcraft Classic (class system, fantasy aesthetic).

## Play on your phone

1. Open the game in **Safari** (iPhone) or **Chrome** (Android).
2. Add it to your Home Screen:
   - **iPhone:** Share → Add to Home Screen
   - **Android:** menu → Install app / Add to Home Screen
3. Launch Soul Harvest from the icon. It opens fullscreen, portrait, with haptics on supported devices.

Local development:

```bash
npm install
npm run dev        # http://localhost:5173 — use your computer's LAN IP on the phone
npm run preview    # production build on http://localhost:4173
npm test
```

On the same Wi-Fi, open `http://<your-computer-ip>:5173` from your phone.

## Game Features

- **Open Explore Maps** — Walk each planet, scout hidden sites, and harvest from groves, ruins, and rifts
- **Interactive Backpack** — Drag relics, merge tiers, equip bonuses, crush shards; idle reapers fill empty pockets
- **Tactile Feedback** — Press, rummage-hold, ripples, screen shake, and haptics
- **9 Bizarre Planets** — From Terra Mortis to the Void Palace, each with unique soul types
- **Reaper Merge System** — Summon and merge reapers through 10 tiers (Wisp → Void Reaper)
- **WoW-Inspired Classes** — Soul Warlock, Necromancer, Death Knight, Soul Priest
- **Upgrade Tree** — Tap mastery, pack webbing, lucky pockets, merge catalysts, and more
- **Void Ascension** — Prestige system for permanent multipliers
- **Simulated .io Multiplayer** — 50 AI players on leaderboards, global chat, and rotating world events
- **Offline Progress** — Earn souls and backpack loot while away; the PWA caches the game shell

## Native apps (Android / iOS)

Requires Android Studio (SDK 34+) and/or Xcode:

```bash
npm install
npm run build
npx cap add android    # first time only
npx cap add ios        # first time only, macOS + Xcode
npx cap sync
npx cap open android   # Build → Build APK
npx cap open ios       # Run on a simulator or device
```

## Tech Stack

- TypeScript + Vite (web game engine)
- Progressive Web App (standalone, portrait, offline cache)
- Capacitor 6 (Android + iOS wrappers, haptics, splash, keyboard, status bar)
- Mobile-first cosmic UI with safe-area and keyboard insets

## Project Structure

```
src/
  game/
    engine.ts          # Core game state & logic
    planets.ts         # Planet definitions
    reapers.ts         # Reaper tiers, classes, merge logic
    upgrades.ts        # Upgrade tree
    simulatedWorld.ts  # Fake .io multiplayer
    backpack.ts        # Relic grid, merge, equip
    locations.ts       # Walkable planet nodes
  styles/
    main.css           # Mobile game UI
  ui/
    fx.ts              # Haptics, ripples, toasts
  mobile.ts            # PWA install, Capacitor, viewport
  main.ts              # UI rendering & event binding
public/
  manifest.webmanifest
  sw.js
  icons/
```

## License

MIT
