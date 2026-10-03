"""Agent pipeline: understand -> plan+generate -> check -> revise -> build.

One generation call returns a plan, the page spec and the code together (the
plan is written first, so the model commits to the mechanism before writing
content). Deterministic checks then validate the result; only when a check
fails is a targeted revision call made, carrying just the problem list.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import checks as checks_mod
from .build import build_page
from .llm import Budget, BudgetExceeded, LLMError, OpenRouterClient
from .parse import ParseError, extract_blocks, merge_revision, normalize_spec, parse_spec
from .prompts import SYSTEM_PROMPT, revision_prompt, user_prompt

GENERATION_MAX_TOKENS = 16_000
REVISION_MAX_TOKENS = 12_000
MAX_REVISIONS = 2
MAX_EXCERPT_CHARS = 24_000
EXCERPT_KEYS = ("excerpt", "passage", "source_text", "text", "content", "context", "section_text")


def reasoning_setting() -> dict[str, Any] | None:
    """Reasoning configuration sent to OpenRouter (reasoning text is always excluded)."""
    # Default "off": in our measurements reasoning tripled tokens and latency
    # (and exhausted max_tokens) without a visible quality gain. The variable
    # exists only for development experiments; no setup is needed to run.
    mode = os.environ.get("P2P_REASONING", "off").strip().lower()
    if mode in ("minimal", "low", "medium", "high"):
        return {"effort": mode, "exclude": True}
    return {"enabled": False}


@dataclass
class RunResult:
    ok: bool
    html: str
    spec: dict | None = None
    code: str = ""
    excerpt: str = ""
    problems: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- understand
def find_excerpt(case: dict) -> tuple[str, str | None]:
    for key in EXCERPT_KEYS:
        v = case.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip(), key
    for key, v in case.items():
        if isinstance(v, str) and re.search(r"excerpt|passage|text|content", key, re.I) and v.strip():
            return v.strip(), key
    skip = {"source_url", "focus", "audience"}
    longest = max(((k, v) for k, v in case.items() if k not in skip and isinstance(v, str)),
                  key=lambda kv: len(kv[1]), default=(None, ""))
    if longest[0] and len(longest[1]) > 300:
        return longest[1].strip(), longest[0]
    return "", None


def trim_excerpt(excerpt: str, focus: str, limit: int = MAX_EXCERPT_CHARS) -> tuple[str, bool]:
    """Keep the excerpt if it fits; otherwise keep the paragraphs most related to the focus."""
    if len(excerpt) <= limit:
        return excerpt, False
    words = {w for w in re.findall(r"[a-z]{4,}", focus.lower())}
    paras = [p for p in re.split(r"\n\s*\n", excerpt) if p.strip()]
    if len(paras) < 3:  # one huge block: split into sentence groups
        sents = re.split(r"(?<=[.!?])\s+", excerpt)
        paras = [" ".join(sents[i:i + 6]) for i in range(0, len(sents), 6)]
    scored = sorted(range(len(paras)),
                    key=lambda i: -sum(paras[i].lower().count(w) for w in words) / (1 + len(paras[i]) / 2000))
    keep, total = set(), 0
    for i in scored:
        if total + len(paras[i]) > limit:
            continue
        keep.add(i)
        total += len(paras[i])
    return "\n\n".join(paras[i] for i in sorted(keep)), True


# ------------------------------------------------------------------- run
def run(case: dict, model: str, api_key: str, out_dir: Path, trace, budget: Budget) -> RunResult:
    excerpt, excerpt_key = find_excerpt(case)
    excerpt, trimmed = trim_excerpt(excerpt, case.get("focus", ""))
    trace.log("understand", "prepare_source", "ok", excerpt_field=excerpt_key, excerpt_chars=len(excerpt),
              excerpt_trimmed=trimmed, fields=sorted(case.keys()))

    reasoning = reasoning_setting()
    client = OpenRouterClient(model, api_key, budget, trace, reasoning=reasoning, temperature=0.3)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(case, excerpt)}]
    trace.log("plan_generate", "request", "sent", reasoning=reasoning,
              prompt_chars=sum(len(m["content"]) for m in messages))

    reply = client.chat(messages, GENERATION_MAX_TOKENS, stage="plan_generate", purpose="plan + spec + code")
    spec, code, reply_problems = _parse_reply(reply.text, trace, reply.finish_reason)
    if spec and spec.get("plan"):
        trace.log("plan_generate", "plan", "ok", plan=spec["plan"])

    # Check -> revise loop. Each round sends only the problem list (plus the
    # previous reply, which the model needs to make a targeted fix).
    history = list(messages) + [{"role": "assistant", "content": reply.text}]
    revisions = 0
    while True:
        problems = list(reply_problems)
        if spec:
            problems += [p for p in checks_mod.run_all(spec, code, trace).problems if p not in problems]
        if not problems:
            break
        if revisions >= MAX_REVISIONS:
            trace.log("revise", "stop", "max_revisions_reached", remaining_problems=problems)
            break
        revisions += 1
        trace.log("revise", "request", "sent", revision=revisions, problems=problems)
        history.append({"role": "user", "content": revision_prompt(problems)})
        try:
            fix = client.chat(history, REVISION_MAX_TOKENS, stage="revise", purpose=f"revision {revisions}")
        except (BudgetExceeded, LLMError) as exc:
            trace.log("revise", "llm_call", "skipped", reason=str(exc))
            break
        history.append({"role": "assistant", "content": fix.text})
        if spec is None:
            spec, code, reply_problems = _parse_reply(fix.text, trace, fix.finish_reason)
            continue
        reply_problems = []
        if fix.finish_reason == "length":
            reply_problems.append("your reply was cut off by the token limit: be more concise")
        try:
            raw_spec, code, changed = merge_revision(dict(spec.get("_raw", spec)), code, fix.text)
        except ParseError as exc:
            reply_problems.append(str(exc))
            trace.log("revise", "apply", "error", revision=revisions, error=str(exc))
            continue
        spec, errors, fixes = normalize_spec(raw_spec)
        spec["_raw"] = raw_spec
        trace.log("revise", "apply", "ok", revision=revisions, changed=changed, auto_fixes=fixes)

    if spec is None:
        trace.log("build", "write_page", "failed", reason="no usable spec from the model", problems=problems)
        return RunResult(ok=False, html="", problems=problems)

    final = checks_mod.run_all(spec, code, trace, final=True)
    clean = {k: v for k, v in spec.items() if k != "_raw"}
    page = build_page(clean, code, case, excerpt)
    page_report = checks_mod.check_page(page, trace)
    remaining = reply_problems + final.problems + page_report
    ok = not final.critical and not page_report and not reply_problems
    trace.log("build", "write_page", "ok" if ok else "degraded", html_chars=len(page),
              revisions=revisions, remaining_problems=remaining)
    return RunResult(ok=ok, html=page, spec=clean, code=code, excerpt=excerpt, problems=remaining)


def _parse_reply(text: str, trace, finish_reason: str | None):
    json_text, js_text = extract_blocks(text)
    problems: list[str] = []
    if finish_reason == "length":
        problems.append("your reply was cut off by the token limit: be more concise")
    if not json_text:
        problems.append("no ```json spec block found")
    if not js_text:
        problems.append("no ```javascript code block found")
    spec = None
    if json_text:
        try:
            raw = parse_spec(json_text)
            spec, errors, fixes = normalize_spec(raw)
            spec["_raw"] = raw
            problems.extend(errors)
            trace.log("check", "parse_spec", "ok" if not errors else "problems", errors=errors, auto_fixes=fixes)
        except ParseError as exc:
            problems.append(str(exc))
            trace.log("check", "parse_spec", "error", error=str(exc))
    return spec, js_text or "", problems
