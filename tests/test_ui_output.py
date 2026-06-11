"""Contract tests for the pipeline UI: --json purity, exit codes, masking."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentsweep.cli import main  # noqa: E402


AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GH_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
FIXTURE_LINE = (
    '{"type":"user","message":{"content":[{"type":"text",'
    f'"text":"key={AWS_KEY} and token {GH_TOKEN}"}}]}}}}\n'
)
ANSI_ESCAPE = re.compile(r"\x1b\[")


def _mkroot(tmp_path: Path, content: str = FIXTURE_LINE) -> Path:
    root = tmp_path / "history"
    root.mkdir()
    (root / "session.jsonl").write_text(content, encoding="utf-8")
    return root


def test_json_mode_is_machine_clean(tmp_path, capsys):
    root = _mkroot(tmp_path)
    code = main(["--root", str(root), "--json"])
    out = capsys.readouterr().out

    assert code == 1
    payload = json.loads(out)  # whole stdout must be valid JSON
    assert {f["rule"] for f in payload} == {"aws-access-key", "github-pat"}
    assert not ANSI_ESCAPE.search(out)
    assert "AGENTSWEEP" not in out


def test_json_mode_clean_history_exits_zero(tmp_path, capsys):
    root = _mkroot(tmp_path, '{"message":"hello world"}\n')
    code = main(["--root", str(root), "--json"])
    out = capsys.readouterr().out

    assert code == 0
    assert json.loads(out) == []


def test_scan_exit_codes(tmp_path, capsys):
    dirty = _mkroot(tmp_path)
    assert main(["--root", str(dirty)]) == 1

    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "s.jsonl").write_text('{"message":"hi"}\n', encoding="utf-8")
    assert main(["--root", str(clean)]) == 0


def test_human_output_pipeline_and_masking(tmp_path, capsys):
    root = _mkroot(tmp_path)
    code = main(["--root", str(root)])
    out = capsys.readouterr().out

    assert code == 1
    assert "AGENTSWEEP" in out
    for stage_name in ("DISCOVER", "SCAN", "FINDINGS", "REDACT", "ROTATE"):
        assert stage_name in out
    assert "ACTION REQUIRED" in out
    # Raw secret values must never reach the screen — masked forms only.
    assert AWS_KEY not in out
    assert GH_TOKEN not in out


def test_fix_redacts_end_to_end_with_force(tmp_path, capsys):
    root = _mkroot(tmp_path)
    code = main(["--root", str(root), "--fix", "--force"])

    assert code == 0
    content = (root / "session.jsonl").read_text(encoding="utf-8")
    assert AWS_KEY not in content
    assert "[REDACTED:aws-access-key]" in content
    assert "[REDACTED:github-pat]" in content
    assert (root / "session.jsonl.bak").exists()
