"""Rebuild index.html from a saved page_spec.json with the current template.

For design work: no API key, no tokens. A page_spec.json is written next to
index.html when the agent runs with the environment variable P2P_SAVE_SPEC=1.

    python tools/rerender.py runs/attention1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from p2p.build import build_page  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    folder = Path(sys.argv[1])
    data = json.loads((folder / "page_spec.json").read_text(encoding="utf-8"))
    page = build_page(data["spec"], data["code"], data["case"], data.get("excerpt", ""))
    (folder / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {folder / 'index.html'} ({len(page)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
