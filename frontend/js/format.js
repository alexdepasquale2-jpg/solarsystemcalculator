/*
 * Number formatting, mirrored from incgame/model.py:fmt_number.
 *
 * The duplication is deliberate. The client interpolates resource amounts
 * between polls (see app.js), so it has to format numbers the server never sent;
 * round-tripping every frame to get a string would defeat the point. Both
 * implementations are covered by tests/test_format_parity.py, which runs the same
 * table of values through each and compares.
 */

const SUFFIXES = ['', 'K', 'M', 'B', 'T', 'Qa', 'Qi', 'Sx', 'Sp', 'Oc', 'No', 'Dc'];

function fmtNumber(value, places = 2) {
  if (Number.isNaN(value)) return 'NaN';
  if (!Number.isFinite(value)) return value > 0 ? '∞' : '-∞';

  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);

  if (abs < 1000) {
    if (abs === Math.trunc(abs)) return sign + String(Math.trunc(abs));
    if (abs < 10) return sign + abs.toFixed(places);
    return sign + abs.toFixed(1);
  }

  const tier = Math.floor(Math.log10(abs) / 3);
  if (tier < SUFFIXES.length) {
    return sign + (abs / Math.pow(1000, tier)).toFixed(places) + SUFFIXES[tier];
  }
  // Match Python's %.2e, which pads the exponent to two digits.
  return sign + abs.toExponential(2).replace(/e([+-])(\d)$/, 'e$10$2');
}

function fmtRate(value) {
  if (Math.abs(value) < 1e-9) return '0/s';
  return (value > 0 ? '+' : '−') + fmtNumber(Math.abs(value)) + '/s';
}

function fmtDuration(seconds) {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}
