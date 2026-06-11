from __future__ import annotations

import subprocess
import sys
from pathlib import Path


CLAUDE_CODE_MARKERS: tuple[str, ...] = (
    "claude-code",
    "anthropic-ai/claude-code",
    "/claude ",
    # Windows tasklist reports the bare image name ("claude.exe", no path),
    # so the marker must not require a leading backslash.
    "claude.exe",
    "claude.cmd",
    " claude ",
)


def is_claude_code_running() -> tuple[bool, str]:
    """Best-effort detection of a running Claude Code process.

    Returns (is_running, matched_marker). If the check itself fails — ps/tasklist
    unavailable, permission denied, etc. — returns (False, "") and the caller
    falls back to the redactor's mtime defense.

    False positives are preferred to false negatives: "claude" is a short, common
    string and we'd rather warn once than silently corrupt a session.
    """
    cmdlines = _list_process_cmdlines()
    if cmdlines is None:
        return (False, "")
    blob = "\n".join(cmdlines).lower()
    for marker in CLAUDE_CODE_MARKERS:
        if marker in blob:
            return (True, marker.strip())
    return (False, "")


def _list_process_cmdlines() -> list[str] | None:
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                text=True,
                timeout=5,
                stderr=subprocess.DEVNULL,
            )
        else:
            out = subprocess.check_output(
                ["ps", "-eo", "args="],
                text=True,
                timeout=5,
                stderr=subprocess.DEVNULL,
            )
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return None
    return out.splitlines()


def is_production_root(source, source_cls) -> bool:
    """Check whether `source` points at the source class's default root."""
    default = source_cls()
    try:
        return source.root.resolve() == default.root.resolve()
    except (OSError, RuntimeError):
        return source.root == default.root
