/*
 * Transport layer.
 *
 * Every mutating endpoint returns the full new state alongside the result of the
 * action, so a click is one round trip and the UI never has to reconcile a local
 * guess against a later fetch. That matters more than payload size here: on a
 * tap-driven game, a stale render after a click is the one bug players notice.
 */

const API = (() => {
  // A stable per-browser session id, so a reload resumes the same in-memory run
  // rather than generating a new world.
  const SESSION_KEY = 'incgame.session';
  let session = localStorage.getItem(SESSION_KEY);
  if (!session) {
    session = 's' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    localStorage.setItem(SESSION_KEY, session);
  }

  async function call(path, method = 'GET', body = null) {
    const options = {
      method,
      headers: { 'X-Session': session },
    };
    if (body !== null) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    let data;
    try {
      data = await response.json();
    } catch (err) {
      throw new Error(`server returned non-JSON (${response.status})`);
    }
    if (!response.ok) {
      throw new Error(data && data.error ? data.error : `HTTP ${response.status}`);
    }
    return data;
  }

  return {
    session,
    state: (full = false) => call('/api/state' + (full ? '?full=1' : '')),
    newGame: (seed) => call('/api/new', 'POST', { seed: seed ?? null }),
    action: (id) => call('/api/action', 'POST', { id }),
    buyGenerator: (id, count = 1) => call('/api/generator', 'POST', { id, count }),
    buyUpgrade: (id) => call('/api/upgrade', 'POST', { id }),
    prestige: () => call('/api/prestige', 'POST', {}),
    buyPrestige: (id) => call('/api/prestige-upgrade', 'POST', { id }),
    save: () => call('/api/save'),
    load: (save) => call('/api/load', 'POST', { save }),
  };
})();
