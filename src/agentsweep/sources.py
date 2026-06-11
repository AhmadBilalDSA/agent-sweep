from __future__ import annotations

import json
import os
import sqlite3
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

from .preflight import CLAUDE_CODE_MARKERS, CODEX_MARKERS, OPENCODE_MARKERS

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

    def iter_files(self) -> Iterator[Path]:
        """Yield history files one by one (default: iterate over files()).

        Override in subclasses where streaming discovery is possible so that
        callers can show a live counter without waiting for the full list.
        """
        yield from self.files()

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

    def iter_files(self) -> Iterator[Path]:
        """Yield JSONL files as rglob discovers them (no full-list sort)."""
        if not self.root.exists():
            return
        for p in self.root.rglob("*.jsonl"):
            if p.is_file():
                yield p

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


def _walk_json_with_base(
    obj,
    base_kp: KeyPath,
    line_num: int,
) -> Iterator[tuple[int, KeyPath, str]]:
    """Like _walk_json but prepends base_kp to every yielded keypath."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                yield (line_num, base_kp + [k], v)
            elif isinstance(v, (dict, list)):
                yield from _walk_json_with_base(v, base_kp + [k], line_num)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str):
                yield (line_num, base_kp + [i], v)
            elif isinstance(v, (dict, list)):
                yield from _walk_json_with_base(v, base_kp + [i], line_num)


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


class OpenCodeSource(Source):
    """OpenCode (sst/opencode) — history stored in a SQLite database at
    ~/.local/share/opencode/opencode.db, or (legacy) as JSON files under
    ~/.local/share/opencode/storage/**/*.json.

    The XDG data dir resolves as follows:
    - Linux/macOS: $XDG_DATA_HOME if set, else ~/.local/share
    - Windows: $XDG_DATA_HOME if set, else %LOCALAPPDATA% if set,
      else ~/.local/share (xdg-basedir fallback)

    If the SQLite DB is present it is the primary source: text content from
    the ``part`` table (column ``content``) is scanned.  The redaction path
    updates the DB row in place.  If only the legacy JSON files exist they are
    scanned as ordinary JSON (not JSONL); each file is parsed as a dict and
    every string value is yielded.
    """

    name = "opencode"
    display_name = "OpenCode"
    process_markers = OPENCODE_MARKERS

    # Sentinel path used in keypath to distinguish SQLite rows from JSON paths.
    _SQLITE_SENTINEL = "__sqlite_row__"

    def __init__(self, root: Path | None = None):
        self.root = root or self.default_root()

    @classmethod
    def _xdg_data_home(cls) -> Path:
        """Return the XDG_DATA_HOME base directory for the current platform."""
        xdg = os.environ.get("XDG_DATA_HOME", "")
        if xdg:
            return Path(xdg)
        if sys.platform == "win32":
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                return Path(local_app)
        return Path.home() / ".local" / "share"

    @classmethod
    def default_root(cls) -> Path:
        return cls._xdg_data_home() / "opencode"

    # --- SQLite helpers -------------------------------------------------

    def _db_path(self) -> Path:
        return self.root / "opencode.db"

    def _storage_dir(self) -> Path:
        return self.root / "storage"

    def _has_sqlite(self) -> bool:
        return self._db_path().is_file()

    # --- Source interface -----------------------------------------------

    def files(self) -> list[Path]:
        """Return the DB path (as a single-element list) if it exists, else
        every JSON file under the legacy storage/ directory."""
        if not self.root.exists():
            return []
        if self._has_sqlite():
            return [self._db_path()]
        storage = self._storage_dir()
        if not storage.exists():
            return []
        return sorted(p for p in storage.rglob("*.json") if p.is_file())

    def iter_files(self) -> Iterator[Path]:
        """Yield files as discovered (SQLite DB or legacy JSON files)."""
        if not self.root.exists():
            return
        if self._has_sqlite():
            yield self._db_path()
            return
        storage = self._storage_dir()
        if not storage.exists():
            return
        for p in storage.rglob("*.json"):
            if p.is_file():
                yield p

    def iter_strings(self, path: Path) -> Iterator[tuple[int, KeyPath, str]]:
        if path == self._db_path():
            yield from self._iter_strings_sqlite(path)
        else:
            yield from self._iter_strings_json(path)

    def apply_redactions(
        self,
        path: Path,
        redactions: list[tuple[int, KeyPath, str]],
    ) -> str:
        if path == self._db_path():
            return self._apply_redactions_sqlite(path, redactions)
        return self._apply_redactions_json(path, redactions)

    # --- SQLite scanning ------------------------------------------------

    def _iter_strings_sqlite(self, path: Path) -> Iterator[tuple[int, KeyPath, str]]:
        """Yield strings from the SQLite ``part`` and ``message`` tables.

        Keypath encoding for SQLite rows:
          [table_name, row_id, column_name]
        Line number is set to the rowid (1-based if rowid >= 1, else 1).
        """
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return
        try:
            for table, col in self._sqlite_text_columns(con):
                try:
                    cur = con.execute(
                        f"SELECT rowid, {col} FROM {table}"  # noqa: S608 (controlled)
                    )
                except sqlite3.OperationalError:
                    continue
                for rowid, value in cur:
                    if not isinstance(value, str) or not value:
                        continue
                    # Try to expand JSON content stored as a string column
                    try:
                        obj = json.loads(value)
                        kp_base: KeyPath = [table, rowid, col]
                        yield from _walk_json_with_base(obj, kp_base, max(rowid, 1))
                    except (json.JSONDecodeError, TypeError):
                        yield (max(rowid, 1), [table, rowid, col], value)
        finally:
            con.close()

    def _sqlite_text_columns(self, con: sqlite3.Connection) -> list[tuple[str, str]]:
        """Return (table, column) pairs for TEXT columns in known tables."""
        pairs: list[tuple[str, str]] = []
        known = {
            "part": ["content"],
            "message": ["metadata", "metadata_part"],
            "session": ["title"],
            "session_input": ["content"],
        }
        try:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        except sqlite3.OperationalError:
            return pairs
        for table, cols in known.items():
            if table not in tables:
                continue
            for col in cols:
                pairs.append((table, col))
        return pairs

    # --- SQLite redaction -----------------------------------------------

    def _apply_redactions_sqlite(
        self,
        path: Path,
        redactions: list[tuple[int, KeyPath, str]],
    ) -> str:
        """Apply redactions directly to the SQLite DB rows.

        Returns the original DB content read as bytes, decoded as latin-1
        (a no-op passthrough that satisfies the pipeline's write-back
        contract).  The actual mutations are applied via UPDATE statements.
        """
        try:
            con = sqlite3.connect(str(path))
        except sqlite3.OperationalError:
            return path.read_bytes().decode("latin-1")
        try:
            for _line_num, kp, new_val in redactions:
                if len(kp) < 3:
                    continue
                table, rowid, col = kp[0], kp[1], kp[2]
                sub_kp = kp[3:]
                if not sub_kp:
                    # Direct column value
                    con.execute(
                        f"UPDATE {table} SET {col} = ? WHERE rowid = ?",  # noqa: S608
                        (new_val, rowid),
                    )
                else:
                    # JSON-embedded value: read, patch, write back
                    cur = con.execute(
                        f"SELECT {col} FROM {table} WHERE rowid = ?",  # noqa: S608
                        (rowid,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        continue
                    try:
                        obj = json.loads(row[0])
                    except (json.JSONDecodeError, TypeError):
                        continue
                    _set_by_path(obj, sub_kp, new_val)
                    con.execute(
                        f"UPDATE {table} SET {col} = ? WHERE rowid = ?",  # noqa: S608
                        (json.dumps(obj, ensure_ascii=False), rowid),
                    )
            con.commit()
        finally:
            con.close()
        # Return the (now mutated) file bytes decoded as latin-1 so the
        # pipeline can write it back via path.write_text(content, "latin-1").
        return path.read_bytes().decode("latin-1")

    # --- JSON (legacy) scanning/redaction --------------------------------

    def _iter_strings_json(self, path: Path) -> Iterator[tuple[int, KeyPath, str]]:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return
        yield from _walk_json(obj, [], 1)

    def _apply_redactions_json(
        self,
        path: Path,
        redactions: list[tuple[int, KeyPath, str]],
    ) -> str:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return text
        for _line_num, kp, new_val in redactions:
            _set_by_path(obj, kp, new_val)
        return json.dumps(obj, ensure_ascii=False, indent=2)


SOURCES: dict[str, type[Source]] = {
    "claude-code": ClaudeCodeSource,
    "codex": CodexSource,
    "opencode": OpenCodeSource,
}
