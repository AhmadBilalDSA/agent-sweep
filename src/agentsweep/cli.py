"""Entry point: verb dispatch and flag parsing.

Usage shapes, all supported:

    agentsweep                 bare → interactive menu (on a real terminal)
    agentsweep scan [opts]     scan only
    agentsweep fix  [opts]     redact (guided + confirmed on a terminal)
    agentsweep undo [opts]     restore .bak backups
    agentsweep --fix ...       legacy flag form, kept working as an alias

Run logic lives in pipeline.py; interaction in menu.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, ui
from .sources import SOURCES

VERBS = {"scan", "fix", "undo"}


def _interactive() -> bool:
    """True when a human is at both ends (stdin tty + terminal stdout)."""
    try:
        return sys.stdin.isatty() and ui.console.is_terminal
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] in ("-V", "--version"):
        print(f"agentsweep {__version__}")
        return 0

    if not argv and _interactive():
        from .menu import run_menu
        try:
            return run_menu()
        except KeyboardInterrupt:
            ui.shutdown_notice()
            return 130

    verb, rest = _route(argv)

    try:
        if verb == "undo":
            from .pipeline import undo
            return undo(_parse_undo(rest))

        args = _parse_run(verb, rest)
        from .pipeline import run
        from .menu import offer_redaction

        if verb == "fix" and not _interactive():
            args.fix = True  # script path: explicit gate flags required
            return run(args)

        # Interactive scan OR interactive fix: scan first, then offer to
        # redact what we found. One guided path; the offer is the fix.
        args.fix = False
        code = run(args)
        if code == 1 and not args.json and _interactive():
            fixed = offer_redaction(args)
            if fixed is not None:
                return fixed
        return code
    except KeyboardInterrupt:
        ui.shutdown_notice(during_fix=(verb == "fix"), plain=("--json" in rest))
        return 130


def _route(argv: list[str]) -> tuple[str, list[str]]:
    """Resolve (verb, remaining args), accepting both verbs and legacy flags."""
    if argv and argv[0] in VERBS:
        return argv[0], argv[1:]
    # Legacy flag form: --fix means the fix verb; otherwise scan.
    if "--fix" in argv:
        return "fix", [a for a in argv if a != "--fix"]
    return "scan", argv


def _add_common(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--source", choices=list(SOURCES), default="claude-code",
                    help="Which agent's history (default: claude-code).")
    ap.add_argument("--root", type=Path,
                    help="Override the source's default root directory.")


def _parse_run(verb: str, rest: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog=f"agentsweep {verb}",
        description="Find and redact secrets in AI coding agent histories.",
    )
    _add_common(ap)
    ap.add_argument("-o", "--output", type=Path,
                    help="Write findings as JSON to this file instead of "
                         "flooding the terminal.")
    ap.add_argument("--json", action="store_true",
                    help="Emit findings as JSON to stdout (no banner/styling).")
    ap.add_argument("--no-ignore", action="store_true",
                    help="Ignore any .agentsweepignore files.")
    # Redaction flags (used by `fix` / legacy --fix; harmless on `scan`).
    ap.add_argument("--no-backup", action="store_true",
                    help="Skip .bak file creation (NOT recommended).")
    ap.add_argument("--force", action="store_true",
                    help="Bypass soft safety checks (mtime, running-process).")
    ap.add_argument("--allow-production", action="store_true",
                    help="Allow --fix against the default production root.")
    args = ap.parse_args(rest)
    args.fix = (verb == "fix")
    return args


def _parse_undo(rest: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="agentsweep undo",
        description="Restore *.jsonl.bak backups over their redacted files.",
    )
    _add_common(ap)
    return ap.parse_args(rest)


if __name__ == "__main__":
    sys.exit(main())
