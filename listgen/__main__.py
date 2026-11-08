"""Entry point: python -m listgen (from repo root)."""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[1]
for _path in (_repo_root, _repo_root / "poc"):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

from listgen.runner import main

if __name__ == "__main__":
    raise SystemExit(main())
