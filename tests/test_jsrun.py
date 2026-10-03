"""Tests for the V8 execution checks (offline, synthetic specs - no paper content)."""

import unittest

from p2p.jsrun import clipped_labels, conform, control_variants, execute

CONTROLS = [
    {"id": "n", "type": "range", "label": "n", "min": 1, "max": 4, "step": 1, "value": 2},
    {"id": "w", "type": "vector", "label": "w", "length": "n", "min": 0, "max": 2, "step": 0.1, "value": [1, 1]},
    {"id": "k", "type": "toggle", "label": "k", "value": True},
]
SPEC = {
    "controls": CONTROLS,
    "explorations": [{"preset": {"n": 3, "w": [1, 2, 0]}}, {"preset": None}],
    "tests": [{"name": "sum", "state": {"n": 2, "w": [1, 2]}, "expect": [{"path": "total", "value": 3}]}],
}
GOOD = """
function compute(s) { var t = PG.sum(s.w); return { total: s.k ? t : -t, share: s.w.map(function (x) { return t > 0 ? x / t : 0; }) }; }
function render(s, r) { return PG.svg(200, 100, PG.bars({x: 0, y: 0, w: 200, h: 100, values: r.share})); }
function show(s, r) { return [{label: "total", value: r.total}, {label: "shares", value: r.share}]; }
function checks(s, r) { return [{name: "shares sum to 1 or 0", pass: Math.abs(PG.sum(r.share) - 1) < 1e-9 || PG.sum(r.share) === 0}]; }
"""


class ConformTest(unittest.TestCase):
    def test_vector_follows_dimension_control(self):
        state = conform({"n": 4, "w": [1, 1], "k": True}, CONTROLS)
        self.assertEqual(state["w"], [1, 1, 0, 0])
        state = conform({"n": 1, "w": [5, 1], "k": True}, CONTROLS)
        self.assertEqual(state["w"], [5])

    def test_variants_cover_edges(self):
        values = [v for _, v in control_variants(CONTROLS[0])]
        self.assertEqual(sorted(values), [1, 3, 4])
        self.assertIn([0.0, 0.0], [v for _, v in control_variants(CONTROLS[1])])


class ExecuteTest(unittest.TestCase):
    def test_good_code_passes(self):
        rep = execute(SPEC, GOOD)
        self.assertEqual(rep.problems, [])
        self.assertFalse(rep.critical)
        self.assertTrue(all(rep.control_effects.values()))
        self.assertTrue(rep.tests and rep.tests[0]["passed"])

    def test_syntax_error_is_critical(self):
        rep = execute(SPEC, GOOD + "\nfunction broken( {")
        self.assertTrue(rep.critical)
        self.assertIn("does not load", rep.problems[0])

    def test_nan_division_is_reported(self):
        bad = GOOD.replace("t > 0 ? x / t : 0", "x / t")
        rep = execute(SPEC, bad)
        self.assertTrue(any("non-finite" in p for p in rep.problems), rep.problems)

    def test_ineffective_control_and_failed_test(self):
        bad = GOOD.replace("s.k ? t : -t", "t + 1")
        rep = execute(SPEC, bad)
        self.assertFalse(rep.control_effects["k"])
        self.assertTrue(any("control 'k' has no effect" in p for p in rep.problems))
        self.assertTrue(any("known-answer test 'sum' failed" in p for p in rep.problems))

    def test_bad_svg_and_failing_check(self):
        bad = GOOD.replace("return PG.svg(200, 100,", "return '<svg><text>' + r.missing + '</text></svg>' || PG.svg(200, 100,")
        bad = bad.replace("< 1e-9 || PG.sum(r.share) === 0", "< 1e-9")
        rep = execute(SPEC, bad)
        self.assertTrue(any("undefined" in p for p in rep.problems), rep.problems)
        self.assertTrue(any("live check" in p for p in rep.problems), rep.problems)

    def test_clipped_labels(self):
        svg = ('<svg viewBox="0 0 200 100"><text x="190" y="50">a long label here</text>'
               '<text x="100" y="50" text-anchor="middle">ok</text>'
               '<g transform="translate(150,0)"><text x="60" y="20">far</text></g>'
               '<g transform="rotate(-90)"><text x="0" y="0">skipped</text></g></svg>')
        found = clipped_labels(svg)
        self.assertEqual(len(found), 2)
        self.assertIn("a long label here", found[0])

    def test_plain_tex_for_svg_labels(self):
        from py_mini_racer import MiniRacer
        from p2p.jsrun import TEMPLATE_DIR
        ctx = MiniRacer()
        ctx.eval((TEMPLATE_DIR / "lib.js").read_text(encoding="utf-8"))
        cases = {r"inputs $x_i$": "inputs xᵢ", r"$\frac{1}{\sqrt{d_k}}$": "1/(√(dₖ))",
                 r"$\hat{x}_i$": "x̂ᵢ", "costs $5": "costs $5", r"$QK^\top$": "QKᵀ"}
        for tex, want in cases.items():
            self.assertEqual(ctx.call("PG.plain", tex), want)
        self.assertIn("σ", ctx.call("PG.text", 0, 0, r"$\sigma$"))

    def test_presets_buttons(self):
        spec = dict(SPEC, controls=CONTROLS + [
            {"id": "quick", "type": "presets", "label": "q", "options": [{"label": "one-hot", "set": {"n": 3, "w": [2, 0, 0]}}]}])
        rep = execute(spec, GOOD)
        self.assertEqual(rep.problems, [])
        self.assertTrue(rep.control_effects["quick"])
        # a button that only sets an input the code ignores is dead
        dead = dict(SPEC, controls=CONTROLS + [
            {"id": "quick", "type": "presets", "label": "q", "options": [{"label": "k off", "set": {"k": False}}]}])
        rep = execute(dead, GOOD.replace("s.k ? t : -t", "t"))
        self.assertTrue(any("control 'quick' has no effect" in p for p in rep.problems))

    def test_missing_function(self):
        rep = execute(SPEC, GOOD.replace("function checks", "function checkz"))
        self.assertTrue(rep.critical)
        self.assertIn("checks", rep.problems[0])


if __name__ == "__main__":
    unittest.main()
