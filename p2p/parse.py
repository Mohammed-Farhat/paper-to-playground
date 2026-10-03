"""Parse the model reply into (spec, code) and validate/normalise the spec.

Models often forget to escape TeX backslashes inside JSON strings ("\\frac"
written as "\frac", which JSON reads as a form feed + "rac"). repair_json()
fixes this deterministically using a list of known TeX command names, so the
valid JSON escapes (\\n, \\t, ...) that start ordinary text are left alone.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .texmath import ACCENTS, BIG_OPS, FONT_CMDS, FUNCTIONS, GREEK, SYMBOLS, TEXT_CMDS, SPACES

_TEX_NAMES = set(GREEK) | set(SYMBOLS) | set(BIG_OPS) | set(FUNCTIONS) | set(ACCENTS) | set(FONT_CMDS) \
    | set(TEXT_CMDS) | {k for k in SPACES if k.isalpha()} | {
        "frac", "dfrac", "tfrac", "sqrt", "left", "right", "begin", "end", "mathbb", "binom",
        "underline", "overbrace", "underbrace", "overset", "underset", "stackrel", "mathop",
        "displaystyle", "textstyle", "limits", "nolimits", "big", "Big", "bigl", "bigr", "Bigl",
        "Bigr", "bigg", "Bigg", "label", "tag", "not", "nonumber", "notag", "operatorname",
        "hat", "bar", "vec", "tilde", "dot", "ddot", "boldsymbol", "mathbf", "mathrm", "text",
        "quad", "qquad", "cdot", "cdots", "ldots", "infty", "partial", "nabla", "top", "times",
        "theta", "tau", "nu", "neq", "ne", "rho", "right", "rangle", "beta", "bar", "frac", "phantom",
        "color", "middle", "vert", "Vert",
    }

CONTROL_TYPES = {"range", "number", "toggle", "select", "vector", "matrix", "presets"}
_BLOCK_RE = re.compile(r"```[ \t]*([A-Za-z]*)[^\n]*\n(.*?)(?:\n[ \t]*```|\Z)", re.S)


class ParseError(ValueError):
    pass


def extract_blocks(text: str) -> tuple[str | None, str | None]:
    """Return (json_text, js_text) from fenced blocks (tolerates a truncated last fence)."""
    json_text = js_text = None
    for lang, body in _BLOCK_RE.findall(text):
        lang = lang.lower()
        if lang == "json" and json_text is None:
            json_text = body
        elif lang in ("javascript", "js") and js_text is None:
            js_text = body
        elif not lang and json_text is None and body.lstrip().startswith("{"):
            json_text = body
    if json_text is None:
        # Unfenced JSON: only outside code fences, and only an object whose
        # first key is a quoted string (so JavaScript braces never match).
        bare = _BLOCK_RE.sub("", text)
        m = re.search(r"\{\s*\"", bare)
        if m:
            end = _match_brace(bare, m.start())
            if end > m.start():
                json_text = bare[m.start():end + 1]
    return json_text, js_text


def _match_brace(text: str, start: int) -> int:
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


_ESC_RE = re.compile(r"\\(\\|[A-Za-z]+|.)", re.S)


def repair_json(text: str) -> str:
    def fix(m: re.Match) -> str:
        tok = m.group(1)
        if tok == "\\":
            return m.group(0)  # already an escaped backslash
        if tok[0].isalpha():
            if tok in _TEX_NAMES:
                return "\\\\" + tok
            first = tok[0]
            if first in "bfnrt":
                return m.group(0)  # valid JSON escape followed by ordinary text
            if first == "u" and re.match(r"u[0-9a-fA-F]{4}", tok):
                return m.group(0)
            return "\\\\" + tok
        if tok in '"/':
            return m.group(0)
        return "\\\\" + tok
    text = re.sub(r"(?m)^\s*//[^\n]*$", "", text)  # whole-line // comments
    text = _ESC_RE.sub(fix, text)
    text = re.sub(r",\s*([}\]])", r"\1", text)  # trailing commas
    return text


def parse_spec(json_text: str) -> dict[str, Any]:
    errors = []
    for candidate in (repair_json(json_text), json_text):
        try:
            data = json.loads(candidate, strict=False)
            if not isinstance(data, dict):
                raise ParseError("spec JSON is not an object")
            return data
        except json.JSONDecodeError as exc:
            errors.append(f"{exc.msg} at line {exc.lineno} col {exc.colno}")
    raise ParseError("spec JSON could not be parsed: " + errors[0])


# --------------------------------------------------------------- validation
def _num(x, default=None):
    try:
        v = float(x)
        return v if v == v and v not in (float("inf"), float("-inf")) else default
    except (TypeError, ValueError):
        return default


def _as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _text(x) -> str:
    if x is None:
        return ""
    if isinstance(x, list):
        return "\n\n".join(_text(i) for i in x)
    if isinstance(x, dict):
        return " ".join(_text(v) for v in x.values())
    return str(x)


def normalize_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    """Return (spec, errors, fixes). Errors need the model; fixes were applied here."""
    errors: list[str] = []
    fixes: list[str] = []
    s = dict(spec)

    for key in ("title", "hook", "idea", "why", "visual_caption"):
        s[key] = _text(s.get(key)).strip()
    for key in ("title", "idea", "why"):
        if not s[key]:
            errors.append(f"spec.{key} is missing or empty")

    s["equations"] = [e if isinstance(e, dict) else {"tex": _text(e)} for e in _as_list(s.get("equations"))]
    s["equations"] = [e for e in s["equations"] if _text(e.get("tex")).strip()]
    if not s["equations"]:
        errors.append("spec.equations is empty: give the key equation(s) from the excerpt")

    s["symbols"] = [x for x in _as_list(s.get("symbols")) if isinstance(x, dict) and _text(x.get("symbol")).strip()]
    if len(s["symbols"]) < 2:
        errors.append("spec.symbols must define the main symbols (at least 2)")

    # ---- controls
    controls, seen = [], set()
    for i, c in enumerate(_as_list(s.get("controls"))):
        if not isinstance(c, dict):
            errors.append(f"controls[{i}] is not an object")
            continue
        c = dict(c)
        cid = str(c.get("id") or "").strip()
        ctype = str(c.get("type") or "").strip().lower()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cid):
            errors.append(f"controls[{i}].id {cid!r} must be a simple identifier")
            continue
        if cid in seen:
            errors.append(f"duplicate control id {cid!r}")
            continue
        seen.add(cid)
        if ctype in ("slider",):
            ctype = "range"
        if ctype in ("checkbox", "boolean", "switch"):
            ctype = "toggle"
        if ctype in ("buttons", "quick", "setups", "preset"):
            ctype = "presets"
        if ctype not in CONTROL_TYPES:
            errors.append(f"control {cid!r} has unsupported type {ctype!r}")
            continue
        c["id"], c["type"] = cid, ctype
        c["label"] = _text(c.get("label")).strip() or cid
        problem = _normalize_control(c, fixes)
        if problem:
            errors.append(f"control {cid!r}: {problem}")
            continue
        controls.append(c)
    ids = {c["id"] for c in controls if c["type"] != "presets"}  # controls that hold state
    for c in [c for c in controls if c["type"] == "presets"]:
        kept = []
        for o in c["options"]:
            unknown = [k for k in o["set"] if k not in ids]
            if unknown:
                fixes.append(f"control {c['id']!r}: dropped unknown ids {unknown} from button {o['label']!r}")
            o = {"label": o["label"], "set": {k: v for k, v in o["set"].items() if k in ids}}
            if o["set"]:
                kept.append(o)
        if kept:
            c["options"] = kept
        else:
            errors.append(f"presets control {c['id']!r} has no button that sets an existing control")
            controls.remove(c)
    s["controls"] = controls
    for c in controls:
        for dim in ("length", "rows", "cols"):
            ref = c.get(dim)
            if isinstance(ref, str) and ref not in ids:
                errors.append(f"control {c['id']!r}: {dim} refers to unknown control {ref!r}")
    if len(ids) < 2:
        errors.append(f"need at least 2 valid input controls (presets buttons do not count), found {len(ids)}")

    # ---- explorations
    exps = [e for e in _as_list(s.get("explorations")) if isinstance(e, dict)]
    if len(exps) > 2:
        fixes.append(f"kept first 2 of {len(exps)} explorations")
        exps = exps[:2]
    if len(exps) < 2:
        errors.append(f"need exactly 2 guided explorations, found {len(exps)}")
    for j, e in enumerate(exps):
        for key in ("title", "change", "observe", "why"):
            e[key] = _text(e.get(key)).strip()
            if not e[key]:
                errors.append(f"explorations[{j}].{key} is empty")
        preset = e.get("preset")
        if preset is not None and not isinstance(preset, dict):
            errors.append(f"explorations[{j}].preset must be an object of control values")
            preset = None
        if preset:
            unknown = [k for k in preset if k not in ids]
            if unknown:
                fixes.append(f"explorations[{j}].preset: dropped unknown control ids {unknown}")
                preset = {k: v for k, v in preset.items() if k in ids}
        e["preset"] = preset or None
    s["explorations"] = exps

    # ---- pitfall / grounding
    p = s.get("pitfall") if isinstance(s.get("pitfall"), dict) else {"text": _text(s.get("pitfall"))}
    p["kind"] = _text(p.get("kind")).strip() or "Limitation"
    p["title"] = _text(p.get("title")).strip()
    p["text"] = _text(p.get("text")).strip()
    if not p["text"]:
        errors.append("spec.pitfall.text is empty (need one limitation, assumption or misconception)")
    s["pitfall"] = p

    g = s.get("grounding") if isinstance(s.get("grounding"), dict) else {}
    g["paper"] = _text(g.get("paper")).strip()
    g["section"] = _text(g.get("section")).strip()
    g["from_source"] = [_text(x).strip() for x in _as_list(g.get("from_source")) if _text(x).strip()]
    g["our_additions"] = [_text(x).strip() for x in _as_list(g.get("our_additions")) if _text(x).strip()]
    g["disclaimer"] = _text(g.get("disclaimer")).strip()
    if not g["section"]:
        errors.append("grounding.section is empty: name the section/equation")
    if not g["from_source"]:
        errors.append("grounding.from_source is empty")
    if not g["our_additions"]:
        errors.append("grounding.our_additions is empty: list your simplifications/examples")
    s["grounding"] = g

    s["tests"] = [t for t in _as_list(s.get("tests")) if isinstance(t, dict)]
    s["plan"] = s.get("plan") if isinstance(s.get("plan"), dict) else {}
    all_ids = {c["id"] for c in s["controls"]}
    s["coverage"], s["coverage_warnings"] = check_coverage(s["plan"].get("coverage"), all_ids, len(exps))
    return s, errors, fixes


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def check_coverage(coverage, control_ids: set[str], n_explorations: int) -> tuple[list[dict], list[str]]:
    """Validate plan.coverage (each required outcome of the brief -> where the page delivers it).

    The map is planning evidence, not page content, so problems are warnings:
    near-miss control ids (e.g. "d_k" for "dk") are corrected, the rest logged."""
    items = [c for c in _as_list(coverage) if isinstance(c, dict) and _text(c.get("outcome")).strip()]
    if not items:
        return [], ["plan.coverage is empty: the brief's outcomes were not listed"]
    by_key = {_key(i): i for i in control_ids}
    warnings, out = [], []
    for c in items:
        outcome = _text(c.get("outcome")).strip()
        where = []
        for w in (str(w).strip() for w in _as_list(c.get("where")) if str(w).strip()):
            kind, _, ref = w.partition(":")
            kind, ref = kind.strip().lower(), ref.strip()
            if kind == "control" and ref and ref not in control_ids:
                if _key(ref) in by_key:
                    w = f"control:{by_key[_key(ref)]}"
                else:
                    warnings.append(f"outcome '{outcome[:60]}' refers to unknown control '{ref}'")
                    continue
            if kind == "exploration" and ref and (not ref.isdigit() or not 1 <= int(ref) <= n_explorations):
                warnings.append(f"outcome '{outcome[:60]}' refers to unknown exploration '{ref}'")
                continue
            where.append(w)
        if not where:
            warnings.append(f"outcome '{outcome[:60]}' has no valid place where it is delivered")
        out.append({"outcome": outcome, "where": where})
    return out, warnings


def _normalize_control(c: dict, fixes: list[str]) -> str | None:
    t = c["type"]
    if t == "presets":
        opts = []
        for o in _as_list(c.get("options")):
            if isinstance(o, dict) and isinstance(o.get("set"), dict) and o["set"]:
                opts.append({"label": _text(o.get("label")).strip() or "Set up", "set": o["set"]})
        if not opts:
            return 'presets needs options like [{"label": "...", "set": {"controlId": value}}]'
        c["options"] = opts
        c.pop("value", None)
        return None
    if t in ("range", "number"):
        lo, hi = _num(c.get("min")), _num(c.get("max"))
        if t == "range" and (lo is None or hi is None):
            return "range needs numeric min and max"
        if lo is not None and hi is not None and lo >= hi:
            return f"min ({lo}) must be < max ({hi})"
        c["min"], c["max"] = lo, hi
        step = _num(c.get("step"))
        c["step"] = step if step and step > 0 else (1 if t == "number" and lo is not None and float(lo).is_integer() else None)
        v = _num(c.get("value"), lo if lo is not None else 0)
        v = _clamp(v, lo, hi, c, fixes)
        c["value"] = v
    elif t == "toggle":
        c["value"] = bool(c.get("value"))
    elif t == "select":
        opts = []
        for o in _as_list(c.get("options")):
            if isinstance(o, dict) and "value" in o:
                opts.append({"value": o["value"], "label": _text(o.get("label", o["value"]))})
            elif not isinstance(o, (dict, list)):
                opts.append({"value": o, "label": str(o)})
        if len(opts) < 2:
            return "select needs at least 2 options"
        c["options"] = opts
        values = [o["value"] for o in opts]
        if c.get("value") not in values:
            fixes.append(f"control {c['id']!r}: default value not in options, using first option")
            c["value"] = values[0]
    elif t == "vector":
        val = c.get("value")
        if not isinstance(val, list) or not val:
            return "vector needs a non-empty numeric list value"
        nums = [_num(x) for x in val]
        if any(x is None for x in nums):
            return "vector value must contain only numbers"
        lo, hi = _num(c.get("min")), _num(c.get("max"))
        c["min"], c["max"] = lo, hi
        c["value"] = [_clamp(x, lo, hi, c, fixes) for x in nums]
        if not isinstance(c.get("length"), str):
            c["length"] = len(c["value"])
    elif t == "matrix":
        val = c.get("value")
        if not isinstance(val, list) or not val or not all(isinstance(r, list) and r for r in val):
            return "matrix needs a non-empty 2D numeric value"
        width = len(val[0])
        if any(len(r) != width for r in val):
            return "matrix rows must all have the same length"
        rows = [[_num(x) for x in r] for r in val]
        if any(x is None for r in rows for x in r):
            return "matrix value must contain only numbers"
        lo, hi = _num(c.get("min")), _num(c.get("max"))
        c["min"], c["max"] = lo, hi
        c["value"] = [[_clamp(x, lo, hi, c, fixes) for x in r] for r in rows]
        if not isinstance(c.get("rows"), str):
            c["rows"] = len(rows)
        if not isinstance(c.get("cols"), str):
            c["cols"] = width
    return None


def _clamp(v, lo, hi, c, fixes):
    if lo is not None and v < lo:
        fixes.append(f"control {c['id']!r}: value {v} raised to min {lo}")
        return lo
    if hi is not None and v > hi:
        fixes.append(f"control {c['id']!r}: value {v} lowered to max {hi}")
        return hi
    return v


def merge_revision(spec: dict, code: str, reply: str) -> tuple[dict, str, list[str], str | None]:
    """Apply a revision reply (partial spec keys and/or full code).

    Returns (spec, code, changed, json_error). A malformed spec patch does not
    discard a valid code block in the same reply."""
    json_text, js_text = extract_blocks(reply)
    changed: list[str] = []
    json_error = None
    if json_text and json_text.strip():
        try:
            patch = parse_spec(json_text)
        except ParseError as exc:
            json_error = str(exc)
            patch = {}
        for k, v in patch.items():
            spec[k] = v
            changed.append(f"spec.{k}")
    if js_text and js_text.strip():
        code = js_text
        changed.append("code")
    return spec, code, changed, json_error
