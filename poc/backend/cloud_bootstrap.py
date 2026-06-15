"""One-time setup for Streamlit Community Cloud (Playwright browser binaries)."""

from __future__ import annotations

import subprocess
import sys


def ensure_playwright_chromium() -> None:
    """Install Chromium on Linux cloud hosts where pip does not fetch browser binaries."""
    if sys.platform != "linux":
        return

    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error").strip()
        raise RuntimeError(f"playwright install chromium failed: {detail}")
