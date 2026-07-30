/*
 * Rendering.
 *
 * The whole file is built around keyed reconciliation: every list keeps a
 * Map of id -> element, updates elements in place, and only creates or removes
 * nodes when the set of ids actually changes. Re-rendering with innerHTML at the
 * poll rate would be simpler and would also cancel an in-progress tap, drop
 * :active feedback, and reset the scroll position of the upgrade list several
 * times a second -- all of which read as an unresponsive game.
 *
 * Node identity is therefore load-bearing. `keyedList` is the only place that
 * adds or removes children of a list container.
 */

const UI = (() => {
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  /**
   * Reconcile `container`'s children against `items` by id.
   * `create(item)` builds a node; `update(node, item)` refreshes one in place.
   * Order is enforced, so newly unlocked content lands where it belongs.
   */
  function keyedList(container, items, create, update) {
    const existing = container._byId || (container._byId = new Map());
    const seen = new Set();

    items.forEach((item, index) => {
      seen.add(item.id);
      let node = existing.get(item.id);
      if (!node) {
        node = create(item);
        node.dataset.id = item.id;
        existing.set(item.id, node);
      }
      update(node, item);
      // Only touch the DOM when the position is actually wrong.
      if (container.children[index] !== node) {
        container.insertBefore(node, container.children[index] || null);
      }
    });

    for (const [id, node] of existing) {
      if (!seen.has(id)) {
        node.remove();
        existing.delete(id);
      }
    }
  }

  function chip(entry, short) {
    const node = el('span', 'chip' + (short ? ' is-short' : ''));
    node.style.setProperty('--res', entry.color);
    node.appendChild(el('i', 'dot'));
    node.appendChild(el('span', null, `${entry.display} ${entry.name}`));
    return node;
  }

  function bundleRow(container, entries, markShort) {
    container.textContent = '';
    entries.forEach((entry) => container.appendChild(chip(entry, markShort && !entry.have)));
  }

  function sectionHead(title, count) {
    const head = el('div', 'section-head');
    head.appendChild(el('h2', null, title));
    if (count !== undefined) head.appendChild(el('span', 'count', count));
    return head;
  }

  // ---------------------------------------------------------------- theme --

  function setTheme(theme) {
    const root = document.documentElement;
    root.style.setProperty('--accent', theme.accent);
    root.style.setProperty('--secondary', theme.secondary);
    root.style.setProperty('--hue', theme.hue);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', '#0b0e14');
  }

  // ------------------------------------------------------------ resources --

  function renderResources(state) {
    const container = document.getElementById('resources');
    const visible = state.resources.filter((r) => r.visible);
    keyedList(
      container,
      visible,
      (res) => {
        const node = el('div', 'res');
        node.style.setProperty('--res', res.color);
        node.appendChild(el('div', 'res-name', res.name));
        node.appendChild(el('div', 'res-amount', res.display));
        node.appendChild(el('div', 'res-rate'));
        const bar = el('div', 'res-bar');
        bar.appendChild(el('i'));
        node.appendChild(bar);
        node.title = res.description;
        return node;
      },
      (node, res) => {
        node.querySelector('.res-amount').textContent = res.display;
        const rate = node.querySelector('.res-rate');
        rate.textContent = res.cap_display
          ? `${fmtRate(res.rate)} · max ${res.cap_display}`
          : fmtRate(res.rate);
        rate.classList.toggle('is-negative', res.rate < -1e-9);
        const bar = node.querySelector('.res-bar');
        bar.hidden = res.cap === null;
        bar.firstElementChild.style.width = `${(res.fill * 100).toFixed(1)}%`;
        node.classList.toggle('is-full', res.cap !== null && res.fill >= 0.999);
      }
    );
  }

  /**
   * Update only the amount text and cap bars, from locally interpolated values.
   * Called on every animation frame between polls, so it must not read layout or
   * allocate.
   */
  function tickResources(amounts, caps) {
    const container = document.getElementById('resources');
    const byId = container._byId;
    if (!byId) return;
    for (const [id, node] of byId) {
      const amount = amounts[id];
      if (amount === undefined) continue;
      node.querySelector('.res-amount').textContent = fmtNumber(amount);
      const cap = caps[id];
      if (cap) {
        const fill = Math.min(1, amount / cap);
        node.querySelector('.res-bar').firstElementChild.style.width = `${(fill * 100).toFixed(1)}%`;
        node.classList.toggle('is-full', fill >= 0.999);
      }
    }
  }

  // -------------------------------------------------------------- actions --

  function renderActions(state, onAction) {
    const container = document.getElementById('actions');
    keyedList(
      container,
      state.actions,
      (action) => {
        const node = el('button', 'action');
        node.type = 'button';
        node.appendChild(el('div', 'action-name'));
        node.appendChild(el('div', 'action-desc'));
        node.appendChild(el('div', 'action-flow'));
        node.appendChild(el('div', 'lock-gate'));
        const bar = el('div', 'lock-bar');
        bar.appendChild(el('i'));
        node.appendChild(bar);
        node.appendChild(el('div', 'action-cool'));
        node.addEventListener('click', () => {
          if (!node.disabled) onAction(node.dataset.id);
        });
        return node;
      },
      (node, action) => {
        node.querySelector('.action-name').textContent = action.name;
        node.querySelector('.action-desc').textContent = action.description;

        const flow = node.querySelector('.action-flow');
        flow.textContent = '';
        if (action.unlocked) {
          if (action.cost.length) {
            action.cost.forEach((c) => flow.appendChild(chip(c, !c.have)));
            flow.appendChild(el('span', 'action-arrow', '→'));
          }
          action.output.forEach((o) => flow.appendChild(chip(o)));
        }

        const gate = node.querySelector('.lock-gate');
        const bar = node.querySelector('.lock-bar');
        gate.hidden = action.unlocked;
        bar.hidden = action.unlocked;
        if (!action.unlocked) {
          gate.textContent = action.gate;
          bar.firstElementChild.style.width = `${(action.progress * 100).toFixed(0)}%`;
        }

        node.classList.toggle('locked', !action.unlocked);
        node.classList.toggle('is-primary', action.unlocked && action.kind === 'click');
        node.disabled = !action.unlocked || !action.affordable;
        // Cooldown width is driven per-frame by tickActions; seed it here so a
        // freshly created node is not briefly full.
        node._cooldown = action.cooldown;
      }
    );
  }

  /** Per-frame cooldown sweep. `readyAt` maps action id -> client timestamp. */
  function tickActions(readyAt, now, affordable) {
    const container = document.getElementById('actions');
    const byId = container._byId;
    if (!byId) return;
    for (const [id, node] of byId) {
      const sweep = node.querySelector('.action-cool');
      const ready = readyAt[id] || 0;
      const cooldown = node._cooldown || 0;
      if (cooldown > 0 && ready > now) {
        const remaining = (ready - now) / cooldown;
        sweep.style.width = `${Math.min(100, remaining * 100).toFixed(1)}%`;
        node.disabled = true;
      } else {
        sweep.style.width = '0%';
        if (affordable[id] !== undefined && !node.classList.contains('locked')) {
          node.disabled = !affordable[id];
        }
      }
    }
  }

  // ----------------------------------------------------------- generators --

  function renderGenerators(state, onBuy) {
    const container = document.getElementById('generators');
    if (!state.generators.length) {
      container.textContent = '';
      container._byId = new Map();
      container.appendChild(
        el('div', 'empty', 'Nothing to build yet. Keep working — the first one will show up here.')
      );
      return;
    }
    keyedList(
      container,
      state.generators,
      (gen) => {
        const node = el('div', 'card');
        const top = el('div', 'card-top');
        const left = el('div');
        left.appendChild(el('div', 'card-name'));
        left.appendChild(el('div', 'card-sub'));
        top.appendChild(left);
        top.appendChild(el('div', 'card-owned'));
        node.appendChild(top);
        node.appendChild(el('div', 'card-meta'));
        node.appendChild(el('div', 'throttle'));
        node.appendChild(el('div', 'lock-gate'));
        const bar = el('div', 'lock-bar');
        bar.appendChild(el('i'));
        node.appendChild(bar);

        const buy = el('div', 'card-buy');
        const one = el('button', 'btn btn-primary');
        one.type = 'button';
        const max = el('button', 'btn btn-max', 'Max');
        max.type = 'button';
        one.addEventListener('click', () => onBuy(node.dataset.id, 1));
        max.addEventListener('click', () => onBuy(node.dataset.id, 'max'));
        buy.appendChild(one);
        buy.appendChild(max);
        node.appendChild(buy);
        return node;
      },
      (node, gen) => {
        node.querySelector('.card-name').textContent = gen.name;
        node.querySelector('.card-sub').textContent = gen.description;
        const owned = node.querySelector('.card-owned');
        owned.textContent = `×${gen.owned}`;
        owned.hidden = gen.owned === 0;

        const meta = node.querySelector('.card-meta');
        meta.textContent = '';
        meta.appendChild(
          el('span', 'chip', `${fmtNumber(gen.rate_each)}/s ${gen.resource_name} each`)
        );
        if (gen.owned > 0) {
          meta.appendChild(el('span', 'chip', `${fmtRate(gen.rate_total)} total`));
        }
        gen.upkeep.forEach((u) => {
          const node2 = chip(u, false);
          node2.lastChild.textContent = `eats ${u.display}/s ${u.name}`;
          meta.appendChild(node2);
        });

        const throttle = node.querySelector('.throttle');
        throttle.hidden = !gen.throttled;
        if (gen.throttled) {
          throttle.textContent = `Starved — running at ${(gen.efficiency * 100).toFixed(0)}%. Feed it more ${gen.upkeep.map((u) => u.name).join(', ')}.`;
        }
        node.classList.toggle('is-throttled', gen.throttled);

        const gate = node.querySelector('.lock-gate');
        const bar = node.querySelector('.lock-bar');
        const buy = node.querySelector('.card-buy');
        gate.hidden = gen.unlocked;
        bar.hidden = gen.unlocked;
        buy.hidden = !gen.unlocked;
        if (!gen.unlocked) {
          gate.textContent = gen.gate;
          bar.firstElementChild.style.width = `${(gen.progress * 100).toFixed(0)}%`;
          node.classList.add('locked');
          return;
        }
        node.classList.remove('locked');

        const [one, max] = buy.children;
        one.textContent = `Build · ${gen.cost_display} ${gen.cost_resource_name}`;
        one.disabled = !gen.affordable;
        max.textContent = gen.max_affordable > 1 ? `Max ×${gen.max_affordable}` : 'Max';
        max.disabled = gen.max_affordable < 1;
      }
    );
  }

  // ------------------------------------------------------------- upgrades --

  function renderUpgrades(state, onBuy) {
    const container = document.getElementById('upgrades');
    if (!state.upgrades.length) {
      container.textContent = '';
      container._byId = new Map();
      container.appendChild(el('div', 'empty', 'No research available yet.'));
      return;
    }
    keyedList(
      container,
      state.upgrades,
      (upg) => {
        const node = el('div', 'card');
        const top = el('div', 'card-top');
        const left = el('div');
        left.appendChild(el('div', 'family'));
        left.appendChild(el('div', 'card-name'));
        left.appendChild(el('div', 'card-sub'));
        top.appendChild(left);
        node.appendChild(top);
        node.appendChild(el('div', 'effect'));
        node.appendChild(el('div', 'card-meta'));
        node.appendChild(el('div', 'lock-gate'));
        const bar = el('div', 'lock-bar');
        bar.appendChild(el('i'));
        node.appendChild(bar);
        const buy = el('div', 'card-buy');
        const button = el('button', 'btn btn-primary');
        button.type = 'button';
        button.addEventListener('click', () => onBuy(node.dataset.id));
        buy.appendChild(button);
        node.appendChild(buy);
        return node;
      },
      (node, upg) => {
        node.querySelector('.family').textContent = `${upg.family} · tier ${upg.tier + 1}`;
        node.querySelector('.card-name').textContent = upg.name;
        node.querySelector('.card-sub').textContent = upg.description;
        node.querySelector('.effect').textContent = upg.effect;

        const meta = node.querySelector('.card-meta');
        bundleRow(meta, upg.cost, true);

        const gate = node.querySelector('.lock-gate');
        const bar = node.querySelector('.lock-bar');
        const buy = node.querySelector('.card-buy');

        node.classList.toggle('is-owned', upg.owned);
        if (upg.owned) {
          gate.hidden = false;
          gate.textContent = 'Researched';
          bar.hidden = true;
          buy.hidden = true;
          node.classList.remove('locked');
          return;
        }

        const missing = upg.requires.filter((r) => !r.owned);
        if (!upg.unlocked) {
          gate.hidden = false;
          gate.textContent = missing.length
            ? `Requires ${missing.map((r) => r.name).join(', ')}`
            : upg.gate;
          bar.hidden = false;
          bar.firstElementChild.style.width = `${(upg.progress * 100).toFixed(0)}%`;
          buy.hidden = true;
          node.classList.add('locked');
          return;
        }

        gate.hidden = true;
        bar.hidden = true;
        buy.hidden = false;
        node.classList.remove('locked');
        const button = buy.firstElementChild;
        button.textContent = 'Research';
        button.disabled = !upg.available;
      }
    );
  }

  // ------------------------------------------------------------ mechanics --

  function renderMechanics(state) {
    const container = document.getElementById('mechanics');
    if (!container._head) {
      container._head = true;
      container.appendChild(sectionHead("This run's rules"));
    }
    let list = container.querySelector('.mech-list');
    if (!list) {
      list = el('div', 'mechanics mech-list');
      container.appendChild(list);
    }
    keyedList(
      list,
      state.mechanics,
      (mech) => {
        const node = el('div', 'mech');
        node.appendChild(el('div', 'mech-kind'));
        node.appendChild(el('div', 'mech-name'));
        node.appendChild(el('div', 'mech-desc'));
        node.appendChild(el('div', 'mech-live'));
        return node;
      },
      (node, mech) => {
        node.querySelector('.mech-kind').textContent = mech.kind;
        node.querySelector('.mech-name').textContent = mech.name;
        node.querySelector('.mech-desc').textContent = mech.description;
        const live = node.querySelector('.mech-live');
        live.hidden = !mech.live;
        live.textContent = mech.live || '';
      }
    );
  }

  // ------------------------------------------------------------- prestige --

  function renderPrestige(state, onPrestige, onBuy) {
    const p = state.prestige;
    const head = document.getElementById('prestige-head');
    if (!head._built) {
      head._built = true;
      head.appendChild(el('h2'));
      head.appendChild(el('p', 'hint'));
      const nums = el('div', 'prestige-nums');
      ['held', 'points', 'ascensions'].forEach((key) => {
        const box = el('div', 'prestige-num');
        box.dataset.key = key;
        box.appendChild(el('div', 'k'));
        box.appendChild(el('div', 'v'));
        nums.appendChild(box);
      });
      head.appendChild(nums);
      const button = el('button', 'btn btn-danger btn-wide');
      button.type = 'button';
      button.addEventListener('click', onPrestige);
      head.appendChild(button);
    }

    head.querySelector('h2').textContent = `Ascend for ${p.name}`;
    head.querySelector('.hint').textContent =
      'Resetting clears this run — resources, buildings, research. ' +
      `You keep ${p.name} and everything bought with it.`;

    const values = { held: p.currency_display, points: p.points_display, ascensions: p.ascensions };
    const labels = { held: p.name + ' held', points: 'Ascend for', ascensions: 'Ascensions' };
    head.querySelectorAll('.prestige-num').forEach((box) => {
      box.querySelector('.k').textContent = labels[box.dataset.key];
      box.querySelector('.v').textContent = values[box.dataset.key];
    });

    const button = head.querySelector('button');
    button.textContent = p.can_prestige ? `Ascend — gain ${p.points_display} ${p.name}` : 'Not enough progress yet';
    button.disabled = !p.can_prestige;

    keyedList(
      document.getElementById('prestige-upgrades'),
      p.upgrades,
      (upg) => {
        const node = el('div', 'card');
        const top = el('div', 'card-top');
        const left = el('div');
        left.appendChild(el('div', 'card-name'));
        left.appendChild(el('div', 'card-sub'));
        top.appendChild(left);
        top.appendChild(el('div', 'card-owned'));
        node.appendChild(top);
        node.appendChild(el('div', 'effect'));
        const buy = el('div', 'card-buy');
        const button = el('button', 'btn btn-primary');
        button.type = 'button';
        button.addEventListener('click', () => onBuy(node.dataset.id));
        buy.appendChild(button);
        node.appendChild(buy);
        return node;
      },
      (node, upg) => {
        node.querySelector('.card-name').textContent = upg.name;
        node.querySelector('.card-sub').textContent = upg.description;
        node.querySelector('.effect').textContent = upg.effect;
        const owned = node.querySelector('.card-owned');
        owned.textContent = upg.max_level > 1 ? `${upg.level}/${upg.max_level}` : upg.level ? '✓' : '—';
        const button = node.querySelector('button');
        button.textContent = upg.maxed ? 'Maxed' : `Buy · ${upg.cost_display}`;
        button.disabled = !upg.affordable;
        node.classList.toggle('is-owned', upg.maxed);
      }
    );
  }

  // ---------------------------------------------------------------- misc ---

  function renderStats(state) {
    const container = document.getElementById('menu-stats');
    const rows = [
      ['Playtime', state.stats.playtime_display],
      ['Actions', state.stats.actions],
      ['Research', `${state.stats.upgrades_owned}`],
      ['Buildings', `${state.stats.generators_owned}`],
      ['Ascensions', `${state.stats.ascensions}`],
      ['Best ascend', fmtNumber(state.stats.best_points)],
    ];
    container.textContent = '';
    rows.forEach(([key, value]) => {
      const row = el('div');
      row.appendChild(el('span', null, key));
      row.appendChild(el('b', null, String(value)));
      container.appendChild(row);
    });
  }

  function setBadges(state) {
    const badges = {
      build: state.generators.some((g) => g.unlocked && g.affordable),
      research: state.upgrades.some((u) => u.available),
      ascend: state.prestige.can_prestige || state.prestige.upgrades.some((u) => u.affordable),
    };
    document.querySelectorAll('.tab').forEach((tab) => {
      const badge = tab.querySelector('.badge');
      if (badge) badge.hidden = !badges[tab.dataset.tab];
    });
  }

  let toastCount = 0;
  function toast(text, kind) {
    const container = document.getElementById('toasts');
    // Cap the stack: a fast clicker can outrun the 1.4s removal timer, and an
    // unbounded column of toasts covers the buttons they are clicking.
    while (container.children.length >= 4) container.firstElementChild.remove();
    const node = el('div', 'toast' + (kind ? ` is-${kind}` : ''), text);
    node.dataset.n = String(++toastCount);
    container.appendChild(node);
    setTimeout(() => node.remove(), 1450);
  }

  function showTab(name) {
    document.querySelectorAll('.panel').forEach((panel) => {
      panel.hidden = panel.dataset.tab !== name;
    });
    document.querySelectorAll('.tab').forEach((tab) => {
      tab.classList.toggle('is-active', tab.dataset.tab === name);
    });
  }

  return {
    setTheme,
    renderResources,
    tickResources,
    renderActions,
    tickActions,
    renderGenerators,
    renderUpgrades,
    renderMechanics,
    renderPrestige,
    renderStats,
    setBadges,
    toast,
    showTab,
  };
})();
