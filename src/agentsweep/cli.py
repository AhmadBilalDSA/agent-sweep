from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path

from . import __version__, ui
from .preflight import is_claude_code_running, is_production_root
from .redactor import SafetyError, safe_write, safety_check
from .scanner import ROTATION_GUIDANCE, Finding, scan_text
from .sources import SOURCES, Source


REDACT_TEMPLATE = "[REDACTED:{rule}]"


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
        return _menu()

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
    args = ap.parse_args(argv)

    source_cls = SOURCES[args.source]
    source: Source = source_cls(root=args.root) if args.root else source_cls()

    if args.root is not None and not source.root.exists():
        print(f"Path not found: {source.root}", file=sys.stderr)
        for hint in _suggest_paths(source.root):
            print(f"  did you mean: {source.root.parent / hint}", file=sys.stderr)
        if args.json:
            print("[]")  # stdout stays parseable JSON even on user error
        return 2

    if not args.json:
        ui.banner(__version__)

    files = source.files()
    if not files:
        print(f"No history files found under {source.root}", file=sys.stderr)
        if args.json:
            print("[]")  # stdout must stay parseable JSON in every --json run
        else:
            ui.stage(1, "warn", "DISCOVER", source.name,
                     f"no history files under {source.root}", err=True)
        return 0

    if args.json:
        found_by_file, _ = _scan_all(source, files)
        _emit_json(found_by_file)
        return 0 if not found_by_file else 1

    ui.stage(1, "ok", "DISCOVER", source.name, f"{len(files)} file(s)", source.root)

    t0 = time.perf_counter()
    with ui.scanning(len(files)):
        found_by_file, strings_scanned = _scan_all(source, files)
    elapsed = time.perf_counter() - t0

    ui.stage(2, "ok", "SCAN", f"{len(files)} file(s)",
             f"{strings_scanned} string(s)", f"{elapsed:.1f}s")

    if not found_by_file:
        ui.stage(3, "ok", "FINDINGS", "no secrets found")
        ui.stage(4, "skip", "REDACT", "nothing to redact")
        ui.stage(5, "skip", "ROTATE", "nothing to rotate")
        return 0

    total = sum(len(v) for v in found_by_file.values())
    ui.stage(3, "fail", "FINDINGS", f"{total} secret(s) in {len(found_by_file)} file(s)")
    ui.findings_table(_table_rows(found_by_file), source.root)

    if not args.fix:
        ui.stage(4, "skip", "REDACT",
                 "skipped — run with --fix to redact in place (.bak backups)")
        ui.stage(5, "warn", "ROTATE", "these keys are still live")
        ui.rotation_panel(_rotation_items(found_by_file))
        return 1

    gate_err = _preflight_gates(source, source_cls, args)
    if gate_err is not None:
        # The user who most needs rotation guidance is the one we just
        # refused to redact for — the keys are confirmed live.
        ui.stage(5, "warn", "ROTATE", "these keys are still live")
        ui.rotation_panel(_rotation_items(found_by_file))
        return gate_err

    rows, errors = _redact_all(
        source=source,
        found_by_file=found_by_file,
        backup=not args.no_backup,
        force=args.force,
    )

    ok_count = sum(1 for status, _, _ in rows if status == "ok")
    if errors == 0:
        ui.stage(4, "ok", "REDACT", f"{ok_count}/{len(rows)} file(s) rewritten")
    elif ok_count:
        ui.stage(4, "warn", "REDACT", f"{ok_count}/{len(rows)} file(s) rewritten")
    else:
        ui.stage(4, "fail", "REDACT", f"0/{len(rows)} file(s) rewritten")
    for status, path_display, note in rows:
        ui.redact_row(status, path_display, note)

    if ok_count:
        ui.stage(5, "warn", "ROTATE", "redacted locally", "keys live until rotated")
    else:
        ui.stage(5, "warn", "ROTATE", "nothing redacted", "these keys are still live")
    ui.rotation_panel(_rotation_items(found_by_file))

    return 0 if errors == 0 else 2


def _menu() -> int:
    """Interactive mode: big banner + numbered actions.

    Forgiveness & confirmation: nothing destructive runs without an explicit
    typed confirmation, backups are always kept, and option 4 undoes the
    last redaction by restoring them. Flags/pipes bypass this entirely.
    """
    ui.big_banner(__version__)
    while True:
        ui.menu_options()
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
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


def _suggest_paths(missing: Path) -> list[str]:
    """Typo forgiveness: close-matching sibling directory names."""
    parent = missing.parent
    try:
        if not parent.exists():
            return []
        siblings = [p.name for p in parent.iterdir() if p.is_dir()]
    except OSError:
        return []
    return difflib.get_close_matches(missing.name, siblings, n=3, cutoff=0.5)


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
    try:
        typed = input("  type REDACT to confirm (anything else cancels): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if typed != "REDACT":
        ui.warn_line("cancelled — nothing was written")
        return

    code = main(["--fix", "--allow-production"])
    if code != 2:
        return
    # A safety gate refused (most likely: Claude Code is running).
    try:
        retry = input(
            "  a safety gate blocked the redaction (see above).\n"
            "  override with --force? Only safe if no agent session is "
            "actively writing. [y/N]: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if retry == "y":
        main(["--fix", "--allow-production", "--force"])


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


def _scan_all(
    source: Source,
    files: list[Path],
) -> tuple[dict[Path, list[tuple[int, list, str, Finding]]], int]:
    out: dict[Path, list[tuple[int, list, str, Finding]]] = {}
    strings_scanned = 0
    for f in files:
        for line_num, keypath, value in source.iter_strings(f):
            strings_scanned += 1
            for finding in scan_text(value):
                finding.file = f
                finding.line = line_num
                finding.keypath = keypath
                out.setdefault(f, []).append((line_num, keypath, value, finding))
    return out, strings_scanned


def _table_rows(found_by_file: dict) -> list[tuple[str, str, Path, int]]:
    rows: list[tuple[str, str, Path, int]] = []
    for path, items in found_by_file.items():
        for line_num, _kp, _val, finding in items:
            rows.append((finding.display, finding.masked, path, line_num))
    return rows


def _rotation_items(found_by_file: dict) -> list[tuple[str, str]]:
    rules = sorted({
        finding.rule
        for items in found_by_file.values()
        for _, _, _, finding in items
    })
    return [
        (rule, ROTATION_GUIDANCE.get(rule, "rotate via the issuing provider"))
        for rule in rules
    ]


def _emit_json(found_by_file: dict) -> None:
    payload = []
    for path, items in found_by_file.items():
        for line_num, keypath, _val, finding in items:
            payload.append({
                "file": str(path),
                "line": line_num,
                "keypath": keypath,
                "rule": finding.rule,
                "display": finding.display,
                "masked": finding.masked,
            })
    print(json.dumps(payload, indent=2))


def _redact_all(
    source: Source,
    found_by_file: dict,
    backup: bool,
    force: bool,
) -> tuple[list[tuple[str, str, str]], int]:
    """Apply redactions, returning ((status, path_display, note) rows, error count).

    Rows are collected rather than printed so the REDACT stage line can
    report the real outcome (ok/partial/all-failed) above them.
    """
    rows: list[tuple[str, str, str]] = []
    errors = 0
    for path, items in found_by_file.items():
        display = ui.rel(path, source.root)
        try:
            safety_check(path, source.root, force=force)
        except SafetyError as e:
            rows.append(("skip", display, str(e)))
            errors += 1
            continue

        redactions = _build_redactions(items)
        try:
            new_content = source.apply_redactions(path, redactions)
            record = safe_write(path, new_content, backup=backup)
            note = f".bak: {record.backup.name}" if record.backup else "no backup"
            rows.append(("ok", display, note))
        except SafetyError as e:
            rows.append(("fail", display, str(e)))
            errors += 1
        except Exception as e:
            rows.append(("fail", display, f"{type(e).__name__}: {e}"))
            errors += 1
    return rows, errors


def _preflight_gates(source: Source, source_cls: type[Source], args) -> int | None:
    """Return an exit code if a gate blocks --fix; otherwise None to continue."""
    if is_production_root(source, source_cls) and not args.allow_production:
        ui.stage(4, "fail", "REDACT", "blocked by safety gate")
        ui.gate_panel("alpha safety gate", [
            "Refusing to --fix the default production root:",
            f"  {source.root}",
            "",
            "agentsweep is in alpha. To proceed, either:",
            "  1. copy history elsewhere and pass --root <that path>, OR",
            "  2. re-run with --allow-production (explicit opt-in).",
        ])
        return 2

    running, marker = is_claude_code_running()
    if running and not args.force:
        ui.stage(4, "fail", "REDACT", "blocked by safety gate")
        ui.gate_panel("active session gate", [
            f"Claude Code appears to be running (marker: {marker!r}).",
            "Close all Claude Code sessions before --fix,",
            "or pass --force to proceed anyway.",
        ])
        return 2
    if running and args.force:
        ui.warn_line(
            f"--force: proceeding while Claude Code appears to be running "
            f"(marker: {marker!r})"
        )

    return None


def _build_redactions(items: list[tuple[int, list, str, Finding]]) -> list[tuple[int, list, str]]:
    # Group findings by the (line, keypath) pair so multiple secrets inside one
    # string are applied in a single rewrite.
    by_loc: dict[tuple[int, tuple], tuple[str, list[Finding]]] = {}
    for line_num, kp, val, finding in items:
        key = (line_num, tuple(kp))
        if key not in by_loc:
            by_loc[key] = (val, [])
        by_loc[key][1].append(finding)

    redactions: list[tuple[int, list, str]] = []
    for (line_num, kp_tuple), (original, findings) in by_loc.items():
        new_val = original
        # Replace right-to-left so earlier spans' offsets stay valid.
        for fd in sorted(findings, key=lambda x: x.span[0], reverse=True):
            start, end = fd.span
            new_val = new_val[:start] + REDACT_TEMPLATE.format(rule=fd.rule) + new_val[end:]
        redactions.append((line_num, list(kp_tuple), new_val))
    return redactions


if __name__ == "__main__":
    sys.exit(main())
