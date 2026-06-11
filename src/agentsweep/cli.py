from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .preflight import is_claude_code_running, is_production_root
from .redactor import SafetyError, safe_write, safety_check
from .scanner import ROTATION_GUIDANCE, Finding, scan_text
from .sources import SOURCES, Source


REDACT_TEMPLATE = "[REDACTED:{rule}]"


def main(argv: list[str] | None = None) -> int:
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
        help="Emit findings as JSON to stdout.",
    )
    args = ap.parse_args(argv)

    source_cls = SOURCES[args.source]
    source: Source = source_cls(root=args.root) if args.root else source_cls()

    files = source.files()
    if not files:
        print(f"No history files found under {source.root}", file=sys.stderr)
        return 0

    found_by_file = _scan_all(source, files)

    if args.json:
        _emit_json(found_by_file)
        return 0 if not found_by_file else 1

    if not found_by_file:
        print(f"No secrets found across {len(files)} file(s).")
        return 0

    _print_report(found_by_file)

    if not args.fix:
        print("\nRun with --fix to redact in place (.bak backups written by default).")
        return 1

    gate_err = _preflight_gates(source, source_cls, args)
    if gate_err is not None:
        return gate_err

    errors = _redact_all(
        source=source,
        found_by_file=found_by_file,
        backup=not args.no_backup,
        force=args.force,
    )

    _print_rotation_guidance(found_by_file)

    return 0 if errors == 0 else 2


def _scan_all(
    source: Source,
    files: list[Path],
) -> dict[Path, list[tuple[int, list, str, Finding]]]:
    out: dict[Path, list[tuple[int, list, str, Finding]]] = {}
    for f in files:
        for line_num, keypath, value in source.iter_strings(f):
            for finding in scan_text(value):
                finding.file = f
                finding.line = line_num
                finding.keypath = keypath
                out.setdefault(f, []).append((line_num, keypath, value, finding))
    return out


def _print_report(found_by_file: dict) -> None:
    total = sum(len(v) for v in found_by_file.values())
    print(f"Found {total} secret(s) in {len(found_by_file)} file(s):\n")
    for path, items in found_by_file.items():
        print(f"  {path}")
        for line_num, _kp, _val, finding in items:
            print(f"    L{line_num}: {finding.display} - {finding.masked}")
        print()


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
) -> int:
    print("Redacting ...")
    errors = 0
    for path, items in found_by_file.items():
        try:
            safety_check(path, source.root, force=force)
        except SafetyError as e:
            print(f"  SKIP {path}: {e}", file=sys.stderr)
            errors += 1
            continue

        redactions = _build_redactions(items)
        try:
            new_content = source.apply_redactions(path, redactions)
            record = safe_write(path, new_content, backup=backup)
            tail = f" (.bak: {record.backup.name})" if record.backup else " (no backup)"
            print(f"  OK   {path}{tail}")
        except SafetyError as e:
            print(f"  FAIL {path}: {e}", file=sys.stderr)
            errors += 1
        except Exception as e:
            print(f"  FAIL {path}: {type(e).__name__}: {e}", file=sys.stderr)
            errors += 1
    return errors


def _preflight_gates(source: Source, source_cls: type[Source], args) -> int | None:
    """Return an exit code if a gate blocks --fix; otherwise None to continue."""
    if is_production_root(source, source_cls) and not args.allow_production:
        print(
            f"\nRefusing to --fix the default production root ({source.root}).\n"
            f"agentsweep is in alpha. To proceed, either:\n"
            f"  1. Copy history elsewhere and pass --root <that path>, OR\n"
            f"  2. Re-run with --allow-production (explicit opt-in).\n",
            file=sys.stderr,
        )
        return 2

    running, marker = is_claude_code_running()
    if running and not args.force:
        print(
            f"\nClaude Code appears to be running (detected marker: {marker!r}).\n"
            f"Close all Claude Code sessions before --fix, or pass --force to proceed anyway.\n",
            file=sys.stderr,
        )
        return 2
    if running and args.force:
        print(
            f"  ! --force: proceeding while Claude Code appears to be running "
            f"(marker: {marker!r}).",
            file=sys.stderr,
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


def _print_rotation_guidance(found_by_file: dict) -> None:
    rules_seen: set[str] = set()
    for items in found_by_file.values():
        for _, _, _, finding in items:
            rules_seen.add(finding.rule)

    print("\nACTION REQUIRED - rotate these secrets now:")
    for rule in sorted(rules_seen):
        guidance = ROTATION_GUIDANCE.get(rule, "rotate via the issuing provider")
        print(f"  - {rule}: {guidance}")
    print(
        "\nRedaction removes the secret from local history, but the key still "
        "works until you rotate it."
    )


if __name__ == "__main__":
    sys.exit(main())
