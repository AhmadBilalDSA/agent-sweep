# Contributing

## PRs we want right now

**New `Source` adapters.** Every AI coding agent stores history somewhere. Today agentsweep only understands Claude Code. If you write code against Codex, Aider, Cursor, Continue, Cline, Amp, Windsurf, Zed AI, or anything else — a ~30-line adapter makes agentsweep work for your tool.

## The `Source` interface

Every adapter implements three methods (see `src/agentsweep/sources.py`):

```python
class Source(ABC):
    name: str
    root: Path

    def files(self) -> list[Path]:
        """Every history file to scan under this source's root."""

    def iter_strings(self, path: Path) -> Iterator[tuple[int, KeyPath, str]]:
        """Yield (line_number, keypath, string_value) for every string.

        line_number is 1-indexed. keypath locates the string inside the file's
        structure (e.g. ["message", "content", 0, "text"] for Claude Code).
        """

    def apply_redactions(
        self,
        path: Path,
        redactions: list[tuple[int, KeyPath, str]],
    ) -> str:
        """Return the full new file content with strings replaced.

        MUST preserve structure — line count, JSON validity (for JSON-based
        formats), line endings — or the redactor's post-write validation
        will reject the write.
        """
```

## Adding a new source — checklist

1. Subclass `Source` in a new file (or in `sources.py` for v1; we'll split later).
2. Add it to the `SOURCES` dict in `sources.py`.
3. Add an anonymized fixture under `tests/fixtures/<your-source>/sample.<ext>`.
4. Add one integration test: `test_<your_source>_iter_strings_finds_secret` and `test_<your_source>_redactions_preserve_structure`.
5. Document the history location in README.md.
6. Open the PR. Mention which version of the agent you tested against.

## Scope boundary for v1

Until v1.0 we will NOT merge:

- New detection rules (keep regex in one place, don't fragment)
- Feature flags / configuration systems
- Dashboard / daemon / watch modes
- CI/CD integrations

These may land in v1.x. For now, the focus is: more sources, more tests, tighter safety.

## Running tests

```
pip install -e ".[dev]"
pytest -v
```

The test suite is fully hermetic — it never touches `~/.claude/` or any real history directory. Every test uses `tmp_path`. If you add a test that reaches outside `tmp_path`, the PR will be rejected.

## Safety-first review

Any PR that touches `redactor.py` or the write path must:

- Preserve all post-write validations (JSON re-parse, line count match).
- Preserve atomic write semantics (tempfile → fsync → replace).
- Preserve `.bak` creation.
- Not add any code path that writes without going through `safe_write()`.

If you're unsure, open a draft PR and ask.
