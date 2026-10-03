"""Unit tests for reply parsing, JSON repair, spec validation and TeX rendering.

Run: python -m unittest discover -s tests
"""

import json
import unittest

from p2p.parse import extract_blocks, normalize_spec, parse_spec, repair_json
from p2p.texmath import rich_text, tex_to_mathml


class RepairJsonTest(unittest.TestCase):
    def test_single_backslash_tex_is_escaped(self):
        raw = '{"a": "$\\frac{1}{\\sqrt{d_k}}$ and $\\times$ and $\\nabla$ and $\\beta$"}'
        data = json.loads(repair_json(raw))
        self.assertEqual(data["a"], "$\\frac{1}{\\sqrt{d_k}}$ and $\\times$ and $\\nabla$ and $\\beta$")

    def test_real_newline_escape_is_kept(self):
        data = json.loads(repair_json('{"a": "line one\\nThe second\\tTabbed"}'))
        self.assertEqual(data["a"], "line one\nThe second\tTabbed")

    def test_already_escaped_is_unchanged(self):
        data = json.loads(repair_json('{"a": "$\\\\log_2 n$"}'))
        self.assertEqual(data["a"], "$\\log_2 n$")

    def test_trailing_comma(self):
        self.assertEqual(json.loads(repair_json('{"a": [1, 2,], }')), {"a": [1, 2]})


class ExtractTest(unittest.TestCase):
    def test_two_blocks(self):
        text = 'intro\n```json\n{"x": 1}\n```\n\n```javascript\nfunction compute(s){return {}}\n```\n'
        j, js = extract_blocks(text)
        self.assertEqual(parse_spec(j), {"x": 1})
        self.assertIn("function compute", js)

    def test_code_only_reply_has_no_json(self):
        j, js = extract_blocks("```javascript\nfunction compute(s) { return {a: 1}; }\n```")
        self.assertIsNone(j)
        self.assertIn("compute", js)

    def test_unfenced_json_object(self):
        j, _ = extract_blocks('Here: {"title": "x"} done')
        self.assertEqual(parse_spec(j), {"title": "x"})

    def test_truncated_js_block(self):
        _, js = extract_blocks('```json\n{}\n```\n```js\nfunction compute(s){\n  return 1')
        self.assertIn("return 1", js)


def _spec(**over):
    spec = {
        "title": "T", "idea": "I", "why": "W", "equations": [{"tex": "x"}],
        "symbols": [{"symbol": "x", "meaning": "m"}, {"symbol": "y", "meaning": "m"}],
        "controls": [
            {"id": "n", "type": "range", "min": 1, "max": 6, "step": 1, "value": 9},
            {"id": "p", "type": "vector", "length": "n", "min": 0, "max": 1, "value": [0.5, 0.5]},
        ],
        "explorations": [{"title": "a", "change": "c", "observe": "o", "why": "w", "preset": {"n": 2, "zz": 1}},
                         {"title": "b", "change": "c", "observe": "o", "why": "w"}],
        "pitfall": {"kind": "assumption", "text": "t"},
        "grounding": {"section": "S1", "from_source": ["a"], "our_additions": ["b"]},
        "plan": {"coverage": [{"outcome": "vary n", "where": ["control:n", "exploration:1"]}]},
    }
    spec.update(over)
    return spec


class NormalizeTest(unittest.TestCase):
    def test_valid_spec_with_fixes(self):
        spec, errors, fixes = normalize_spec(_spec())
        self.assertEqual(errors, [])
        self.assertEqual(spec["controls"][0]["value"], 6)  # clamped to max
        self.assertIsNone(spec["explorations"][1]["preset"])
        self.assertEqual(spec["explorations"][0]["preset"], {"n": 2})  # unknown id dropped
        self.assertTrue(fixes)

    def test_missing_pieces_are_reported(self):
        _, errors, _ = normalize_spec(_spec(controls=[], explorations=[]))
        self.assertTrue(any("2 valid controls" in e for e in errors))
        self.assertTrue(any("2 guided explorations" in e for e in errors))

    def test_coverage_references_are_checked(self):
        bad = _spec(plan={"coverage": [{"outcome": "o", "where": ["control:nope", "exploration:3", "visual", "control:N"]}]})
        spec, errors, _ = normalize_spec(bad)
        self.assertEqual(errors, [])  # coverage issues are warnings, never revision triggers
        self.assertTrue(any("unknown control 'nope'" in w for w in spec["coverage_warnings"]))
        self.assertTrue(any("unknown exploration '3'" in w for w in spec["coverage_warnings"]))
        self.assertEqual(spec["coverage"][0]["where"], ["visual", "control:n"])  # near-miss id corrected
        spec, _, _ = normalize_spec(_spec(plan={}))
        self.assertTrue(any("empty" in w for w in spec["coverage_warnings"]))

    def test_bad_dimension_reference(self):
        bad = _spec()
        bad["controls"][1]["length"] = "missing"
        _, errors, _ = normalize_spec(bad)
        self.assertTrue(any("unknown control" in e for e in errors))


class TexTest(unittest.TestCase):
    def test_fraction_and_sqrt(self):
        m = tex_to_mathml(r"\frac{QK^\top}{\sqrt{d_k}}")
        self.assertIn("<mfrac>", m)
        self.assertIn("<msqrt>", m)
        self.assertIn("⊤", m)

    def test_sum_limits(self):
        m = tex_to_mathml(r"\sum_{i=1}^{n} p_i", display=True)
        self.assertIn("<munderover>", m)

    def test_matrix_environment(self):
        m = tex_to_mathml(r"\begin{pmatrix}1 & 2 \\ 3 & 4\end{pmatrix}")
        self.assertEqual(m.count("<mtr>"), 2)
        self.assertEqual(m.count("<mtd"), 4)

    def test_html_is_escaped(self):
        self.assertNotIn("<script>", rich_text("<script>alert(1)</script> and $x<y$"))

    def test_unknown_command_degrades(self):
        self.assertIn("foo", tex_to_mathml(r"\foo{x}"))


if __name__ == "__main__":
    unittest.main()
