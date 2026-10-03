"""Deterministic checks on the generated spec, code and page.

Every check is logged to the trace with its outcome. Problems are phrased as
instructions the model can act on in a revision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .jsrun import execute
from .parse import normalize_spec

REQUIRED_FUNCTIONS = ("compute", "render", "show", "checks")
FORBIDDEN_CODE = [
    (r"\bfetch\s*\(", "uses fetch(); the page must work offline"),
    (r"\bXMLHttpRequest\b", "uses XMLHttpRequest; the page must work offline"),
    (r"^\s*import\s", "uses import; write plain script code"),
    (r"\brequire\s*\(", "uses require(); write plain script code"),
    (r"\bdocument\s*\.", "touches document; functions must be pure (the template owns the DOM)"),
    (r"\bMath\.random\s*\(", "uses Math.random(); results must be deterministic"),
    (r"https?://(?!www\.w3\.org/)", "contains a URL; the page must not load anything from the network"),
    (r"\b(?:const|let|var)\s+PG\b|\bfunction\s+PG\b|[(,]\s*PG\s*[,)=]|(?<![.\w])PG\s*=[^=]",
     "declares or reassigns a variable named PG, which hides the helper library PG: rename that variable"),
]


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    critical: bool = False


def static_code_problems(code: str) -> list[str]:
    problems = []
    if not code.strip():
        return ["the javascript block is missing or empty"]
    for name in REQUIRED_FUNCTIONS:
        if not re.search(rf"\bfunction\s+{name}\s*\(|\b(?:const|let|var)\s+{name}\s*=", code):
            problems.append(f"code must define a top-level function {name}()")
    for pattern, msg in FORBIDDEN_CODE:
        if re.search(pattern, code, re.M):
            problems.append(f"code {msg}")
    return problems


def run_all(spec: dict, code: str, trace, final: bool = False) -> Report:
    stage = "final_check" if final else "check"
    report = Report()
    normalized, spec_errors, _ = normalize_spec(dict(spec.get("_raw", spec)))
    trace.log(stage, "spec_structure", "pass" if not spec_errors else "fail", problems=spec_errors)
    warnings = normalized.get("coverage_warnings", [])
    trace.log(stage, "brief_coverage", "pass" if not warnings else "warning",
              outcomes=len(normalized.get("coverage", [])), coverage=normalized.get("coverage", []),
              warnings=warnings)
    report.problems += spec_errors

    code_problems = static_code_problems(code)
    trace.log(stage, "code_static", "pass" if not code_problems else "fail", problems=code_problems)
    report.problems += code_problems
    if any("must define" in p or "missing" in p for p in code_problems):
        report.critical = True

    if not spec_errors or spec.get("controls"):
        ex = execute(spec, code)
        if ex.engine == "unavailable":
            trace.log(stage, "js_execute", "skipped", reason="JavaScript engine (mini-racer) not importable")
        else:
            trace.log(stage, "js_execute", "pass" if not ex.problems else "fail",
                      states_tested=ex.states_tested, live_checks_evaluated=ex.checks_seen,
                      control_effects=ex.control_effects, critical=ex.critical, problems=ex.problems)
            if ex.tests:
                passed = sum(1 for t in ex.tests if t["passed"])
                trace.log(stage, "known_answer_tests", "pass" if passed == len(ex.tests) else "fail",
                          passed=passed, total=len(ex.tests), tests=ex.tests)
            report.problems += [p for p in ex.problems if p not in report.problems]
            report.critical = report.critical or ex.critical
    return report


_EXTERNAL_RE = re.compile(
    r"<(?:script|img|link|iframe|source|video|audio|embed|object)\b[^>]*\b(?:src|href|data)\s*=\s*[\"']?\s*(?:https?:)?//"
    r"|@import|url\(\s*[\"']?\s*(?:https?:)?//",
    re.I,
)
REQUIRED_IDS = ("idea", "symbols", "p2p-playground", "p2p-controls", "p2p-visual", "p2p-values",
                "p2p-checks", "explore", "caveat", "grounding")


def check_page(page: str, trace) -> list[str]:
    problems = []
    if _EXTERNAL_RE.search(page):
        problems.append("page references an external resource")
    for pid in REQUIRED_IDS:
        if f'id="{pid}"' not in page:
            problems.append(f"page is missing the #{pid} section")
    if "{{" in page and re.search(r"\{\{[A-Z_]+\}\}", page):
        problems.append("page has an unfilled template placeholder")
    trace.log("final_check", "page_static", "pass" if not problems else "fail",
              problems=problems, html_chars=len(page))
    return problems
