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

CODEX_MARKERS: tuple[str, ...] = (
    "openai/codex",
    "/codex ",
    "codex.exe",
    "codex.cmd",
    " codex ",
)

OPENCODE_MARKERS: tuple[str, ...] = (
    "sst/opencode",
    "/opencode ",
    "opencode.exe",
    "opencode.cmd",
    " opencode ",
)


def is_agent_running(markers: tuple[str, ...]) -> tuple[bool, str]:
    """Best-effort detection of a running agent process by marker substrings.

    Returns (is_running, matched_marker). If the check itself fails — ps/tasklist
    unavailable, permission denied, etc. — returns (False, "") and the caller
    falls back to the redactor's mtime defense.

    False positives are preferred to false negatives: these are short, common
    strings and we'd rather warn once than silently corrupt a session.
    """
    cmdlines = _list_process_cmdlines()
    if cmdlines is None:
        return (False, "")
    blob = "\n".join(cmdlines).lower()
    for marker in markers:
        if marker in blob:
            return (True, marker.strip())
    return (False, "")


def is_claude_code_running() -> tuple[bool, str]:
    """Back-compat wrapper around is_agent_running for Claude Code."""
    return is_agent_running(CLAUDE_CODE_MARKERS)


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
