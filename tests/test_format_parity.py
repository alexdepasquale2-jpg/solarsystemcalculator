"""
Parity between the Python and JavaScript number formatters.

`fmt_number` exists twice: in `incgame/model.py` for the server, and in
`frontend/js/format.js` for the client, which formats locally interpolated
amounts between polls. Duplication is the right call there -- round-tripping to
the server every frame to get a string would defeat the point of interpolating --
but two implementations of the same function drift, and the symptom is a number
that visibly changes format on every poll.

This test runs the same table of values through both and requires identical
output. It shells out to `node`; if node is unavailable the test skips rather than
failing, since the parity risk is real but not worth blocking a Python-only
environment over.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from incgame.model import fmt_number, fmt_rate

FORMAT_JS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "format.js"

# Values chosen to hit every branch and every boundary: the integer shortcut, the
# <10 decimal case, the 10-999 case, each suffix threshold, and the scientific
# fallback past decillion.
VALUES = [
    0, 1, 7, 9.5, 9.999, 10, 99.94, 100, 999, 999.4, 999.99, 1000, 1023.7,
    9999, 12345, 999999, 1e6, 1.5e6, 1e9, 5.55e9, 1e12, 1e15, 1e18, 1e21,
    1e24, 1e27, 1e30, 1e33, 1e36, 1e39, 1.7e40, 1e100,
    0.5, 0.05, 0.004, 1 / 3, 2 / 3,
    -1, -1234.5, -1e7,
]


class TestFormatParity(unittest.TestCase):
    def setUp(self):
        if shutil.which("node") is None:
            self.skipTest("node is not available")

    def _js(self, script: str) -> list:
        source = FORMAT_JS.read_text() + "\n" + script
        result = subprocess.run(
            ["node", "-e", source], capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode != 0:
            self.fail(f"node failed: {result.stderr.strip()}")
        return json.loads(result.stdout)

    def test_fmt_number_matches(self):
        script = f"console.log(JSON.stringify({json.dumps(VALUES)}.map(v => fmtNumber(v))));"
        js_output = self._js(script)
        py_output = [fmt_number(v) for v in VALUES]
        mismatches = [
            (value, py, js)
            for value, py, js in zip(VALUES, py_output, js_output)
            if py != js
        ]
        self.assertEqual(
            mismatches,
            [],
            "formatters disagree (value, python, javascript):\n"
            + "\n".join(f"  {v!r}: {p!r} != {j!r}" for v, p, j in mismatches),
        )

    def test_fmt_rate_matches(self):
        rates = [0, 1e-12, 0.5, 1, 12.5, 1234, 1e7, -0.5, -1234]
        script = f"console.log(JSON.stringify({json.dumps(rates)}.map(v => fmtRate(v))));"
        self.assertEqual([fmt_rate(v) for v in rates], self._js(script))

    def test_non_finite_values_match(self):
        script = (
            "console.log(JSON.stringify([Infinity, -Infinity, NaN].map(v => fmtNumber(v))));"
        )
        expected = [fmt_number(float("inf")), fmt_number(float("-inf")), fmt_number(float("nan"))]
        self.assertEqual(expected, self._js(script))


if __name__ == "__main__":
    unittest.main()
