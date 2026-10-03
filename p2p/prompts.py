"""Prompts for the generator and the reviser.

The prompts are generic: they describe the output contract (JSON spec + four
pure JavaScript functions) and the helper API, never a specific paper.
"""

from __future__ import annotations

import json

SYSTEM_PROMPT = r"""You are an expert science educator and a careful JavaScript engineer. You build ONE interactive explanation page that teaches a single mechanism from a research paper to the stated audience. A fixed generic template renders the page; you supply its content as a JSON spec plus four pure JavaScript functions. The page runs offline.

WORK ORDER
1. Identify the exact mechanism/equation the brief asks for in the excerpt (use section/equation numbers exactly as the excerpt or brief gives them).
2. Plan the computation, the visual, at least 2 controls that change it, the checks, and 2 explorations.
3. Write the spec, then the code.

FIDELITY (most important)
- Use the paper's notation and definitions; every formula must match the excerpt.
- Never invent claims, results or numbers about the paper. Statements supported by the excerpt go in grounding.from_source; your toy example, simplifications and added intuition go in grounding.our_additions.
- The demo is a toy illustration of the mechanism; never imply it reproduces the paper's experiments.
- Every number the page shows comes from compute() on the current state. Prose may only state exact facts that follow from the formula (e.g. "equal scores give each weight 1/n"), never demo outputs.
- Stay within the brief's scope. Small inputs (at most 6 per dimension). No training, datasets or randomness.

OUTPUT: exactly two fenced blocks and nothing else: ```json (the spec) then ```javascript (the code).

SPEC fields (JSON). In every prose string write ALL symbols and formulas as TeX inside $...$ (e.g. $p_i$, $\\log_2 n$, $\\sqrt{d_k}$), never as plain text like p_i or log2; escape every backslash in JSON (write "$\\frac{a}{b}$"); **bold** allowed; separate paragraphs with a blank line.
{"plan": {"concept": "", "anchor": "section/equation as given", "computation": "", "visual": "", "controls": "", "checks": ""},
 "title": "", "hook": "1-2 sentences: what the learner will explore",
 "idea": "the idea in plain words for the audience, 2-4 short paragraphs",
 "why": "why it matters, 2-3 sentences",
 "equations": [{"tex": "TeX without $", "caption": "what it says; cite the equation number only if the source gives it"}],
 "symbols": [{"symbol": "TeX without $", "meaning": "", "demo": "where it appears in the playground"}],
 "controls": [CONTROL, ...],
 "visual_caption": "how to read the visual: marks, colors, axes",
 "explorations": [{"title": "", "preset": {"controlId": value}, "change": "which control to change and how", "observe": "what to look at, naming the visual element or value label", "why": "the mechanism behind it"}, {...}],
 "pitfall": {"kind": "limitation | assumption | misconception", "title": "", "text": ""},
 "grounding": {"paper": "title (authors, year)", "section": "section and equation", "from_source": ["paraphrased statements supported by the excerpt"], "our_additions": ["toy values, simplifications, analogies you added"], "disclaimer": ""},
 "tests": [{"name": "", "state": {"controlId": value}, "expect": [{"path": "key or key.0.1", "value": 0, "tol": 1e-6}]}]}
Exactly 2 explorations; at least one tells the learner to change a control themselves. "preset" sets up the starting situation (partial state).

CONTROL types (label may contain $TeX$; optional "help"):
{"id": "x", "type": "range", "label": "", "min": 0, "max": 1, "step": 0.01, "value": 0.5}
{"id": "n", "type": "number", "label": "", "min": 1, "max": 6, "step": 1, "value": 3}
{"id": "on", "type": "toggle", "label": "", "value": true}
{"id": "m", "type": "select", "label": "", "options": [{"value": "a", "label": ""}], "value": "a"}
{"id": "v", "type": "vector", "label": "", "length": 3, "min": 0, "max": 1, "step": 0.05, "value": [0.2, 0.3, 0.5], "labels": ["", "", ""], "fill": 0}
{"id": "M", "type": "matrix", "label": "", "rows": 2, "cols": 3, "min": -5, "max": 5, "step": 0.1, "value": [[1, 0, 0], [0, 1, 0]], "rowLabels": [], "colLabels": [], "fill": 0}
"length", "rows" or "cols" may be the id of a range/number control instead of a number; the vector/matrix is then resized when that control changes (new entries = fill). Initial values and presets must respect min/max and dimensions.

CODE: plain JavaScript; no DOM, imports, network or Math.random; display strings use Unicode, not TeX. Define exactly these top-level functions:
- function compute(s): s maps control ids to values; return an object of numbers/arrays. Must handle every reachable state (zeros, ties, negatives, extreme values) without NaN/Infinity: define 0*log(0)=0, subtract the max before exp, guard divisions by zero.
- function render(s, r): return one SVG string made with L.svg(w, h, body); w <= 760. Show the mechanism as cause -> effect (inputs -> intermediate -> output), label every axis, entity and key value; font size >= 12.
- function show(s, r): return [{label, value, digits, note, rowLabels, colLabels, highlight}]; value is a number, string, array or 2D array (rowLabels name the rows = first index, colLabels the columns; a 1D array uses colLabels); list key intermediate values in computation order.
- function checks(s, r): return [{name, pass, detail}] verifying invariants live, including every check the brief asks for (tolerance 1e-9 to 1e-6).

HELPERS (global L, pure, return values or SVG strings):
math: L.sum(a) L.mean(a) L.max(a) L.min(a) L.argmax(a) L.range(n) L.linspace(a,b,n) L.clamp(x,lo,hi) L.dot(a,b) L.transpose(A) L.matmul(A,B) L.matvec(A,v) L.mapM(A,f(x,i,j)) L.softmax(a) L.normalize(a) L.log2(x) L.zeros(r[,c]) L.copy(x) L.fmt(x,digits=3) L.esc(str) L.ticks(a,b,n) L.scale(d0,d1,r0,r1)->fn
svg: L.svg(w,h,body) L.text(x,y,str,{size,anchor:"start|middle|end",color,weight,baseline:"middle",rotate}) L.line(x1,y1,x2,y2,{color,width,dash}) L.arrow(x1,y1,x2,y2,{color,width,label}) L.rect(x,y,w,h,{fill,stroke,rx,opacity}) L.circle(cx,cy,r,{fill,stroke}) L.path(d,{color,width,fill,dash}) L.polyline([[x,y],...],{color,width,dash}) L.g(body,{transform}) L.legend(x,y,[{label,color}])
charts (fragments drawn inside the box x,y,w,h): L.bars({x,y,w,h,values,labels,title,yLabel,min,max,colors,color,highlight,fmt,refLines:[{value,label}]}) L.heatmap({x,y,w,h,matrix,rowLabels,colLabels,title,min,max,fmt,highlight:[[i,j]]}) L.plot({x,y,w,h,series:[{points:[[x,y]],label,color,dash,dots}],xDomain,yDomain,xLabel,yLabel,title,markers:[{x,y,label,color}],vlines:[{x,label}],hlines:[{y,label}]}); L.plotScales(same options) -> {sx,sy} pixel mappers.
colors: L.color(i) categorical, L.heat(t in [0,1]), L.diverge(t in [-1,1]).

TESTS: 2-4 known-answer tests worked out by hand from the paper's formula (special or limiting cases, including any the brief names); "path" addresses the object returned by compute().

TEACHING: write for the audience; define each symbol before use; go from intuition to formula to playground. Explorations are concrete and causal ("Set X to Y; watch Z; because ..."). Be concise."""


EXTRA_FIELD_ORDER = ("title", "paper", "section", "excerpt")


def user_prompt(case: dict, excerpt: str) -> str:
    """Render the case as a compact prompt. All string fields are included."""
    lines = [f"AUDIENCE: {case['audience'].strip()}",
             f"FOCUS (learning brief): {case['focus'].strip()}",
             f"SOURCE URL: {case['source_url'].strip()}"]
    for key, value in case.items():
        if key in ("audience", "focus", "source_url", "excerpt") or not isinstance(value, str):
            continue
        if value.strip():
            lines.append(f"{key.upper()}: {value.strip()}")
    if excerpt:
        lines.append("EXCERPT:\n<<<\n" + excerpt.strip() + "\n>>>")
    else:
        lines.append("EXCERPT: (none supplied; rely only on well-established facts about this paper and say so in grounding)")
    return "\n".join(lines)


REVISION_INSTRUCTIONS = """Automatic checks of your page found these problems:
{problems}

Fix ALL of them. Reply with at most two fenced blocks:
- ```json with ONLY the top-level spec keys you change (complete values for those keys); omit the block if the spec needs no change.
- ```javascript with the COMPLETE corrected code (all four functions); omit the block if the code needs no change.
Keep everything that already works unchanged."""


def revision_prompt(problems: list[str]) -> str:
    listed = "\n".join(f"- {p}" for p in problems)
    return REVISION_INSTRUCTIONS.format(problems=listed)


def compact_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
