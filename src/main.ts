import { getGameEngine } from './game/engine';
import { PLANETS } from './game/planets';
import { REAPER_CLASSES, getReaperTierInfo, getReaperPower, type Reaper } from './game/reapers';
import { UPGRADES, getUpgradeCost } from './game/upgrades';
import {
  EQUIP_SLOTS,
  GRID_COLS,
  RARITY_COLOR,
  getItemDef,
  itemPower,
  packUsed,
  type PackItem,
} from './game/backpack';
import { getNode, getPlanetNodes, type WorldNode } from './game/locations';
import { formatNumber, formatTime } from './utils/format';
import { floatText, shake, spawnLootToast, spawnRipple, triggerHaptic } from './ui/fx';

const engine = getGameEngine();
let currentTab = 'explore';
let selectedReaperId: string | null = null;
let selectedItemUid: string | null = null;
let dragging = false;
let rummageTimer: number | null = null;
let rummageStarted = 0;

function init(): void {
  setTimeout(() => {
    document.getElementById('loading-screen')?.classList.add('hidden');
    render();
    engine.start();

    engine.subscribe((kind) => {
      if (kind === 'tick') {
        updateHud();
        return;
      }
      if (kind === 'travel') {
        updateTraveler();
        updateHud();
        return;
      }
      if (kind === 'loot') {
        updateHud();
        updatePackBadge();
        const drop = engine.lastLootDrop;
        if (drop) {
          const def = getItemDef(drop.defId);
          spawnLootToast(def.icon, `${def.name} T${drop.tier}`);
          triggerHaptic('medium');
        }
        if (currentTab === 'pack' && !dragging) render();
        return;
      }
      if (!dragging) render();
    });

    setInterval(() => engine.save(), 30000);
  }, 1200);
}

function render(): void {
  const app = document.getElementById('app');
  if (!app) return;
  const planet = engine.getCurrentPlanet();
  const idleRate = engine.getIdleRate();
  const rank = engine.simulatedWorld.getPlayerRank();
  const onlineCount = engine.simulatedWorld.players.filter((p) => p.isOnline).length;
  const event = engine.simulatedWorld.globalEvent;

  app.innerHTML = `
    <div class="game-container">
      ${renderTopBar(idleRate, rank, onlineCount)}
      ${event ? renderEventBanner(event) : ''}
      <div class="main-content">
        <div class="tab-panel ${currentTab === 'explore' ? 'active' : ''}">${currentTab === 'explore' ? renderExploreTab(planet.ambientColor) : ''}</div>
        <div class="tab-panel ${currentTab === 'pack' ? 'active' : ''}">${currentTab === 'pack' ? renderPackTab() : ''}</div>
        <div class="tab-panel ${currentTab === 'reapers' ? 'active' : ''}">${currentTab === 'reapers' ? renderReapersTab() : ''}</div>
        <div class="tab-panel ${currentTab === 'galaxy' ? 'active' : ''}">${currentTab === 'galaxy' ? renderGalaxyTab() : ''}</div>
        <div class="tab-panel ${currentTab === 'realm' ? 'active' : ''}">${currentTab === 'realm' ? renderWorldTab() : ''}</div>
        <div class="tab-panel ${currentTab === 'void' ? 'active' : ''}">${currentTab === 'void' ? renderVoidTab() : ''}</div>
      </div>
      ${renderBottomNav()}
      <div id="fx-layer"></div>
    </div>
  `;
  bindEvents();
}

function renderTopBar(idleRate: number, rank: number, onlineCount: number): string {
  const used = packUsed(engine.packItems);
  const cap = engine.getPackCapacity();
  return `
    <div class="top-bar">
      <div class="soul-counter">
        <span class="soul-icon">💀</span>
        <div>
          <div class="soul-amount" id="soul-amount">${formatNumber(engine.souls)}</div>
          <div class="soul-rate" id="soul-rate">+${formatNumber(idleRate)}/s</div>
        </div>
      </div>
      <div class="top-bar-right">
        <button class="pack-pill" id="pack-pill" type="button">
          🎒 <span id="pack-count">${used}/${cap}</span>
        </button>
        <div class="player-rank" id="player-rank">Rank #${rank}</div>
        <div class="online-badge">
          <span class="online-dot"></span>
          ${onlineCount + 1} online
        </div>
      </div>
    </div>
  `;
}

function renderEventBanner(event: { name: string; description: string; endsAt: number }): string {
  const remaining = Math.max(0, (event.endsAt - Date.now()) / 1000);
  return `
    <div class="event-banner">
      🌟 ${event.name}: ${event.description} (<span id="event-timer">${formatTime(remaining)}</span>)
    </div>
  `;
}

function renderExploreTab(ambient: string): string {
  const planet = engine.getCurrentPlanet();
  const node = engine.getCurrentNode();
  const nodes = getPlanetNodes(planet.id);
  const wanderers = engine.simulatedWorld.players
    .filter((p) => p.isOnline && p.planet === planet.name)
    .slice(0, 4);

  return `
    <div class="explore-view">
      <div class="planet-header compact">
        <div class="planet-name">${planet.icon} ${planet.name}</div>
        <div class="planet-flavor">"${node.flavor}"</div>
      </div>
      <div class="world-map" id="world-map" style="--ambient:${ambient}">
        ${nodes.map((n) => renderMapNode(n)).join('')}
        ${wanderers
          .map(
            (w, i) =>
              `<div class="wanderer" style="left:${18 + i * 18}%;top:${20 + (i % 3) * 22}%" title="${w.name}">${w.avatar}</div>`
          )
          .join('')}
        <div class="player-token" id="player-token" style="left:${engine.playerX}%;top:${engine.playerY}%">🎮</div>
      </div>
      <div class="node-panel" id="node-panel">
        <div class="node-panel-head">
          <div class="node-panel-icon">${node.icon}</div>
          <div>
            <div class="node-panel-name">${node.name}</div>
            <div class="node-panel-kind">${node.kind} · ${node.soulMult.toFixed(2)}x souls</div>
          </div>
        </div>
        <div class="node-actions">
          <button class="harvest-orb" id="harvest-orb" type="button">${node.icon}</button>
          <button class="rummage-btn" id="rummage-btn" type="button">
            <span class="rummage-ring" id="rummage-ring"></span>
            <span>Hold to rummage</span>
          </button>
        </div>
      </div>
      <div class="harvest-actions">
        <button class="btn btn-primary" id="btn-summon" type="button">
          <span class="btn-icon">👻</span>
          Summon · ${formatNumber(engine.getReaperSummonCost())}
        </button>
        <button class="btn" id="btn-auto-merge" type="button">
          <span class="btn-icon">⚗️</span>
          Auto Merge
        </button>
      </div>
    </div>
  `;
}

function renderMapNode(n: WorldNode): string {
  const discovered = engine.discoveredNodeIds.includes(n.id);
  const here = engine.currentNodeId === n.id;
  const locked = !discovered && engine.souls < n.unlockSouls;
  return `
    <button class="map-node ${discovered ? 'known' : 'fog'} ${here ? 'here' : ''} ${locked ? 'locked' : ''}"
      data-node="${n.id}" style="left:${n.x}%;top:${n.y}%" type="button">
      <span>${discovered ? n.icon : '❔'}</span>
      <em>${discovered ? n.name : `Scout ${formatNumber(n.unlockSouls)}`}</em>
    </button>
  `;
}

function renderPackTab(): string {
  const used = packUsed(engine.packItems);
  const cap = engine.getPackCapacity();
  const fullness = used / cap;
  const selected = engine.packItems.find((i) => i.uid === selectedItemUid);
  const bonuses = engine.getEquippedBonuses();

  return `
    <div class="pack-view ${fullness > 0.85 ? 'heavy' : ''}">
      <div class="section-header">🎒 Soulpack · ${used}/${cap}</div>
      <div class="equip-row">
        ${Array.from({ length: EQUIP_SLOTS }, (_, i) => {
          const item = engine.packItems.find((it) => it.slot === -(i + 1));
          return renderEquipSlot(i, item);
        }).join('')}
      </div>
      <div class="pack-bonus">Equipped: +${Math.round(bonuses.tap * 100)}% tap · +${Math.round(bonuses.idle * 100)}% idle · +${Math.round(bonuses.loot * 100)}% loot</div>
      ${selected ? renderItemSheet(selected) : '<div class="pack-hint">Tap a relic to crush or equip. Drag to merge matching tiers.</div>'}
      <div class="pack-grid ${fullness > 0.85 ? 'strained' : ''}" id="pack-grid" style="grid-template-columns:repeat(${GRID_COLS},1fr)">
        ${Array.from({ length: cap }, (_, slot) => {
          const item = engine.packItems.find((it) => it.slot === slot);
          return renderPackSlot(slot, item);
        }).join('')}
      </div>
      <div class="harvest-actions">
        <button class="btn" id="btn-crush-shards" type="button">Crush all shards</button>
      </div>
    </div>
  `;
}

function renderEquipSlot(index: number, item?: PackItem): string {
  if (!item) {
    return `<div class="equip-slot empty" data-equip="${index}">+</div>`;
  }
  const def = getItemDef(item.defId);
  return `
    <button class="equip-slot filled" data-unequip="${item.uid}" type="button"
      style="border-color:${RARITY_COLOR[def.rarity]}">
      <span>${def.icon}</span>
      <em>T${item.tier}</em>
    </button>
  `;
}

function renderPackSlot(slot: number, item?: PackItem): string {
  if (!item) {
    return `<div class="pack-slot empty" data-slot="${slot}"></div>`;
  }
  const def = getItemDef(item.defId);
  const selected = selectedItemUid === item.uid ? 'selected' : '';
  return `
    <button class="pack-slot filled ${selected}" data-slot="${slot}" data-item="${item.uid}" type="button"
      style="border-color:${RARITY_COLOR[def.rarity]};box-shadow:0 0 10px ${RARITY_COLOR[def.rarity]}55">
      <span class="pack-icon">${def.icon}</span>
      <em>T${item.tier}</em>
    </button>
  `;
}

function renderItemSheet(item: PackItem): string {
  const def = getItemDef(item.defId);
  const power = itemPower(item);
  return `
    <div class="item-sheet">
      <div class="item-sheet-title">${def.icon} ${def.name} · T${item.tier}</div>
      <div class="item-sheet-meta" style="color:${RARITY_COLOR[def.rarity]}">${def.rarity} ${def.kind}</div>
      <div class="item-sheet-stats">Crush ${formatNumber(power.crush * Math.max(1, engine.getCurrentPlanet().baseSoulValue * 0.35))} · Tap +${Math.round(power.tap * 100)}% · Idle +${Math.round(power.idle * 100)}%</div>
      <div class="harvest-actions">
        <button class="btn btn-primary" id="btn-equip" data-uid="${item.uid}" type="button">Equip</button>
        <button class="btn" id="btn-crush" data-uid="${item.uid}" type="button">Crush</button>
      </div>
    </div>
  `;
}

function renderReapersTab(): string {
  const reapers = engine.reapers;
  if (reapers.length === 0) {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">👻</div>
        <div class="empty-state-text">No reapers yet. Summon one from Explore — they idle-fill your backpack.</div>
      </div>
    `;
  }

  return `
    <div class="section-header">👻 Reapers (${reapers.length}) · Tap two to merge</div>
    <div class="reaper-grid">
      ${reapers.map((r) => renderReaperCard(r)).join('')}
    </div>
    <div class="section-header">📜 Class</div>
    <div class="class-grid">
      ${Object.values(REAPER_CLASSES)
        .map(
          (c) => `
        <div class="class-card ${engine.playerClass === c.id ? 'selected' : ''}" data-class="${c.id}">
          <div class="class-card-icon">${c.icon}</div>
          <div class="class-card-name">${c.name}</div>
          <div class="class-card-desc">${c.description}</div>
        </div>
      `
        )
        .join('')}
    </div>
  `;
}

function renderReaperCard(r: Reaper): string {
  const tier = getReaperTierInfo(r.tier);
  const power = getReaperPower(r);
  const cls = REAPER_CLASSES[r.classId];
  return `
    <div class="reaper-card ${selectedReaperId === r.id ? 'selected' : ''}" data-reaper="${r.id}">
      <div class="reaper-card-icon">${tier.icon}</div>
      <div class="reaper-card-name">${tier.name}</div>
      <div class="reaper-card-tier">Tier ${r.tier} · ${cls.icon}</div>
      <div class="reaper-card-power">${formatNumber(power)}/s</div>
    </div>
  `;
}

function renderGalaxyTab(): string {
  return `
    <div class="section-header">🌌 Galaxy</div>
    <div class="galaxy-map">
      ${PLANETS.map((p, i) => {
        const unlocked = engine.unlockedPlanetIds.includes(p.id);
        const isActive = engine.currentPlanetId === p.id;
        const angle = (i / PLANETS.length) * Math.PI * 2 - Math.PI / 2;
        const radius = 34 + (i % 2) * 8;
        const x = 50 + Math.cos(angle) * radius;
        const y = 50 + Math.sin(angle) * 38;
        return `
          <button class="galaxy-planet ${unlocked ? '' : 'locked'} ${isActive ? 'active' : ''}"
            data-planet="${p.id}" data-unlocked="${unlocked}" type="button"
            style="left:${x}%;top:${y}%">
            <span>${unlocked ? p.icon : '🌑'}</span>
            <em>${unlocked ? p.name : formatNumber(p.unlockCost)}</em>
          </button>
        `;
      }).join('')}
    </div>
    <div class="section-header">Sites on this world</div>
    ${getPlanetNodes(engine.currentPlanetId)
      .map((n) => {
        const known = engine.discoveredNodeIds.includes(n.id);
        return `
          <div class="planet-card ${n.id === engine.currentNodeId ? 'active' : ''}">
            <div class="planet-card-icon">${known ? n.icon : '❔'}</div>
            <div class="planet-card-info">
              <div class="planet-card-name">${known ? n.name : 'Unscouted site'}</div>
              <div class="planet-card-soul">${n.kind} · ${n.soulMult}x · loot ${Math.round(n.lootChance * 100)}%</div>
            </div>
          </div>
        `;
      })
      .join('')}
  `;
}

function renderWorldTab(): string {
  const leaderboard = engine.simulatedWorld.getLeaderboard();
  const chat = engine.simulatedWorld.chatMessages;

  return `
    <div class="chat-container">
      <div class="section-header">🏆 Leaderboard</div>
      ${leaderboard
        .slice(0, 10)
        .map(
          (p, i) => `
        <div class="leaderboard-item">
          <div class="lb-rank ${i < 3 ? 'top3' : ''}">${i + 1}</div>
          <div class="lb-avatar">${p.avatar}</div>
          <div class="lb-info">
            <div class="lb-name">${p.name}</div>
            <div class="lb-guild">${p.guild} · ${p.planet}</div>
          </div>
          <div class="lb-souls">${formatNumber(p.souls)}</div>
          <div class="${p.isOnline ? 'lb-online' : 'lb-offline'}"></div>
        </div>
      `
        )
        .join('')}
      <div class="leaderboard-item is-player">
        <div class="lb-rank">${engine.simulatedWorld.getPlayerRank()}</div>
        <div class="lb-avatar">🎮</div>
        <div class="lb-info">
          <div class="lb-name">You</div>
          <div class="lb-guild">${REAPER_CLASSES[engine.playerClass].name}</div>
        </div>
        <div class="lb-souls">${formatNumber(engine.souls)}</div>
        <div class="lb-online"></div>
      </div>
      <div class="section-header">💬 Global Chat</div>
      <div class="chat-messages" id="chat-messages">
        ${chat
          .map(
            (m) => `
          <div class="chat-msg ${m.isSystem ? 'system' : ''}">
            ${m.isSystem ? m.message : `<span class="chat-sender">${m.sender}:</span> ${m.message}`}
          </div>
        `
          )
          .join('')}
      </div>
      <div class="chat-input-area">
        <input class="chat-input" id="chat-input" placeholder="Say something..." maxlength="100" />
        <button class="btn btn-primary" id="btn-send-chat" style="flex:0;padding:8px 16px" type="button">Send</button>
      </div>
    </div>
  `;
}

function renderVoidTab(): string {
  const canPrestige = engine.canPrestige();
  const reward = engine.getPrestigeReward();

  return `
    <div class="section-header">🌀 Void Ascension</div>
    <div class="prestige-card">
      <div class="prestige-title">Ascend to the Void</div>
      <div class="prestige-desc">Reset progress for permanent harvest power. Backpack relics reset; the Void remembers you.</div>
      <div>Current Prestige: <strong>${engine.prestigeLevel}</strong> (${engine.prestigeSouls} souls)</div>
      <div class="prestige-reward">+${reward} Prestige Souls</div>
      <button class="btn btn-gold" id="btn-prestige" ${canPrestige ? '' : 'disabled'} type="button">
        ${canPrestige ? '🌀 ASCEND' : `Need ${formatNumber(1_000_000)} total souls`}
      </button>
    </div>
    <div class="section-header">⚡ Upgrades</div>
    ${UPGRADES.map((u) => {
      const level = engine.upgradeLevels[u.id] ?? 0;
      const maxed = level >= u.maxLevel;
      const cost = getUpgradeCost(u, level);
      return `
        <div class="upgrade-item ${maxed ? 'maxed' : ''}" data-upgrade="${u.id}">
          <div class="upgrade-icon">${u.icon}</div>
          <div class="upgrade-info">
            <div class="upgrade-name">${u.name}</div>
            <div class="upgrade-desc">${u.description}</div>
            <div class="upgrade-level">Lv ${level}/${u.maxLevel}</div>
          </div>
          <div class="upgrade-cost">${maxed ? 'MAX' : formatNumber(cost)}</div>
        </div>
      `;
    }).join('')}
    <div class="section-header">📊 Stats</div>
    <div class="card">
      <div style="font-size:0.8rem;line-height:1.8">
        <div>💀 Total Souls: <strong>${formatNumber(engine.totalSoulsEarned)}</strong></div>
        <div>👆 Harvests: <strong>${formatNumber(engine.tapCount)}</strong></div>
        <div>🎒 Rummages: <strong>${engine.rummageCount}</strong></div>
        <div>🗺️ Sites found: <strong>${engine.discoveredNodeIds.length}</strong></div>
        <div>⚡ Tap Power: <strong>${formatNumber(engine.getTapPower())}</strong></div>
        <div>🔄 Idle Rate: <strong>${formatNumber(engine.getIdleRate())}/s</strong></div>
      </div>
    </div>
    <div style="padding:12px;text-align:center">
      <button class="btn" id="btn-reset" style="color:var(--accent-red);border-color:var(--accent-red)" type="button">Reset Save</button>
    </div>
  `;
}

function renderBottomNav(): string {
  const used = packUsed(engine.packItems);
  const cap = engine.getPackCapacity();
  const tabs = [
    { id: 'explore', icon: '🗺️', label: 'Explore' },
    { id: 'pack', icon: used >= cap ? '🎒!' : '🎒', label: 'Pack' },
    { id: 'reapers', icon: '👻', label: 'Reapers' },
    { id: 'galaxy', icon: '🌌', label: 'Galaxy' },
    { id: 'realm', icon: '🌐', label: 'Realm' },
    { id: 'void', icon: '🌀', label: 'Void' },
  ];
  return `
    <div class="bottom-nav">
      ${tabs
        .map(
          (t) => `
        <button class="nav-tab ${currentTab === t.id ? 'active' : ''}" data-tab="${t.id}" type="button">
          <span class="nav-tab-icon">${t.icon}</span>
          ${t.label}
        </button>
      `
        )
        .join('')}
    </div>
  `;
}

function updateHud(): void {
  const amount = document.getElementById('soul-amount');
  const rate = document.getElementById('soul-rate');
  const rank = document.getElementById('player-rank');
  const timer = document.getElementById('event-timer');
  if (amount) amount.textContent = formatNumber(engine.souls);
  if (rate) rate.textContent = `+${formatNumber(engine.getIdleRate())}/s`;
  if (rank) rank.textContent = `Rank #${engine.simulatedWorld.getPlayerRank()}`;
  if (timer && engine.simulatedWorld.globalEvent) {
    const remaining = Math.max(0, (engine.simulatedWorld.globalEvent.endsAt - Date.now()) / 1000);
    timer.textContent = formatTime(remaining);
  }
}

function updatePackBadge(): void {
  const el = document.getElementById('pack-count');
  if (el) el.textContent = `${packUsed(engine.packItems)}/${engine.getPackCapacity()}`;
}

function updateTraveler(): void {
  const token = document.getElementById('player-token');
  if (!token) return;
  token.style.left = `${engine.playerX}%`;
  token.style.top = `${engine.playerY}%`;
  token.classList.toggle('walking', !!engine.travel);
}

function bindEvents(): void {
  document.querySelectorAll('.nav-tab').forEach((el) => {
    el.addEventListener('click', () => {
      currentTab = (el as HTMLElement).dataset.tab!;
      selectedItemUid = null;
      render();
    });
  });

  document.getElementById('pack-pill')?.addEventListener('click', () => {
    currentTab = 'pack';
    render();
  });

  bindExplore();
  bindPack();
  bindRest();
}

function bindExplore(): void {
  const orb = document.getElementById('harvest-orb');
  if (orb) {
    orb.addEventListener('pointerdown', (e) => {
      const ev = e as PointerEvent;
      const rect = orb.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const y = ev.clientY - rect.top;
      orb.classList.add('pressed');
      const result = engine.tap(x, y);
      floatText(orb, x, y, `+${formatNumber(result.souls)}${result.isCritical ? ' CRIT!' : ''}`, result.isCritical);
      spawnRipple(orb, x, y);
      shake(document.getElementById('node-panel'), result.isCritical ? 280 : 120);
      triggerHaptic(result.isCritical ? 'heavy' : 'light');
    });
    orb.addEventListener('pointerup', () => orb.classList.remove('pressed'));
    orb.addEventListener('pointerleave', () => orb.classList.remove('pressed'));
  }

  document.querySelectorAll('.map-node').forEach((el) => {
    el.addEventListener('click', () => {
      const id = (el as HTMLElement).dataset.node!;
      if (id === engine.currentNodeId) {
        const rect = el.getBoundingClientRect();
        engine.tap(rect.width / 2, rect.height / 2);
        triggerHaptic('light');
        return;
      }
      const dest = getNode(id);
      const ok = engine.travelTo(id);
      if (ok && dest) {
        spawnLootToast('🗺️', `Walking to ${dest.name}`);
        triggerHaptic('medium');
        shake(document.getElementById('world-map'), 160);
      } else if (dest && !engine.discoveredNodeIds.includes(dest.id)) {
        spawnLootToast('❔', `Need ${formatNumber(dest.unlockSouls)} souls to scout`);
        triggerHaptic('light');
      }
    });
  });

  const rummage = document.getElementById('rummage-btn');
  const ring = document.getElementById('rummage-ring');
  if (rummage) {
    const start = (e: PointerEvent) => {
      rummage.setPointerCapture(e.pointerId);
      rummageStarted = Date.now();
      rummage.classList.add('holding');
      rummage.querySelector('span:last-child')!.textContent = 'Rummaging...';
      rummageTimer = window.setInterval(() => {
        const p = Math.min(1, (Date.now() - rummageStarted) / 900);
        if (ring) {
          ring.style.setProperty('--p', String(p));
          ring.style.width = `${Math.round(p * 100)}%`;
        }
        if (p >= 1) finishRummage();
      }, 40);
    };
    const cancel = () => {
      if (rummageTimer) clearInterval(rummageTimer);
      rummageTimer = null;
      rummage.classList.remove('holding');
      rummage.querySelector('span:last-child')!.textContent = 'Hold to rummage';
      if (ring) ring.style.setProperty('--p', '0');
    };
    const finishRummage = () => {
      cancel();
      const result = engine.rummage();
      floatText(rummage, 40, 10, `+${formatNumber(result.souls)}`, !!result.loot);
      shake(document.getElementById('node-panel'), 240);
      triggerHaptic('heavy');
    };
    rummage.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      start(e as PointerEvent);
    });
    rummage.addEventListener('pointerup', cancel);
    rummage.addEventListener('pointercancel', cancel);
  }
}

function bindPack(): void {
  document.querySelectorAll('.pack-slot.filled').forEach((el) => {
    const btn = el as HTMLElement;
    btn.addEventListener('pointerdown', (e) => beginDrag(e as PointerEvent, btn));
  });

  document.querySelectorAll('.pack-slot.empty').forEach((el) => {
    el.addEventListener('pointerup', () => {
      /* drop handled globally */
    });
  });

  document.querySelectorAll('.equip-slot.empty').forEach((el) => {
    el.addEventListener('click', () => {
      if (!selectedItemUid) return;
      engine.equipItem(selectedItemUid, Number((el as HTMLElement).dataset.equip));
      triggerHaptic('medium');
    });
  });

  document.querySelectorAll('[data-unequip]').forEach((el) => {
    el.addEventListener('click', () => {
      engine.unequipItem((el as HTMLElement).dataset.unequip!);
      triggerHaptic('light');
    });
  });

  document.getElementById('btn-equip')?.addEventListener('click', () => {
    if (!selectedItemUid) return;
    const taken = engine.packItems.filter((i) => i.slot < 0).length;
    engine.equipItem(selectedItemUid, Math.min(taken, EQUIP_SLOTS - 1));
    triggerHaptic('medium');
  });

  document.getElementById('btn-crush')?.addEventListener('click', () => {
    if (!selectedItemUid) return;
    const value = engine.crushItem(selectedItemUid);
    selectedItemUid = null;
    spawnLootToast('💀', `+${formatNumber(value)} souls`);
    triggerHaptic('medium');
  });

  document.getElementById('btn-crush-shards')?.addEventListener('click', () => {
    const value = engine.crushAllShards();
    if (value > 0) spawnLootToast('💎', `Crushed for ${formatNumber(value)}`);
    triggerHaptic('medium');
  });
}

function beginDrag(e: PointerEvent, btn: HTMLElement): void {
  const uid = btn.dataset.item;
  if (!uid) return;
  const startX = e.clientX;
  const startY = e.clientY;
  let ghost: HTMLElement | null = null;

  const move = (ev: PointerEvent) => {
    const dx = ev.clientX - startX;
    const dy = ev.clientY - startY;
    if (!dragging && Math.hypot(dx, dy) < 8) return;
    if (!dragging) {
      dragging = true;
      ghost = btn.cloneNode(true) as HTMLElement;
      ghost.classList.add('drag-ghost');
      document.body.appendChild(ghost);
      btn.classList.add('ghosted');
      triggerHaptic('light');
    }
    if (ghost) {
      ghost.style.pointerEvents = 'none';
      ghost.style.left = `${ev.clientX - 28}px`;
      ghost.style.top = `${ev.clientY - 28}px`;
    }
  };

  const end = (ev: PointerEvent) => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', end);
    btn.classList.remove('ghosted');
    if (!dragging) {
      selectedItemUid = uid;
      render();
      return;
    }
    dragging = false;
    ghost?.remove();
    ghost = null;
    const under = document.elementFromPoint(ev.clientX, ev.clientY) as HTMLElement | null;
    const slotEl = under?.closest('[data-slot]') as HTMLElement | null;
    const equipEl = under?.closest('[data-equip]') as HTMLElement | null;
    if (slotEl?.dataset.slot != null) {
      engine.moveItem(uid, Number(slotEl.dataset.slot));
      triggerHaptic('medium');
    } else if (equipEl?.dataset.equip != null) {
      engine.equipItem(uid, Number(equipEl.dataset.equip));
      triggerHaptic('medium');
    }
  };

  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', end);
}

function bindRest(): void {
  document.getElementById('btn-summon')?.addEventListener('click', () => {
    if (engine.summonReaper()) triggerHaptic('medium');
  });

  document.getElementById('btn-auto-merge')?.addEventListener('click', () => {
    if (engine.autoMerge() > 0) triggerHaptic('medium');
  });

  document.querySelectorAll('.galaxy-planet, .planet-card[data-planet]').forEach((el) => {
    el.addEventListener('click', () => {
      const planetId = (el as HTMLElement).dataset.planet!;
      const unlocked = (el as HTMLElement).dataset.unlocked === 'true';
      if (unlocked) engine.selectPlanet(planetId);
      else engine.unlockPlanet(planetId);
      currentTab = 'explore';
      triggerHaptic('medium');
    });
  });

  document.querySelectorAll('.reaper-card').forEach((el) => {
    el.addEventListener('click', () => {
      const id = (el as HTMLElement).dataset.reaper!;
      if (selectedReaperId && selectedReaperId !== id) {
        engine.mergeReaperPair(selectedReaperId, id);
        selectedReaperId = null;
        triggerHaptic('medium');
      } else {
        selectedReaperId = selectedReaperId === id ? null : id;
        render();
      }
    });
  });

  document.querySelectorAll('.class-card').forEach((el) => {
    el.addEventListener('click', () => {
      engine.setPlayerClass((el as HTMLElement).dataset.class as 'warlock');
      triggerHaptic('light');
    });
  });

  document.querySelectorAll('.upgrade-item').forEach((el) => {
    el.addEventListener('click', () => {
      engine.buyUpgrade((el as HTMLElement).dataset.upgrade!);
      triggerHaptic('light');
    });
  });

  document.getElementById('btn-prestige')?.addEventListener('click', () => {
    if (confirm('Ascend to the Void? This resets your progress but grants permanent bonuses.')) {
      engine.prestige();
      triggerHaptic('heavy');
    }
  });

  document.getElementById('btn-reset')?.addEventListener('click', () => {
    if (confirm('Reset all progress? This cannot be undone.')) engine.reset();
  });

  const chatInput = document.getElementById('chat-input') as HTMLInputElement;
  const sendChat = () => {
    const msg = chatInput?.value.trim();
    if (msg) {
      engine.simulatedWorld.addChat('You', msg);
      chatInput.value = '';
      render();
    }
  };
  document.getElementById('btn-send-chat')?.addEventListener('click', sendChat);
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendChat();
  });
  const chatMessages = document.getElementById('chat-messages');
  if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
}

init();
