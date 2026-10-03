"""Execute the generated JavaScript in V8 (mini-racer) and test it.

The page's pure functions are run exactly as the browser runtime runs them:
same helper library, same state construction (defaults, presets, resizing of
dimension-linked vectors/matrices). States tested:
  - the default state and both exploration presets,
  - every control at its edge/alternative values (min, max, other options,
    all-zero / one-hot / equal vectors and matrices),
  - each known-answer test state from the spec.
For each state compute/render/show/checks must run without exceptions, return
finite numbers and well-formed SVG, and every live check must pass. Each
control must change the result or the visual (a "meaningful" control).
"""

from __future__ import annotations

import copy
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
CALL_TIMEOUT_SEC = 2.0

HARNESS_JS = r"""
var __P2P = (function () {
  function fn(name) { try { var f = (0, eval)(name); return typeof f === 'function' ? f : null; } catch (e) { return null; } }
  var F = { compute: fn('compute'), render: fn('render'), show: fn('show'), checks: fn('checks') };
  function msg(e) { return String(e && e.message ? e.message : e).slice(0, 200); }
  function nonFinite(x, path, out, depth) {
    if (out.length >= 4 || depth > 6) return;
    if (typeof x === 'number') { if (!isFinite(x)) out.push((path || 'value') + '=' + x); return; }
    if (x === undefined) { out.push((path || 'value') + '=undefined'); return; }
    if (Array.isArray(x)) { for (var i = 0; i < x.length && i < 400; i++) nonFinite(x[i], path + '[' + i + ']', out, depth + 1); return; }
    if (x && typeof x === 'object') { for (var k in x) nonFinite(x[k], path ? path + '.' + k : k, out, depth + 1); }
  }
  function copy(x) { return JSON.parse(JSON.stringify(x)); }
  function missing() { return ['compute', 'render', 'show', 'checks'].filter(function (n) { return !F[n]; }); }
  function run(stateJson) {
    var s = JSON.parse(stateJson), res = {};
    if (!F.compute) return JSON.stringify(res);
    var r;
    try { r = F.compute(copy(s)); } catch (e) { res.error = { stage: 'compute', msg: msg(e) }; return JSON.stringify(res); }
    var nf = []; nonFinite(r, '', nf, 0); res.nonfinite = nf;
    try { res.result = JSON.stringify(r); } catch (e) { res.result = null; res.resultError = msg(e); }
    if (F.render) {
      try { var svg = F.render(copy(s), r); res.svgType = typeof svg; res.svg = typeof svg === 'string' ? svg.slice(0, 300000) : null; }
      catch (e) { res.renderError = msg(e); }
    }
    if (F.show) {
      try {
        var items = F.show(copy(s), r);
        if (!Array.isArray(items)) res.showError = 'show() must return an array';
        else {
          res.showCount = items.length; res.showBad = [];
          items.forEach(function (it, i) {
            if (!it || typeof it !== 'object' || it.label == null) { res.showBad.push('item ' + i + ' has no label'); return; }
            var bad = []; nonFinite(it.value, '', bad, 0);
            if (bad.length) res.showBad.push('"' + it.label + '" value is ' + bad[0].replace(/^value=/, ''));
          });
        }
      } catch (e) { res.showError = msg(e); }
    }
    if (F.checks) {
      try {
        var cs = F.checks(copy(s), r);
        if (!Array.isArray(cs)) res.checksError = 'checks() must return an array';
        else res.checks = cs.map(function (c) { return { name: String(c && c.name), pass: !!(c && c.pass === true), detail: c && c.detail != null ? String(c.detail).slice(0, 160) : '' }; });
      } catch (e) { res.checksError = msg(e); }
    }
    return JSON.stringify(res);
  }
  function getPath(resultJson, path) {
    var r = JSON.parse(resultJson), parts = String(path).replace(/\[(\d+)\]/g, '.$1').split('.').filter(Boolean);
    for (var i = 0; i < parts.length; i++) { if (r == null || !(parts[i] in Object(r))) return JSON.stringify({ found: false, keys: r && typeof r === 'object' ? Object.keys(r).slice(0, 25) : [] }); r = r[parts[i]]; }
    return JSON.stringify({ found: true, value: r });
  }
  return { run: run, missing: missing, getPath: getPath };
})();
"""


@dataclass
class ExecReport:
    problems: list[str] = field(default_factory=list)
    critical: bool = False
    states_tested: int = 0
    tests: list[dict] = field(default_factory=list)
    control_effects: dict[str, bool] = field(default_factory=dict)
    checks_seen: int = 0
    engine: str = "v8"


# ------------------------------------------------------------ state building
def _round(x: float) -> int:
    return int(math.floor(x + 0.5))  # JavaScript Math.round semantics


def _dim(d, fallback: int, state: dict) -> int:
    if isinstance(d, (int, float)) and not isinstance(d, bool):
        return max(1, _round(d))
    if isinstance(d, str):
        v = state.get(d)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            return max(1, _round(v))
    return fallback


def _num_or(x, fill):
    try:
        v = float(x)
        return v if math.isfinite(v) else fill
    except (TypeError, ValueError):
        return fill


def conform(state: dict, controls: list[dict]) -> dict:
    """Mirror runtime.js conform(): resize vectors/matrices to their dimensions."""
    for c in controls:
        fill = float(c.get("fill", 0) or 0)
        if c["type"] == "vector":
            n = _dim(c.get("length"), len(c["value"]) if isinstance(c.get("value"), list) else 3, state)
            v = state.get(c["id"]) if isinstance(state.get(c["id"]), list) else []
            v = list(v[:n]) + [fill] * max(0, n - len(v))
            state[c["id"]] = [_num_or(x, fill) for x in v]
        elif c["type"] == "matrix":
            val = c.get("value") if isinstance(c.get("value"), list) else []
            r0 = len(val) or 2
            c0 = len(val[0]) if val and isinstance(val[0], list) else 2
            r, k = _dim(c.get("rows"), r0, state), _dim(c.get("cols"), c0, state)
            m = state.get(c["id"]) if isinstance(state.get(c["id"]), list) else []
            m = list(m[:r]) + [[]] * max(0, r - len(m))
            out = []
            for row in m:
                row = row if isinstance(row, list) else []
                row = list(row[:k]) + [fill] * max(0, k - len(row))
                out.append([_num_or(x, fill) for x in row])
            state[c["id"]] = out
    return state


def default_state(controls: list[dict]) -> dict:
    return conform({c["id"]: copy.deepcopy(c["value"]) for c in controls}, controls)


def with_overrides(controls: list[dict], overrides: dict) -> dict:
    state = {c["id"]: copy.deepcopy(c["value"]) for c in controls}
    ids = set(state)
    for k, v in (overrides or {}).items():
        if k in ids:
            state[k] = copy.deepcopy(v)
    return conform(state, controls)


def _bounds(c: dict, values: list[float]) -> tuple[float, float]:
    lo = c.get("min")
    hi = c.get("max")
    if lo is None:
        lo = 0.0 if all(v >= 0 for v in values) else -3.0
    if hi is None:
        hi = max(3.0, 2 * max((abs(v) for v in values), default=1.0))
    return float(lo), float(hi)


def control_variants(c: dict) -> list[tuple[str, Any]]:
    """Alternative values of one control: (description, value)."""
    t, v = c["type"], c["value"]
    out: list[tuple[str, Any]] = []
    if t in ("range", "number"):
        lo, hi = c.get("min"), c.get("max")
        step = c.get("step")
        cands = []
        if lo is not None and hi is not None:
            if step and float(step).is_integer() and float(lo).is_integer() and (hi - lo) / step <= 8:
                x = lo
                while x <= hi + 1e-9:
                    cands.append(x)
                    x += step
            else:
                cands += [lo, hi, lo + (hi - lo) / 2]
        else:
            cands += [x for x in (lo, hi) if x is not None] + [v + 1, v - 1 if (lo is None or v - 1 >= lo) else v]
        for x in cands:
            x = round(float(x), 10)
            if x != v:
                out.append((f"{c['id']}={x:g}", x))
    elif t == "toggle":
        out.append((f"{c['id']}={not v}", not v))
    elif t == "select":
        for o in c["options"]:
            if o["value"] != v:
                out.append((f"{c['id']}={o['value']!r}", o["value"]))
    elif t == "vector":
        lo, hi = _bounds(c, v)
        n = len(v)
        out.append((f"all {c['id']} entries = {lo:g}", [lo] * n))
        out.append((f"all {c['id']} entries = {hi:g}", [hi] * n))
        out.append((f"{c['id']} one-hot", [hi] + [lo] * (n - 1)))
        mid = lo + (hi - lo) / 2
        out.append((f"all {c['id']} entries equal ({mid:g})", [mid] * n))
    elif t == "matrix":
        lo, hi = _bounds(c, [x for row in v for x in row])
        r, k = len(v), len(v[0])
        zero = 0.0 if lo <= 0 <= hi else lo
        out.append((f"all {c['id']} entries = {zero:g}", [[zero] * k for _ in range(r)]))
        out.append((f"all {c['id']} entries = {hi:g}", [[hi] * k for _ in range(r)]))
        out.append((f"all {c['id']} entries = {lo:g}", [[lo] * k for _ in range(r)]))
        dom = [[zero] * k for _ in range(r)]
        dom[0][0] = hi
        out.append((f"{c['id']} with one dominant entry", dom))
    seen, uniq = set(), []
    for desc, val in out:
        key = json.dumps(val, sort_keys=True)
        if key not in seen:
            seen.add(key)
            uniq.append((desc, val))
    return uniq


# --------------------------------------------------------------- execution
class _Engine:
    def __init__(self, code: str):
        from py_mini_racer import MiniRacer  # imported lazily: failure is handled by caller

        self.ctx = MiniRacer()
        self.ctx.eval((TEMPLATE_DIR / "lib.js").read_text(encoding="utf-8"), timeout_sec=CALL_TIMEOUT_SEC)
        self.code_error: str | None = None
        try:
            self.ctx.eval(code, timeout_sec=CALL_TIMEOUT_SEC)
        except Exception as exc:  # syntax error or top-level runtime error
            self.code_error = _short(exc)
        self.ctx.eval(HARNESS_JS, timeout_sec=CALL_TIMEOUT_SEC)

    def missing(self) -> list[str]:
        return json.loads(self.ctx.eval("JSON.stringify(__P2P.missing())", timeout_sec=CALL_TIMEOUT_SEC))

    def run(self, state: dict) -> dict:
        arg = json.dumps(json.dumps(state))
        try:
            return json.loads(self.ctx.eval(f"__P2P.run({arg})", timeout_sec=CALL_TIMEOUT_SEC))
        except Exception as exc:
            return {"error": {"stage": "execution", "msg": _short(exc)}}

    def get_path(self, result_json: str, path: str) -> dict:
        expr = f"__P2P.getPath({json.dumps(result_json)}, {json.dumps(path)})"
        return json.loads(self.ctx.eval(expr, timeout_sec=CALL_TIMEOUT_SEC))


def _short(exc: Exception) -> str:
    text = str(exc).strip()
    m = re.search(r"(SyntaxError|ReferenceError|TypeError|RangeError|Error)[^\n]*", text)
    if m:
        line = re.search(r"<anonymous>:(\d+)", text)
        return m.group(0)[:200] + (f" (line {line.group(1)})" if line else "")
    if "timeout" in text.lower():
        return "execution timed out (infinite loop?)"
    return text.splitlines()[0][:200] if text else type(exc).__name__


_ENTITY_RE = re.compile(r"&(?!#\d+;|#x[0-9a-fA-F]+;|amp;|lt;|gt;|quot;|apos;)[A-Za-z0-9]+;")


def _svg_problem(svg: str) -> str | None:
    if "<svg" not in svg:
        return "render() must return an <svg> string (use PG.svg(w, h, body))"
    try:
        ET.fromstring(_ENTITY_RE.sub("&#160;", svg.strip()))
    except ET.ParseError as exc:
        return f"render() SVG is not well-formed ({exc}); escape text with PG.esc or use PG.text"
    m = re.search(r"\b(NaN|undefined|Infinity)\b", svg)
    if m:
        return f"render() output contains '{m.group(1)}' (a coordinate or label was not computed)"
    return None


_TRANSLATE_RE = re.compile(r"\s*translate\(\s*([-+\d.eE]+)(?:[\s,]+([-+\d.eE]+))?\s*\)\s*")


def _num_attr(value, default: float = 0.0) -> float:
    try:
        return float(str(value).replace("px", "").split()[0].split(",")[0])
    except (ValueError, IndexError):
        return default


def clipped_labels(svg: str) -> list[str]:
    """Text labels that extend outside the SVG viewBox (they are cut off when drawn).

    Width is estimated from font size and character count, so only clear
    overflows are reported. Elements under non-translate transforms are skipped.
    """
    try:
        root = ET.fromstring(_ENTITY_RE.sub("&#160;", svg.strip()))
    except ET.ParseError:
        return []
    box = (root.get("viewBox") or "").replace(",", " ").split()
    if len(box) != 4:
        return []
    x0, y0, w, h = (_num_attr(v) for v in box)
    found: list[str] = []

    def walk(el, dx: float, dy: float) -> None:
        tr = el.get("transform")
        if tr:
            m = _TRANSLATE_RE.fullmatch(tr)
            if not m:
                return  # rotated/scaled content: geometry not estimated
            dx += float(m.group(1))
            dy += float(m.group(2) or 0)
        if el.tag.split("}")[-1] == "text":
            label = "".join(el.itertext()).strip()
            if label:
                size = _num_attr(el.get("font-size"), 13.0)
                x = _num_attr(el.get("x")) + dx
                y = _num_attr(el.get("y")) + dy
                width = 0.55 * size * len(label)
                anchor = el.get("text-anchor", "start")
                left = x - width / 2 if anchor == "middle" else x - width if anchor == "end" else x
                top = y - size / 2 if el.get("dominant-baseline") in ("middle", "central") else y - 0.8 * size
                over = max(x0 - left, left + width - (x0 + w), y0 - top, top + size - (y0 + h))
                if over > max(8.0, 0.3 * min(width, 200)):
                    found.append(f"\"{label[:40]}\" at x={x:.0f}, y={y:.0f} (anchor {anchor}) in a "
                                 f"{w:.0f}x{h:.0f} viewBox")
            return
        for child in el:
            walk(child, dx, dy)

    walk(root, 0.0, 0.0)
    return found


def execute(spec: dict, code: str) -> ExecReport:
    rep = ExecReport()
    controls = spec.get("controls", [])
    try:
        eng = _Engine(code)
    except ImportError:
        rep.engine = "unavailable"
        return rep
    if eng.code_error:
        rep.problems.append(f"the javascript does not load: {eng.code_error}")
        rep.critical = True
        return rep
    missing = eng.missing()
    if missing:
        rep.problems.append("code must define top-level functions: " + ", ".join(missing))
        rep.critical = True
        if "compute" in missing:
            return rep

    issues: dict[str, list[str]] = {}

    def note(message: str, where: str) -> None:
        issues.setdefault(message, [])
        if len(issues[message]) < 2:
            issues[message].append(where)

    def evaluate(state: dict, where: str) -> dict:
        rep.states_tested += 1
        res = eng.run(state)
        if res.get("error"):
            e = res["error"]
            hint = ""
            m = re.search(r"PG\.(\w+) is not a function", e["msg"])
            if m:
                hint = (f" (PG.{m.group(1)} is not one of the listed helpers; use a listed one or write "
                        f"the function yourself)")
            elif "PG" in e["msg"]:
                hint = " (a local variable may be hiding the helper library PG; rename it)"
            note(f"{e['stage']}() throws: {e['msg']}{hint}", where)
            return res
        if res.get("nonfinite"):
            note("compute() returns non-finite values (" + ", ".join(res["nonfinite"][:3]) + ")", where)
        if res.get("resultError"):
            note(f"compute() result is not JSON-serializable: {res['resultError']}", where)
        if res.get("renderError"):
            note(f"render() throws: {res['renderError']}", where)
        elif "svgType" in res:
            if res["svgType"] != "string":
                note(f"render() must return a string, got {res['svgType']}", where)
            else:
                p = _svg_problem(res["svg"] or "")
                if p:
                    note(p, where)
                elif where == "default state" or where.startswith("exploration"):
                    cut = clipped_labels(res["svg"])
                    if cut:
                        note(f"render(): {len(cut)} text label(s) extend outside the SVG viewBox and are cut off: "
                             f"{'; '.join(cut[:3])}. Move them inside or enlarge the PG.svg(w, h) size", where)
        if res.get("showError"):
            note(f"show() error: {res['showError']}", where)
        for b in res.get("showBad") or []:
            note(f"show(): {b}", where)
        if res.get("checksError"):
            note(f"checks() error: {res['checksError']}", where)
        for c in res.get("checks") or []:
            rep.checks_seen += 1
            if not c["pass"]:
                note(f"live check \"{c['name']}\" fails, but every check must be exactly true in every state the "
                     f"learner can reach. If the code is right, the claim itself only holds in a special case "
                     f"(a limiting value, a particular parameter, or approximately): restate the check so it is "
                     f"exactly true (put the condition in its name and test only when it applies, or compute the "
                     f"special case inside the check); otherwise fix the code",
                     where + (f": {c['detail']}" if c["detail"] else ""))
        return res

    base_state = default_state(controls)
    base = evaluate(base_state, "default state")
    if base.get("error") or base.get("renderError") or base.get("svgType") not in (None, "string"):
        rep.critical = True
    if base.get("error"):
        rep.problems += _format(issues)
        return rep
    if base.get("showCount", 1) == 0:
        note("show() returns no items: display the key intermediate values", "default state")
    contexts = [("default state", base_state, base)]
    for i, ex in enumerate(spec.get("explorations", [])):
        if ex.get("preset"):
            st = with_overrides(controls, ex["preset"])
            contexts.append((f"exploration {i + 1} preset", st, evaluate(st, f"exploration {i + 1} preset")))

    # Single-control sweeps from the default state (edge values of every control).
    sweeps: dict[str, list[tuple[str, Any, dict]]] = {}
    for c in controls:
        for desc, value in control_variants(c):
            sweeps.setdefault(c["id"], []).append((desc, value, evaluate(with_overrides(controls, {**base_state, c["id"]: value}), desc)))
    # Other controls' first variants are extra contexts: a control may only
    # matter once something else changes (e.g. a "force uniform" toggle when
    # the default distribution is already uniform).
    for c in controls:
        for desc, value, res in sweeps.get(c["id"], [])[:1]:
            if len(contexts) < 9:
                contexts.append((desc, with_overrides(controls, {**base_state, c["id"]: value}), res))

    def signature(res: dict):
        return (res.get("result"), res.get("svg"))

    for c in controls:
        changed = False
        for ctx_desc, ctx_state, ctx_res in contexts:
            if ctx_res.get("error"):
                continue
            for desc, value in control_variants(c):
                if ctx_state.get(c["id"]) == value:
                    continue
                if ctx_desc == "default state":
                    res = next(r for d, v, r in sweeps[c["id"]] if d == desc)
                else:
                    res = evaluate(with_overrides(controls, {**ctx_state, c["id"]: value}), f"{ctx_desc} + {desc}")
                if not res.get("error") and signature(res) != signature(ctx_res):
                    changed = True
                    break
            if changed:
                break
        rep.control_effects[c["id"]] = changed
        if not changed:
            note(f"control '{c['id']}' has no effect in any tested state: changing it alters neither compute() results nor the SVG", "control sweep")
    effective = sum(rep.control_effects.values())
    if controls and effective < 2:
        note(f"only {effective} control(s) change the output; at least 2 meaningful controls are required", "control sweep")

    for t in spec.get("tests", [])[:6]:
        name = str(t.get("name") or "test")
        state = with_overrides(controls, t.get("state") if isinstance(t.get("state"), dict) else {})
        res = evaluate(state, f"test '{name}'")
        if res.get("error") or res.get("result") is None:
            continue
        failures = []
        for exp in t.get("expect") or []:
            if not isinstance(exp, dict) or "path" not in exp:
                continue
            got = eng.get_path(res["result"], str(exp["path"]))
            entry = {"name": name, "path": exp["path"], "expected": exp.get("value")}
            if not got.get("found"):
                entry.update(passed=False, actual=None)
                failures.append(f"path '{exp['path']}' is not in the compute() result "
                                f"(keys: {', '.join(map(str, got.get('keys', [])))})")
            else:
                ok = _matches(got["value"], exp.get("value"), exp.get("tol"))
                approx = not ok and _matches(got["value"], exp.get("value"), None, rounded=True)
                entry.update(passed=ok or approx, actual=got["value"])
                if approx:
                    entry["note"] = "accepted: expectation is a rounded hand calculation (within 1%)"
                if not ok and not approx:
                    failures.append(f"expected {exp['path']} = {exp.get('value')!r}, compute() gave {_compact(got['value'])}")
            rep.tests.append(entry)
        if failures:
            more = f" (and {len(failures) - 1} more mismatches)" if len(failures) > 1 else ""
            note(f"known-answer test '{name}' failed: {failures[0]}{more}. Fix whichever of the code or the test "
                 f"disagrees with the paper's formula; if the test state contains rounded inputs (e.g. a "
                 f"hand-computed root), use inputs with an exact answer or drop the test", f"test '{name}'")

    rep.problems += _format(issues)
    return rep


def _is_rounded(x: float) -> bool:
    """True for values with more than 4 decimals, i.e. a rounded hand calculation."""
    return abs(x * 10_000 - round(x * 10_000)) > 1e-6


def _matches(actual, expected, tol, rounded: bool = False) -> bool:
    try:
        tol = float(tol) if tol is not None else 1e-6
    except (TypeError, ValueError):
        tol = 1e-6
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual == expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if rounded:
            # Exact-looking expectations (<= 4 decimals) get no extra slack.
            return _is_rounded(expected) and abs(actual - expected) <= 0.01 * max(1.0, abs(expected))
        return abs(actual - expected) <= max(tol, 1e-9 * max(1.0, abs(expected)))
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        return all(_matches(a, e, tol, rounded) or _matches(a, e, tol) for a, e in zip(actual, expected))
    return actual == expected


def _compact(value) -> str:
    text = json.dumps(value)
    return text if len(text) <= 120 else text[:117] + "..."


def _format(issues: dict[str, list[str]]) -> list[str]:
    out = []
    for message, where in issues.items():
        out.append(f"{message} [seen in: {'; '.join(where)}]")
    return out[:12]
