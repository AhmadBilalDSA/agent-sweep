"""Entry point: flag parsing and dispatch.

Bare invocation on a real terminal goes to the interactive menu;
anything with flags (or piped) runs the pipeline directly. All run
logic lives in pipeline.py, all interaction in menu.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ui
from .sources import SOURCES


def _interactive() -> bool:
    """True when a human is at both ends (stdin tty + terminal stdout)."""
    try:
        return sys.stdin.isatty() and ui.console.is_terminal
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv and _interactive():
        from .menu import run_menu
        try:
            return run_menu()
        except KeyboardInterrupt:
            ui.shutdown_notice()
            return 130
    try:
        from .pipeline import run
        return run(_parse(argv))
    except KeyboardInterrupt:
        ui.shutdown_notice(during_fix="--fix" in argv, plain="--json" in argv)
        return 130


def _parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="agentsweep",
        description="Find and redact secrets in AI coding agent histories.",
    )
    ap.add_argument(
        "--source",
        choices=list(SOURCES),
        default="claude-code",
        help="Which agent's history to scan (default: claude-code).",
    )
    ap.add_argument(
        "--root",
        type=Path,
        help="Override the source's default root directory.",
    )
    ap.add_argument(
        "--fix",
        action="store_true",
        help="Redact found secrets in place. Without this flag, scan only.",
    )
    ap.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip .bak file creation (NOT recommended).",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Bypass soft safety checks (mtime window, running-process check).",
    )
    ap.add_argument(
        "--allow-production",
        action="store_true",
        help=(
            "Allow --fix against the default production root (e.g. ~/.claude/projects). "
            "Alpha-stage safety gate — required while agentsweep is pre-1.0."
        ),
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as JSON to stdout (no banner, no styling).",
    )
    return ap.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
