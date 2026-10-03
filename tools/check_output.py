"""Check an agent output folder against the hackathon's output rules (section 5).

    python tools/check_output.py out [more output folders ...]

Checks index.html (exists, self-contained, nothing loaded from the network,
no API key) and trace.jsonl (one JSON object per line with stage/action/result,
per-call token counts and elapsed seconds, checks recorded, limits respected,
no credentials or hidden reasoning). Exit code 0 if every folder passes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LIMIT_REQUESTS, LIMIT_COMPLETION, LIMIT_SECONDS = 10, 30_000, 600

EXTERNAL = [
    (r"<script\b[^>]*\bsrc\s*=", "external <script src>"),
    (r"<link\b[^>]*\bhref\s*=\s*[\"']?\s*(?:https?:)?//", "external <link href>"),
    (r"<(?:img|iframe|video|audio|source|embed|object)\b[^>]*\b(?:src|data)\s*=\s*[\"']?\s*(?:https?:)?//", "remote media"),
    (r"@import", "CSS @import"),
    (r"url\(\s*[\"']?\s*(?:https?:)?//", "remote CSS url()"),
    (r"@font-face", "downloaded font (@font-face)"),
    (r"\bfetch\s*\(|XMLHttpRequest|new\s+WebSocket|navigator\.sendBeacon", "network call in script"),
]
KEY_PATTERN = re.compile(r"sk-or-v1-[0-9a-f]{20,}")


def check_folder(folder: Path) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []

    def check(ok: bool, text: str) -> None:
        results.append((bool(ok), text))

    page_path, trace_path = folder / "index.html", folder / "trace.jsonl"
    check(page_path.is_file(), "index.html exists")
    check(trace_path.is_file(), "trace.jsonl exists")
    if page_path.is_file():
        page = page_path.read_text(encoding="utf-8")
        check(page.lstrip().lower().startswith("<!doctype html>"), "index.html is a complete HTML document")
        check("<style>" in page and "<script>" in page, "CSS and JavaScript are embedded in the page")
        check("<svg" in page or "p2p-visual" in page, "page has a visual container")
        for pattern, label in EXTERNAL:
            check(not re.search(pattern, page, re.I), f"no {label}")
        check(not KEY_PATTERN.search(page), "no API key in the page")
        check(not re.search(r"\{\{[A-Z_]+\}\}", page), "no unfilled template placeholders")
    if not trace_path.is_file():
        return results

    raw_lines = [ln for ln in trace_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    events, bad = [], 0
    for ln in raw_lines:
        try:
            ev = json.loads(ln)
            events.append(ev) if isinstance(ev, dict) else None
            bad += not isinstance(ev, dict)
        except json.JSONDecodeError:
            bad += 1
    check(bad == 0 and events, f"trace: every line is one JSON object ({len(events)} events)")
    check(all({"stage", "action", "result"} <= set(e) for e in events), "trace: every event has stage, action, result")
    check(all(isinstance(e.get("t"), (int, float)) for e in events), "trace: every event has elapsed seconds (t)")
    calls = [e for e in events if e.get("action") == "llm_call"]
    check(calls, f"trace: model calls recorded ({len(calls)})")
    check(all(isinstance(e.get("prompt_tokens"), int) and isinstance(e.get("completion_tokens"), int) for e in calls),
          "trace: every call has prompt and completion token counts")
    check(all(isinstance(e.get("elapsed_s"), (int, float)) for e in calls), "trace: every call has elapsed seconds")
    check(all(e.get("generation_id") for e in calls if e.get("result") == "ok"),
          "trace: every successful call has an OpenRouter generation id (verifiable usage)")
    check(any(e.get("stage") in ("check", "final_check") for e in events), "trace: checks are recorded")
    revisions = [e for e in events if e.get("stage") == "revise" and e.get("action") == "request"]
    failed_checks = [e for e in events if e.get("result") in ("fail", "error")]
    check(True, f"trace: {len(failed_checks)} failed check/error events and {len(revisions)} revisions recorded")
    text = trace_path.read_text(encoding="utf-8")
    check(not KEY_PATTERN.search(text) and "Bearer" not in text, "trace: no credentials")
    check(not any(isinstance(e.get(k), str) and len(e.get(k)) > 0 for e in events
                  for k in ("reasoning", "reasoning_content", "thinking")), "trace: no hidden reasoning text")
    summary = events[-1] if events else {}
    check(summary.get("action") == "summary", "trace: final summary event present")
    req = summary.get("requests", len(calls))
    comp = summary.get("completion_tokens", sum(e.get("completion_tokens", 0) for e in calls))
    secs = summary.get("elapsed_s", summary.get("t", 0))
    check(req <= LIMIT_REQUESTS, f"limit: {req} API requests (max {LIMIT_REQUESTS})")
    check(comp <= LIMIT_COMPLETION, f"limit: {comp} completion tokens (max {LIMIT_COMPLETION})")
    check(secs <= LIMIT_SECONDS, f"limit: {secs:.1f} s elapsed (max {LIMIT_SECONDS})")
    check(summary.get("exit_code") in (0, 1, 2), f"exit code recorded: {summary.get('exit_code')} "
          f"(total tokens {summary.get('total_tokens')})")
    return results


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    all_ok = True
    for arg in sys.argv[1:]:
        results = check_folder(Path(arg))
        ok = all(r for r, _ in results)
        all_ok &= ok
        print(f"== {arg}: {'PASS' if ok else 'FAIL'}")
        for passed, text in results:
            print(f"  [{'x' if passed else ' '}] {text}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
