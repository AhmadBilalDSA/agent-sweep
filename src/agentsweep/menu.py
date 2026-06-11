"""Interactive mode: big banner + numbered actions.

Forgiveness & confirmation: nothing destructive runs without an explicit
typed confirmation, backups are always kept, and the undo action restores
them. Flags/pipes bypass this module entirely (see cli.main).

Menu actions invoke cli.main with curated flag lists — zero duplicated
logic, and every action inherits the pipeline UI, safety gates, and exit
codes. The import is lazy to avoid a cycle (cli imports this module).
"""
from __future__ import annotations

import os
from pathlib import Path

from . import __version__, ui
from .pipeline import _suggest_paths
from .sources import SOURCES


def run_menu() -> int:
    from .cli import main

    ui.big_banner(__version__)
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
            main(["--source", "claude-code"])
        elif choice == "2":
            root = _ask_folder()
            if root is not None:
                main(["--root", str(root)])
        elif choice == "3":
            _menu_redact()
        elif choice == "4":
            _menu_undo()
        elif choice == "5":
            main(["--source", "claude-code", "--json"])
        elif choice in {"6", "q", "quit", "exit"}:
            return 0
        else:
            ui.warn_line(f"unknown option: {choice!r} — pick 1-6")
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


def _menu_redact() -> None:
    ui.warn_line("This rewrites files under your Claude Code history in place.")
    ui.warn_line("Every file gets a .bak backup; option 4 can undo afterwards.")
    _confirm_and_fix("claude-code", None)


def _confirm_and_fix(source: str, root: Path | None) -> int | None:
    """Typed-confirmation redaction with a guided --force retry.

    Returns the fix run's exit code, or None if the user backed out.
    """
    from .cli import main

    try:
        typed = input("  type REDACT to confirm (anything else cancels): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if typed != "REDACT":
        ui.warn_line("cancelled — nothing was written")
        return None

    argv = ["--source", source, "--fix", "--allow-production"]
    if root is not None:
        argv += ["--root", str(root)]
    code = main(argv)
    if code != 2:
        return code
    # A safety gate refused (most likely: Claude Code is running, or the
    # files were written moments ago).
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
        return main(argv + ["--force"])
    return code


def offer_redaction(args) -> int | None:
    """Post-scan offer: the report just showed live secrets — fix them now.

    Returns the fix run's exit code, or None if the user skipped.
    """
    print()
    ui.warn_line("those keys are sitting in plain text — you can redact "
                 "them right now (.bak backups kept)")
    return _confirm_and_fix(args.source, args.root)


def _menu_undo() -> None:
    source = SOURCES["claude-code"]()
    backups = sorted(source.root.rglob("*.jsonl.bak")) if source.root.exists() else []
    if not backups:
        ui.warn_line(f"no .bak backups found under {source.root}")
        return
    print(f"  {len(backups)} backup(s) found under {source.root}")
    try:
        confirm = input(
            "  restore them over the redacted files? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if confirm != "y":
        ui.warn_line("cancelled — backups kept as-is")
        return
    for bak in backups:
        original = bak.with_name(bak.name[: -len(".bak")])
        try:
            os.replace(bak, original)
            ui.redact_row("ok", ui.rel(original, source.root), "restored from .bak")
        except OSError as e:
            ui.redact_row("fail", ui.rel(bak, source.root), str(e))
