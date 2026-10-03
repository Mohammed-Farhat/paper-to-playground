"""Small TeX -> MathML converter (build time, no dependencies).

Chromium renders MathML Core natively, so equations need no CDN, fonts or
JavaScript. Supports the subset of LaTeX that appears in paper equations:
scripts, fractions, roots, Greek letters, big operators, accents, font
commands, \\left/\\right fences, \\text, matrices/cases environments.
Anything unrecognised degrades to readable text instead of failing.
"""

from __future__ import annotations

import html
import re

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "varpi": "ϖ", "rho": "ρ",
    "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "ϕ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ",
    "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ",
    "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω", "ell": "ℓ", "hbar": "ℏ", "imath": "ı",
}
SYMBOLS = {
    "cdot": "⋅", "times": "×", "div": "÷", "pm": "±", "mp": "∓", "le": "≤", "leq": "≤",
    "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠", "approx": "≈", "equiv": "≡", "sim": "∼",
    "simeq": "≃", "cong": "≅", "propto": "∝", "to": "→", "rightarrow": "→", "leftarrow": "←",
    "gets": "←", "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔", "implies": "⇒",
    "iff": "⇔", "leftrightarrow": "↔", "mapsto": "↦", "uparrow": "↑", "downarrow": "↓",
    "infty": "∞", "partial": "∂", "nabla": "∇", "in": "∈", "notin": "∉", "ni": "∋",
    "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "cup": "∪", "cap": "∩", "forall": "∀",
    "exists": "∃", "ldots": "…", "dots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱",
    "odot": "⊙", "otimes": "⊗", "oplus": "⊕", "circ": "∘", "ast": "∗", "star": "⋆",
    "top": "⊤", "intercal": "⊺", "perp": "⊥", "bot": "⊥", "mid": "∣", "parallel": "∥",
    "langle": "⟨", "rangle": "⟩", "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
    "prime": "′", "neg": "¬", "lnot": "¬", "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨",
    "setminus": "∖", "emptyset": "∅", "varnothing": "∅", "colon": ":", "gg": "≫", "ll": "≪",
    "triangleq": "≜", "coloneqq": "≔", "vert": "|", "Vert": "‖", "lvert": "|", "rvert": "|",
    "lVert": "‖", "rVert": "‖", "bullet": "∙", "angle": "∠", "degree": "°", "dagger": "†",
    "aleph": "ℵ", "Re": "ℜ", "Im": "ℑ", "wp": "℘", "checkmark": "✓", "cdotp": "⋅",
    "lbrace": "{", "rbrace": "}", "lbrack": "[", "rbrack": "]", "backslash": "∖",
}
BIG_OPS = {"sum": "∑", "prod": "∏", "coprod": "∐", "int": "∫", "iint": "∬", "oint": "∮",
           "bigcup": "⋃", "bigcap": "⋂", "bigoplus": "⨁", "bigotimes": "⨂"}
FUNCTIONS = {"log", "ln", "exp", "sin", "cos", "tan", "sec", "csc", "cot", "sinh", "cosh",
             "tanh", "arcsin", "arccos", "arctan", "max", "min", "arg", "det", "dim", "sup",
             "inf", "lim", "limsup", "liminf", "gcd", "deg", "ker", "Pr", "hom", "mod",
             "sgn", "argmax", "argmin", "softmax", "diag", "tr", "rank", "var", "Var",
             "Cov", "cov", "erf", "sign", "relu", "ReLU"}
LIMIT_FUNCS = {"lim", "max", "min", "sup", "inf", "argmax", "argmin", "limsup", "liminf"}
ACCENTS = {"hat": "^", "widehat": "^", "bar": "¯", "overline": "‾", "vec": "→",
           "overrightarrow": "→", "tilde": "~", "widetilde": "~", "dot": "˙", "ddot": "¨",
           "check": "ˇ", "breve": "˘"}
SPACES = {",": "0.1667em", ":": "0.2222em", ";": "0.2778em", "!": "0em", " ": "0.25em",
          "quad": "1em", "qquad": "2em", "enspace": "0.5em", "thinspace": "0.1667em"}
BLACKBOARD = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ", "E": "𝔼", "P": "ℙ"}
IGNORED = {"displaystyle", "textstyle", "scriptstyle", "limits", "nolimits", "nonumber",
           "notag", "left.", "right.", "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl",
           "Bigr", "biggl", "biggr", "Biggl", "Biggr", "middle"}
ARG_IGNORED = {"label", "tag", "color", "hspace", "vspace", "phantom"}
FONT_CMDS = {"mathbf": "bold", "boldsymbol": "bold", "bm": "bold", "mathrm": "normal",
             "mathit": "italic", "mathsf": "normal", "mathtt": "normal", "mathcal": "normal",
             "mathscr": "normal", "mathfrak": "normal", "operatorname": "normal"}
TEXT_CMDS = {"text", "textrm", "textit", "textbf", "mbox", "textsf", "texttt", "mathtext"}
MATRIX_FENCES = {"matrix": ("", ""), "pmatrix": ("(", ")"), "bmatrix": ("[", "]"),
                 "Bmatrix": ("{", "}"), "vmatrix": ("|", "|"), "Vmatrix": ("‖", "‖"),
                 "smallmatrix": ("", ""), "array": ("", ""), "cases": ("{", ""),
                 "aligned": ("", ""), "align": ("", ""), "align*": ("", ""), "gathered": ("", ""),
                 "split": ("", ""), "equation": ("", ""), "equation*": ("", "")}

_TOKEN_RE = re.compile(r"\\([a-zA-Z]+\*?|.)|(\d+(?:\.\d+)?)|(\s+)|(.)", re.S)


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


class _Parser:
    def __init__(self, tex: str):
        self.toks: list[tuple[str, str]] = []
        for m in _TOKEN_RE.finditer(tex):
            if m.group(1) is not None:
                self.toks.append(("cmd", m.group(1)))
            elif m.group(2) is not None:
                self.toks.append(("num", m.group(2)))
            elif m.group(3) is not None:
                continue
            else:
                self.toks.append(("chr", m.group(4)))
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    # expression = sequence of atoms until '}' / \right / end
    def expr(self, stop_right: bool = False) -> str:
        out = []
        while self.i < len(self.toks):
            kind, val = self.peek()
            if kind == "chr" and val == "}":
                break
            if stop_right and kind == "cmd" and val == "right":
                break
            atom = self.atom()
            if atom is None:
                continue
            out.append(self.scripts(atom))
        return "".join(out)

    def group(self) -> str:
        """Parse a mandatory argument: {...} or a single token."""
        kind, val = self.peek()
        if kind == "chr" and val == "{":
            self.next()
            inner = self.expr()
            if self.peek() == ("chr", "}"):
                self.next()
            return f"<mrow>{inner}</mrow>"
        atom = self.atom()
        return atom if atom is not None else "<mrow></mrow>"

    def raw_group(self) -> str:
        """Return the raw token text of a {...} argument (for \\text etc.)."""
        if self.peek() != ("chr", "{"):
            kind, val = self.next()
            return val or ""
        self.next()
        depth, parts = 1, []
        while self.i < len(self.toks):
            kind, val = self.next()
            if kind == "chr" and val == "{":
                depth += 1
            elif kind == "chr" and val == "}":
                depth -= 1
                if depth == 0:
                    break
            parts.append("\\" + val + (" " if val.isalpha() else "") if kind == "cmd" else val)
        return "".join(parts)

    def optional(self) -> str | None:
        if self.peek() == ("chr", "["):
            self.next()
            out = []
            while self.i < len(self.toks) and self.peek() != ("chr", "]"):
                atom = self.atom()
                if atom is not None:
                    out.append(self.scripts(atom))
            self.next()
            return "<mrow>" + "".join(out) + "</mrow>"
        return None

    def scripts(self, base: str, limits: bool = False) -> str:
        sub = sup = None
        while True:
            kind, val = self.peek()
            if kind == "chr" and val == "_" and sub is None:
                self.next()
                sub = self.group()
            elif kind == "chr" and val == "^" and sup is None:
                self.next()
                sup = self.group()
            elif kind == "chr" and val == "'" and sup is None:
                self.next()
                primes = "′"
                while self.peek() == ("chr", "'"):
                    self.next()
                    primes += "′"
                sup = f"<mo>{primes}</mo>"
            else:
                break
        if sub is None and sup is None:
            return base
        if limits:
            if sub is not None and sup is not None:
                return f"<munderover>{base}{sub}{sup}</munderover>"
            if sub is not None:
                return f"<munder>{base}{sub}</munder>"
            return f"<mover>{base}{sup}</mover>"
        if sub is not None and sup is not None:
            return f"<msubsup>{base}{sub}{sup}</msubsup>"
        if sub is not None:
            return f"<msub>{base}{sub}</msub>"
        return f"<msup>{base}{sup}</msup>"

    def fence_token(self) -> str:
        kind, val = self.next()
        if kind is None:
            return ""
        if kind == "cmd":
            if val in ("{", "}", "|"):
                return {"|": "‖"}.get(val, val)
            if val == ".":
                return ""
            return SYMBOLS.get(val, "")
        return "" if val == "." else val

    def atom(self) -> str | None:
        kind, val = self.next()
        if kind is None:
            return None
        if kind == "num":
            return f"<mn>{val}</mn>"
        if kind == "chr":
            if val == "{":
                inner = self.expr()
                if self.peek() == ("chr", "}"):
                    self.next()
                return f"<mrow>{inner}</mrow>"
            if val in "^_":
                # dangling script: attach to an empty base
                self.i -= 1
                return self.scripts("<mrow></mrow>")
            if val == "&":
                return "<mspace width=\"1em\"></mspace>"
            if val.isalpha():
                return f"<mi>{_esc(val)}</mi>"
            if val == "-":
                return "<mo>−</mo>"
            if val == "~":
                return "<mspace width=\"0.25em\"></mspace>"
            if val == "'":
                return "<mo>′</mo>"
            return f"<mo>{_esc(val)}</mo>"
        return self.command(val)

    def command(self, name: str) -> str | None:
        star = name.endswith("*")
        base_name = name.rstrip("*")
        if name in GREEK:
            return f"<mi>{GREEK[name]}</mi>"
        if name in SYMBOLS:
            return f"<mo>{SYMBOLS[name]}</mo>"
        if name in SPACES:
            return f"<mspace width=\"{SPACES[name]}\"></mspace>"
        if name in ("{", "}", "%", "$", "#", "&", "_", "|"):
            return f"<mo>{_esc({'|': '‖'}.get(name, name))}</mo>"
        if name == "\\":
            return "<mspace width=\"1em\"></mspace>"
        if name in BIG_OPS:
            return self.scripts(f"<mo movablelimits=\"true\">{BIG_OPS[name]}</mo>", limits=True)
        if name in FUNCTIONS:
            limits = name in LIMIT_FUNCS
            label = {"argmax": "arg max", "argmin": "arg min"}.get(name, name)
            op = f"<mo movablelimits=\"true\" form=\"prefix\">{_esc(label)}</mo>" if limits \
                else f"<mi mathvariant=\"normal\">{_esc(label)}</mi>"
            return self.scripts(op, limits=limits) + "<mspace width=\"0.1667em\"></mspace>"
        if base_name in ("frac", "dfrac", "tfrac", "cfrac"):
            num = self.group()
            den = self.group()
            return f"<mfrac>{num}{den}</mfrac>"
        if base_name == "binom":
            top = self.group()
            bot = self.group()
            return f"<mrow><mo>(</mo><mfrac linethickness=\"0\">{top}{bot}</mfrac><mo>)</mo></mrow>"
        if name == "sqrt":
            idx = self.optional()
            body = self.group()
            return f"<mroot>{body}{idx}</mroot>" if idx else f"<msqrt>{body}</msqrt>"
        if name in ACCENTS:
            body = self.group()
            return f"<mover accent=\"true\">{body}<mo>{ACCENTS[name]}</mo></mover>"
        if name in ("underline", "underbrace"):
            body = self.group()
            under = "<mo>_</mo>" if name == "underline" else "<mo>⏟</mo>"
            return self.scripts(f"<munder>{body}{under}</munder>", limits=True)
        if name == "overbrace":
            body = self.group()
            return self.scripts(f"<mover>{body}<mo>⏞</mo></mover>", limits=True)
        if name in ("overset", "stackrel"):
            over = self.group()
            body = self.group()
            return f"<mover>{body}{over}</mover>"
        if name == "underset":
            under = self.group()
            body = self.group()
            return f"<munder>{body}{under}</munder>"
        if base_name in TEXT_CMDS:
            txt = self.raw_group()
            weight = " style=\"font-weight:bold\"" if base_name == "textbf" else ""
            return f"<mtext{weight}>{_esc(txt)}</mtext>"
        if base_name == "operatorname":
            txt = self.raw_group().replace("\\", "").strip()
            limits = star or txt in LIMIT_FUNCS
            if limits:
                return self.scripts(f"<mo movablelimits=\"true\" form=\"prefix\">{_esc(txt)}</mo>", limits=True)
            return self.scripts(f"<mi mathvariant=\"normal\">{_esc(txt)}</mi>")
        if base_name == "mathbb":
            txt = self.raw_group().strip()
            return f"<mi mathvariant=\"normal\">{_esc(''.join(BLACKBOARD.get(c, c) for c in txt))}</mi>"
        if base_name in FONT_CMDS:
            style = FONT_CMDS[base_name]
            if style == "normal":
                save = self.i
                raw = self.raw_group().strip()
                if re.fullmatch(r"[A-Za-z][A-Za-z ]*", raw):
                    return self.scripts(f"<mi mathvariant=\"normal\">{_esc(raw)}</mi>")
                self.i = save
            body = self.group()
            if style == "bold":
                return f"<mrow style=\"font-weight:bold\">{body}</mrow>"
            if style == "normal":
                body = body.replace("<mi>", "<mi mathvariant=\"normal\">")
            return body
        if name == "mathop":
            return self.scripts(self.group(), limits=True)
        if name == "left":
            open_f = self.fence_token()
            inner = self.expr(stop_right=True)
            close_f = ""
            if self.peek() == ("cmd", "right"):
                self.next()
                close_f = self.fence_token()
            o = f"<mo fence=\"true\" stretchy=\"true\">{_esc(open_f)}</mo>" if open_f else ""
            c = f"<mo fence=\"true\" stretchy=\"true\">{_esc(close_f)}</mo>" if close_f else ""
            return f"<mrow>{o}{inner}{c}</mrow>"
        if name == "right":
            self.fence_token()
            return None
        if name in ("bigl", "bigr", "Bigl", "Bigr", "big", "Big", "bigg", "Bigg", "biggl", "biggr"):
            f = self.fence_token()
            return f"<mo>{_esc(f)}</mo>" if f else None
        if name in IGNORED:
            return None
        if name in ARG_IGNORED:
            self.raw_group()
            return None
        if name == "begin":
            return self.environment()
        if name == "end":
            self.raw_group()
            return None
        # Unknown command: show its name upright so the reader still sees it.
        return f"<mi mathvariant=\"normal\">{_esc(base_name)}</mi>"

    def environment(self) -> str:
        env = self.raw_group().strip()
        if env == "array" and self.peek() == ("chr", "{"):
            self.raw_group()  # column spec
        # collect tokens until the matching \end{env}
        depth, body = 1, []
        while self.i < len(self.toks):
            kind, val = self.next()
            if kind == "cmd" and val == "begin":
                depth += 1
            elif kind == "cmd" and val == "end":
                depth -= 1
                if depth == 0:
                    self.raw_group()
                    break
            body.append((kind, val))
        rows: list[list[list[tuple[str, str]]]] = [[[]]]
        brace = 0
        for kind, val in body:
            if kind == "chr" and val == "{":
                brace += 1
            elif kind == "chr" and val == "}":
                brace -= 1
            if brace == 0 and kind == "cmd" and val == "\\":
                rows.append([[]])
                continue
            if brace == 0 and kind == "chr" and val == "&":
                rows[-1].append([])
                continue
            rows[-1][-1].append((kind, val))
        if rows and rows[-1] == [[]]:
            rows.pop()
        align = "left" if env in ("cases", "aligned", "align", "align*", "split") else "center"
        trs = []
        for row in rows:
            tds = []
            for cell in row:
                sub = _Parser("")
                sub.toks = cell
                tds.append(f"<mtd style=\"text-align:{align}\"><mrow>{sub.expr()}</mrow></mtd>")
            trs.append("<mtr>" + "".join(tds) + "</mtr>")
        table = "<mtable>" + "".join(trs) + "</mtable>"
        o, c = MATRIX_FENCES.get(env, ("", ""))
        if o or c:
            of = f"<mo fence=\"true\" stretchy=\"true\">{_esc(o)}</mo>" if o else ""
            cf = f"<mo fence=\"true\" stretchy=\"true\">{_esc(c)}</mo>" if c else ""
            return f"<mrow>{of}{table}{cf}</mrow>"
        return table


def tex_to_mathml(tex: str, display: bool = False) -> str:
    """Convert a TeX string to a <math> element; falls back to escaped text."""
    tex = (tex or "").strip()
    try:
        parser = _Parser(tex)
        parts = [parser.expr()]
        while parser.i < len(parser.toks):  # skip stray closing braces
            parser.next()
            parts.append(parser.expr())
        attr = ' display="block"' if display else ""
        return f"<math{attr} aria-label=\"{html.escape(tex)}\"><mrow>{''.join(parts)}</mrow></math>"
    except Exception:  # defensive: never fail the build because of an equation
        return f"<code class=\"p2p-tex\">{_esc(tex)}</code>"


_MATH_RE = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]|\\\((.+?)\\\)|\$([^$\n]+?)\$", re.S)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
_CODE_RE = re.compile(r"`([^`\n]+)`")
_BULLET_RE = re.compile(r"^([-*•]|\d+[.)])\s+")


def _inline(text: str) -> str:
    """Escape text, then render $math$, **bold** and `code`."""
    out, pos = [], 0
    for m in _MATH_RE.finditer(text):
        out.append(_plain(text[pos:m.start()]))
        if m.group(1) is not None or m.group(2) is not None:
            out.append(tex_to_mathml(m.group(1) or m.group(2), display=True))
        else:
            out.append(tex_to_mathml(m.group(3) or m.group(4), display=False))
        pos = m.end()
    out.append(_plain(text[pos:]))
    return "".join(out)


def _plain(text: str) -> str:
    s = _esc(text)
    s = _BOLD_RE.sub(r"<strong>\1</strong>", s)
    s = _CODE_RE.sub(r"<code>\1</code>", s)
    return s


def rich_inline(text) -> str:
    """Single-line rich text (no paragraphs)."""
    return _inline(str(text or "").replace("\n", " "))


def rich_text(text) -> str:
    """Multi-paragraph rich text: blank lines -> paragraphs, '- ' lines -> lists."""
    if isinstance(text, list):
        text = "\n\n".join(str(t) for t in text)
    text = str(text or "").strip()
    if not text:
        return ""
    blocks = re.split(r"\n\s*\n", text)
    out = []
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
        if lines and all(_BULLET_RE.match(ln) for ln in lines):
            ordered = bool(re.match(r"^\d+[.)]", lines[0]))
            items = "".join("<li>" + _inline(_BULLET_RE.sub("", ln)) + "</li>" for ln in lines)
            out.append(f"<ol>{items}</ol>" if ordered else f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{_inline(' '.join(lines))}</p>")
    return "".join(out)
