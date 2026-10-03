"""Paper to Playground - agent entry point.

Usage (exact interface required by the hackathon):
    python -m pip install -r requirements.txt
    python agent.py --input case.json --output out --model MODEL_ID

Reads OPENROUTER_API_KEY from the environment. Writes out/index.html and
out/trace.jsonl. Exits 0 on success, nonzero on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
    with path.open("r", encoding="utf-8") as f:
        case = json.load(f)
    if not isinstance(case, dict):
        raise ValueError("case.json must contain a JSON object")
    missing = [k for k in REQUIRED_FIELDS if not isinstance(case.get(k), str) or not case[k].strip()]
    if missing:
        raise ValueError(f"case.json is missing required string field(s): {', '.join(missing)}")
    return case


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        case = load_case(Path(args.input))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"loaded case with fields: {', '.join(case)}; model={args.model}", file=sys.stderr)
    print("error: generation pipeline not implemented yet (Phase 0 scaffold)", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
