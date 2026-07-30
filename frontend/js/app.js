/*
 * Application loop and wiring.
 *
 * Three cadences, deliberately different:
 *
 *   ~8Hz  animation frame -- interpolates resource amounts and cooldown sweeps
 *         from the last known rates. Purely local; costs no network.
 *   ~1Hz  poll -- fetches authoritative state and re-renders the lists.
 *   ~10s  autosave -- pulls a save blob and stores it in localStorage.
 *
 * The server is the only authority on the economy. The client extrapolates
 * between polls so numbers move smoothly, but every poll overwrites the guess,
 * and every mutating call returns fresh state. There is no client-side economy to
 * drift out of sync.
 */

(() => {
  const SAVE_KEY = 'incgame.save';
  const POLL_MS = 1000;
  const FRAME_MS = 125;
  const AUTOSAVE_MS = 10000;

  let state = null;
  // Snapshot for interpolation: amounts and rates as of the last poll.
  let snapshot = { at: 0, amounts: {}, rates: {}, caps: {} };
  let readyAt = {};
  let affordable = {};
  let polling = false;
  let lastFrame = 0;
  let visible = true;

  // ------------------------------------------------------------- rendering --

  function apply(next) {
    const firstRun = state === null || state.seed !== next.seed;
    state = next;

    if (firstRun) {
      UI.setTheme(next.theme);
      document.getElementById('run-title').textContent = next.title;
      document.getElementById('run-flavor').textContent = next.flavor;
      document.getElementById('menu-seed').textContent = String(next.seed);
      document.title = `${next.title} — incremental`;
    }

    const now = performance.now();
    snapshot = { at: now, amounts: {}, rates: {}, caps: {} };
    next.resources.forEach((res) => {
      snapshot.amounts[res.id] = res.amount;
      snapshot.rates[res.id] = res.rate;
      if (res.cap !== null) snapshot.caps[res.id] = res.cap;
    });

    readyAt = {};
    affordable = {};
    next.actions.forEach((action) => {
      if (action.ready_in > 0) readyAt[action.id] = now + action.ready_in * 1000;
      affordable[action.id] = action.affordable;
    });

    UI.renderResources(next);
    UI.renderActions(next, doAction);
    UI.renderMechanics(next);
    UI.renderGenerators(next, buyGenerator);
    UI.renderUpgrades(next, buyUpgrade);
    UI.renderPrestige(next, doPrestige, buyPrestige);
    UI.renderStats(next);
    UI.setBadges(next);
  }

  function frame(now) {
    requestAnimationFrame(frame);
    if (!state || !visible) return;
    if (now - lastFrame < FRAME_MS) return;
    lastFrame = now;

    // Extrapolate from the last poll. Clamped at the cap so a capped resource
    // does not visibly overshoot and snap back on the next poll.
    const elapsed = (now - snapshot.at) / 1000;
    const projected = {};
    for (const id in snapshot.amounts) {
      const cap = snapshot.caps[id];
      let value = snapshot.amounts[id] + (snapshot.rates[id] || 0) * elapsed;
      if (value < 0) value = 0;
      if (cap !== undefined && value > cap) value = cap;
      projected[id] = value;
    }
    UI.tickResources(projected, snapshot.caps);
    UI.tickActions(readyAt, now, affordable);
  }

  // --------------------------------------------------------------- actions --

  async function guard(promise, label) {
    try {
      return await promise;
    } catch (err) {
      UI.toast(`${label}: ${err.message}`, 'bad');
      return null;
    }
  }

  async function doAction(id) {
    // Optimistic cooldown so a rapid tapper gets immediate feedback rather than
    // firing three requests into a cooldown the server will reject anyway.
    const action = state && state.actions.find((a) => a.id === id);
    if (action && action.cooldown > 0) {
      readyAt[id] = performance.now() + action.cooldown * 1000;
    }

    const data = await guard(API.action(id), 'Action failed');
    if (!data) return;

    const result = data.result || {};
    if (result.ok) {
      const gained = Object.entries(result.gained || {})
        .map(([rid, amount]) => `+${fmtNumber(amount)} ${nameOf(data, rid)}`)
        .join('  ');
      if (result.crit) {
        UI.toast(`×${result.multiplier.toFixed(1)}!  ${gained}`, 'crit');
      } else if (result.multiplier > 1.15) {
        UI.toast(`×${result.multiplier.toFixed(2)}  ${gained}`, 'good');
      } else if (gained) {
        UI.toast(gained);
      }
      if (result.cascade) {
        UI.toast(`${result.cascade.name} fired free`, 'crit');
      }
    } else if (result.reason && result.reason !== 'cooling down') {
      UI.toast(result.reason, 'bad');
    }
    apply(data);
  }

  async function buyGenerator(id, count) {
    const data = await guard(API.buyGenerator(id, count), 'Build failed');
    if (!data) return;
    const result = data.result || {};
    if (result.ok) {
      UI.toast(`Built ×${result.bought}`, 'good');
    } else if (result.reason) {
      UI.toast(result.reason, 'bad');
    }
    apply(data);
  }

  async function buyUpgrade(id) {
    const data = await guard(API.buyUpgrade(id), 'Research failed');
    if (!data) return;
    const result = data.result || {};
    if (result.ok) UI.toast(`Researched ${result.name}`, 'good');
    else if (result.reason) UI.toast(result.reason, 'bad');
    apply(data);
  }

  async function buyPrestige(id) {
    const data = await guard(API.buyPrestige(id), 'Purchase failed');
    if (!data) return;
    const result = data.result || {};
    if (result.ok) UI.toast('Permanent upgrade bought', 'good');
    else if (result.reason) UI.toast(result.reason, 'bad');
    apply(data);
  }

  async function doPrestige() {
    if (!state || !state.prestige.can_prestige) return;
    const name = state.prestige.name;
    if (!confirm(`Ascend now?\n\nThis clears the run and grants ${state.prestige.points_display} ${name}.`)) {
      return;
    }
    const data = await guard(API.prestige(), 'Ascend failed');
    if (!data) return;
    const result = data.result || {};
    if (result.ok) {
      UI.toast(`Ascended — +${fmtNumber(result.points)} ${name}`, 'crit');
      UI.showTab('do');
    } else if (result.reason) {
      UI.toast(result.reason, 'bad');
    }
    apply(data);
    save();
  }

  function nameOf(data, resourceId) {
    const res = data.resources.find((r) => r.id === resourceId);
    return res ? res.name : resourceId;
  }

  // ------------------------------------------------------------ persistence --

  async function save() {
    try {
      const blob = await API.save();
      localStorage.setItem(SAVE_KEY, JSON.stringify(blob));
    } catch (err) {
      // Autosave failing is not worth interrupting play over; the next tick
      // retries, and a full disk is not something the player can act on here.
    }
  }

  async function boot() {
    const stored = localStorage.getItem(SAVE_KEY);
    let data = null;

    if (stored) {
      try {
        // Offline production is credited by the server from the save timestamp.
        data = await API.load(JSON.parse(stored));
      } catch (err) {
        UI.toast('Could not load save — starting fresh', 'bad');
      }
    }
    if (!data) {
      data = await API.state(true);
    }

    apply(data);
    document.getElementById('boot').classList.add('is-gone');
    setTimeout(() => document.getElementById('boot').remove(), 400);

    setInterval(poll, POLL_MS);
    setInterval(save, AUTOSAVE_MS);
    requestAnimationFrame(frame);
  }

  async function poll() {
    if (polling || !visible) return;
    polling = true;
    try {
      apply(await API.state());
    } catch (err) {
      // A dropped poll is invisible: the interpolator keeps the numbers moving
      // and the next poll re-syncs.
    } finally {
      polling = false;
    }
  }

  // ------------------------------------------------------------------ menu --

  function wireMenu() {
    const dialog = document.getElementById('menu');
    const open = document.getElementById('btn-menu');

    open.addEventListener('click', () => {
      if (state) UI.renderStats(state);
      dialog.showModal();
      open.setAttribute('aria-expanded', 'true');
    });
    document.getElementById('btn-close-menu').addEventListener('click', () => {
      dialog.close();
      open.setAttribute('aria-expanded', 'false');
    });

    document.getElementById('btn-copy-seed').addEventListener('click', async () => {
      if (!state) return;
      try {
        await navigator.clipboard.writeText(String(state.seed));
        UI.toast('Seed copied', 'good');
      } catch (err) {
        UI.toast(`Seed: ${state.seed}`);
      }
    });

    document.getElementById('btn-export').addEventListener('click', async () => {
      const blob = await API.save();
      const text = JSON.stringify(blob);
      try {
        await navigator.clipboard.writeText(text);
        UI.toast('Save copied to clipboard', 'good');
      } catch (err) {
        // Clipboard is unavailable over plain HTTP on some browsers; fall back to
        // a download, which always works and is arguably the better artefact.
        const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = `incgame-${state.seed}.json`;
        link.click();
        URL.revokeObjectURL(url);
      }
    });

    document.getElementById('btn-import').addEventListener('click', async () => {
      const text = prompt('Paste a save:');
      if (!text) return;
      try {
        const data = await API.load(JSON.parse(text));
        localStorage.setItem(SAVE_KEY, text);
        apply(data);
        dialog.close();
        UI.toast('Save loaded', 'good');
      } catch (err) {
        UI.toast(`Import failed: ${err.message}`, 'bad');
      }
    });

    document.getElementById('btn-new').addEventListener('click', async () => {
      const raw = document.getElementById('menu-new-seed').value.trim();
      const seed = raw === '' ? null : Number(raw);
      if (seed !== null && !Number.isFinite(seed)) {
        UI.toast('Seed must be a number', 'bad');
        return;
      }
      if (!confirm('Generate a new world? The current run is discarded.')) return;
      const data = await guard(API.newGame(seed), 'Could not generate');
      if (!data) return;
      localStorage.removeItem(SAVE_KEY);
      state = null; // force a full re-theme
      apply(data);
      await save();
      dialog.close();
      UI.showTab('do');
      UI.toast('New world generated', 'good');
    });
  }

  function wireTabs() {
    document.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => UI.showTab(tab.dataset.tab));
    });
  }

  function wireLifecycle() {
    // Pause polling in the background; the server credits the gap on return, so
    // a backgrounded tab costs nothing and loses nothing.
    document.addEventListener('visibilitychange', () => {
      visible = document.visibilityState === 'visible';
      if (visible) {
        snapshot.at = performance.now();
        poll();
      } else {
        save();
      }
    });
    window.addEventListener('pagehide', save);

    // Keyboard play on desktop: 1-9 fire the visible actions in order.
    document.addEventListener('keydown', (event) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (document.activeElement && document.activeElement.tagName === 'INPUT') return;
      const index = Number(event.key) - 1;
      if (!Number.isInteger(index) || index < 0 || !state) return;
      const unlocked = state.actions.filter((a) => a.unlocked);
      if (unlocked[index]) {
        event.preventDefault();
        doAction(unlocked[index].id);
      }
    });
  }

  wireMenu();
  wireTabs();
  wireLifecycle();
  boot().catch((err) => {
    document.getElementById('boot').innerHTML =
      `<div class="boot-inner"><p>Could not reach the game server.</p><p style="color:#5b667a">${err.message}</p></div>`;
  });
})();
