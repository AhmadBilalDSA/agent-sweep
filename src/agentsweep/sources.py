from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

from .preflight import CLAUDE_CODE_MARKERS, CODEX_MARKERS

KeyPath = list  # list of str (dict keys) or int (list indices)


class Source(ABC):
    """Adapter for a specific AI coding agent's on-disk history format.

    To add a new source (Aider, Cursor, ...), subclass and implement the
    three abstract methods — or subclass JsonlSource if the agent stores
    plain JSONL. See CONTRIBUTING.md for the PR template.
    """

    name: str
    display_name: str
    root: Path
    # Substrings that identify the agent in a process listing; used by the
    # active-session safety gate before --fix.
    process_markers: tuple[str, ...] = ()

    @abstractmethod
    def files(self) -> list[Path]:
        """Return every history file to scan under this source's root."""

    @abstractmethod
    def iter_strings(self, path: Path) -> Iterator[tuple[int, KeyPath, str]]:
        """Yield (line_number, keypath, value) for every string in the file.

        line_number is 1-indexed. keypath is a list of dict keys / list indices
        that locates the string inside the file's structure (for JSONL: inside
        its parsed line). value is the raw string content.
        """

    @abstractmethod
    def apply_redactions(
        self,
        path: Path,
        redactions: list[tuple[int, KeyPath, str]],
    ) -> str:
        """Produce the new file content with string values replaced.

        Each redaction is (line_number, keypath, new_string). The returned
        string is the full file content to write. Implementations MUST preserve
        structure (line count, JSON validity, line endings) so the redactor's
        post-write validation passes.
        """


class JsonlSource(Source):
    """Shared implementation for agents that store history as JSONL files:
    every string value inside each line's parsed JSON is scanned, and
    redaction replaces values in the parsed structure before re-serializing."""

    def __init__(self, root: Path | None = None):
        self.root = root or self.default_root()

    @classmethod
    def default_root(cls) -> Path:
        raise NotImplementedError

    def files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(p for p in self.root.rglob("*.jsonl") if p.is_file())

    def iter_strings(self, path: Path) -> Iterator[tuple[int, KeyPath, str]]:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield from _walk_json(obj, [], i)

    def apply_redactions(
        self,
        path: Path,
        redactions: list[tuple[int, KeyPath, str]],
    ) -> str:
        text = path.read_text(encoding="utf-8")
        # splitlines(keepends=True) preserves \r\n vs \n vs trailing-no-newline.
        lines = text.splitlines(keepends=True)

        by_line: dict[int, list[tuple[KeyPath, str]]] = {}
        for line_num, kp, new_val in redactions:
            by_line.setdefault(line_num, []).append((kp, new_val))

        out: list[str] = []
        for i, line in enumerate(lines, 1):
            if i not in by_line or not line.strip():
                out.append(line)
                continue
            ending = _line_ending(line)
            body = line[: len(line) - len(ending)]
            try:
                obj = json.loads(body)
            except json.JSONDecodeError:
                out.append(line)
                continue
            for kp, new_val in by_line[i]:
                _set_by_path(obj, kp, new_val)
            out.append(json.dumps(obj, ensure_ascii=False) + ending)
        return "".join(out)


class ClaudeCodeSource(JsonlSource):
    """Claude Code CLI — per-session JSONL under ~/.claude/projects/."""

    name = "claude-code"
    display_name = "Claude Code"
    process_markers = CLAUDE_CODE_MARKERS

    @classmethod
    def default_root(cls) -> Path:
        return Path.home() / ".claude" / "projects"


class CodexSource(JsonlSource):
    """OpenAI Codex CLI — rollout JSONL under ~/.codex/sessions/YYYY/MM/DD/,
    plus history.jsonl and session_index.jsonl at the root.

    Rooted at ~/.codex: rglob('*.jsonl') picks up every transcript while
    structurally excluding auth.json (OAuth tokens, .json) and config.toml —
    files a redactor must never rewrite.
    """

    name = "codex"
    display_name = "Codex"
    process_markers = CODEX_MARKERS

    @classmethod
    def default_root(cls) -> Path:
        return Path.home() / ".codex"


def _walk_json(obj, path: KeyPath, line_num: int) -> Iterator[tuple[int, KeyPath, str]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                yield (line_num, path + [k], v)
            elif isinstance(v, (dict, list)):
                yield from _walk_json(v, path + [k], line_num)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str):
                yield (line_num, path + [i], v)
            elif isinstance(v, (dict, list)):
                yield from _walk_json(v, path + [i], line_num)


def _set_by_path(obj, path: KeyPath, value) -> None:
    cur = obj
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


SOURCES: dict[str, type[Source]] = {
    "claude-code": ClaudeCodeSource,
    "codex": CodexSource,
}
