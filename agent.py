"""Paper to Playground - agent entry point.

Usage (exact interface required by the hackathon):
    python -m pip install -r requirements.txt
    python agent.py --input case.json --output out --model MODEL_ID

Reads OPENROUTER_API_KEY from the environment. Writes out/index.html and
out/trace.jsonl. Exits 0 on success, nonzero on failure.
"""

from __future__ import annotations

import time

T0 = time.monotonic()  # latency is measured from process start

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

REQUIRED_FIELDS = ("source_url", "focus", "audience")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turn a research-paper excerpt into an interactive HTML explanation."
    )
    parser.add_argument("--input", required=True, help="Path to case.json (UTF-8 JSON).")
    parser.add_argument("--output", required=True, help="Output directory (index.html, trace.jsonl).")
    parser.add_argument("--model", required=True, help="OpenRouter model ID, e.g. deepseek/deepseek-v4.1-flash.")
    return parser.parse_args(argv)


def load_case(path: Path) -> dict:
    """Load case.json. Every string field is kept; the three named fields are required."""
    with path.open("r", encoding="utf-8-sig") as f:
        case = json.load(f)
    if not isinstance(case, dict):
        raise ValueError("case.json must contain a JSON object")
    missing = [k for k in REQUIRED_FIELDS if not isinstance(case.get(k), str) or not case[k].strip()]
    if missing:
        raise ValueError(f"case.json is missing required string field(s): {', '.join(missing)}")
    return case


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    from p2p.llm import Budget, BudgetExceeded, LLMError
    from p2p.trace import Trace

    trace = Trace(out_dir / "trace.jsonl", T0)
    budget = Budget(t0=T0)
    exit_code = 1
    try:
        try:
            case = load_case(Path(args.input))
        except (OSError, ValueError) as exc:
            trace.log("setup", "load_case", "error", error=str(exc))
            print(f"error: {exc}", file=sys.stderr)
            exit_code = 2
            return exit_code
        trace.log("setup", "load_case", "ok", input=str(args.input), model=args.model,
                  fields={k: len(v) if isinstance(v, str) else type(v).__name__ for k, v in case.items()})

        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            trace.log("setup", "read_api_key", "error", error="OPENROUTER_API_KEY is not set")
            print("error: OPENROUTER_API_KEY is not set", file=sys.stderr)
            exit_code = 2
            return exit_code
        trace.log("setup", "read_api_key", "ok")  # the key itself is never logged

        from p2p.pipeline import run

        try:
            result = run(case, args.model, api_key, out_dir, trace, budget)
        except (BudgetExceeded, LLMError) as exc:
            trace.log("generate", "abort", "error", error=str(exc))
            print(f"error: {exc}", file=sys.stderr)
            return exit_code

        if result.html:
            (out_dir / "index.html").write_text(result.html, encoding="utf-8")
            if os.environ.get("P2P_SAVE_SPEC"):  # development only: lets tools/rerender.py rebuild the page
                (out_dir / "page_spec.json").write_text(json.dumps(
                    {"case": case, "excerpt": result.excerpt, "spec": result.spec, "code": result.code},
                    ensure_ascii=False, indent=1), encoding="utf-8")
        exit_code = 0 if result.ok else 1
        if result.problems:
            print("remaining problems:\n- " + "\n- ".join(result.problems), file=sys.stderr)
        return exit_code
    except Exception as exc:  # never die without a trace entry
        trace.log("agent", "crash", "error", error=f"{type(exc).__name__}: {exc}")
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        exit_code = 1
        return exit_code
    finally:
        trace.log("finish", "summary", "success" if exit_code == 0 else "failure",
                  exit_code=exit_code, elapsed_s=round(time.monotonic() - T0, 3), **budget.summary())
        trace.close()


if __name__ == "__main__":
    sys.exit(main())
