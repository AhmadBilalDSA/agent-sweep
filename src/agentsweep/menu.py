"""Interactive mode: big banner + numbered actions.

Forgiveness & confirmation: nothing destructive runs without an explicit
typed confirmation, backups are always kept, and undo restores them.
Flags/pipes bypass this module entirely (see cli.main).

Menu actions invoke cli.main with verb argv — zero duplicated logic, and
every action inherits the pipeline UI, safety gates, and exit codes. The
imports are lazy to avoid a cycle (cli imports this module).
"""
from __future__ import annotations

import copy
import os
import threading
from pathlib import Path

from . import __version__, ui
from .pipeline import _suggest_paths


def _passive_update_check() -> None:
    """Fire a background thread to check PyPI for a newer version.

    If a newer version is found within ~1 second, print a dim yellow notice.
    On timeout or any failure, print nothing.  The thread is daemonized so it
    never blocks process exit.
    """
    from .cli import check_for_update

    result: list[str | None] = [None]  # [latest_version]

    def _fetch() -> None:
        latest, err = check_for_update(timeout=2)
        if err is None:
            result[0] = latest

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=1.0)  # wait at most 1 s; if slower, skip notice

    if not t.is_alive() and result[0] is not None:
        from .cli import _version_tuple
        if _version_tuple(result[0]) > _version_tuple(__version__):
            ui.console.print(
                f"  [dim yellow]update available: agentsweep {result[0]} — "
                f"run: pip install --upgrade agentsweep[/dim yellow]"
            )


def run_menu() -> int:
    from .cli import main

    # Clear once on entry so the banner gets a clean canvas — but NOT between
    # menu actions (you want your scan results to stay on screen), and never
    # for flag/piped runs (that path doesn't reach here). Honors NO_ANIM.
    if ui.console.is_terminal and not os.environ.get("AGENTSWEEP_NO_ANIM"):
        ui.console.clear()
    ui.big_banner(__version__)
    _passive_update_check()
    while True:
        ui.menu_options()
        try:
            choice = input("  > ").strip().lower()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            ui.shutdown_notice()
            return 0

        if choice == "1":
            main(["scan", "--source", "claude-code"])
        elif choice == "2":
            main(["scan", "--source", "codex"])
        elif choice == "3":
            main(["scan", "--source", "opencode"])
        elif choice == "4":
            main(["scan", "--source", "cursor"])
        elif choice == "5":
            main(["scan", "--source", "windsurf"])
        elif choice == "6":
            main(["scan", "--source", "aider"])
        elif choice == "7":
            main(["scan", "--source", "cline"])
        elif choice == "8":
            main(["scan", "--source", "gemini-cli"])
        elif choice == "9":
            main(["scan", "--source", "continue-vscode"])
        elif choice == "10":
            main(["scan", "--source", "github-copilot-chat"])
        elif choice == "11":
            root = _ask_folder()
            if root is not None:
                main(["scan", "--root", str(root)])
        elif choice == "12":
            main(["fix", "--source", "claude-code"])
        elif choice == "13":
            main(["undo", "--source", "claude-code"])
        elif choice == "14":
            main(["scan", "--source", "claude-code", "--json"])
        elif choice == "15":
            from .cli import check_for_update, _version_tuple
            print("  checking for updates…")
            latest, err = check_for_update(timeout=5)
            if err is not None:
                ui.warn_line(f"could not reach PyPI — {err}")
            elif _version_tuple(latest) > _version_tuple(__version__):
                print(
                    f"  agentsweep {latest} is available — run: "
                    f"pip install --upgrade agentsweep"
                )
            else:
                print(f"  agentsweep {__version__} is up to date")
        elif choice in {"16", "q", "quit", "exit"}:
            return 0
        else:
            ui.warn_line(f"unknown option: {choice!r} — pick 1-16")
            continue

        try:
            input("\n  press Enter for the menu...")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0


def _ask_folder() -> Path | None:
    """Prompt for a folder, forgivingly: suggest near-misses on typos,
    show the file count before scanning, allow up to 3 attempts."""
    for _ in range(3):
        try:
            raw = input("  folder to scan: ").strip().strip('"')
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not raw:
            return None
        path = Path(raw).expanduser()
        if path.exists():
            count = sum(1 for _ in path.rglob("*.jsonl"))
            print(f"  found {count} .jsonl file(s) under {path}")
            if count == 0:
                try:
                    anyway = input("  scan anyway? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return None
                if anyway != "y":
                    continue
            return path
        ui.warn_line(f"path not found: {path}")
        for hint in _suggest_paths(path):
            print(f"    did you mean: {path.parent / hint}")
    return None


def offer_redaction(args) -> int | None:
    """After a scan shows live secrets, offer to redact them in place.

    Calls pipeline.run directly (not back through the fix verb) so there's
    no re-dispatch loop. Returns the redaction exit code, or None if the
    user skipped. A typed REDACT confirmation is required; a blocked gate
    prompts once for a --force override.
    """
    from .pipeline import run

    print()
    ui.warn_line("those keys are sitting in plain text — redact them now? "
                 "(.bak backups kept; `agentsweep undo` reverts)")
    try:
        typed = input("  type REDACT to confirm (anything else cancels): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if typed != "REDACT":
        ui.warn_line("cancelled — nothing was written")
        return None

    fix_args = copy.copy(args)
    fix_args.fix = True
    # A typed, interactive confirmation IS the alpha-stage opt-in.
    fix_args.allow_production = True
    code = run(fix_args)
    if code == 2 and not fix_args.force:
        try:
            retry = input(
                "  a safety gate blocked the redaction (see above).\n"
                "  override with --force? Only safe if no agent session is "
                "actively writing. [y/N]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return code
        if retry == "y":
            fix_args.force = True
            return run(fix_args)
    return code
