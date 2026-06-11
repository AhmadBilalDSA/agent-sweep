"""Tests for .agentsweepignore support.

Covers:
  - ignore.IgnoreSet, load(), fingerprint() directly
  - suppression in pipeline._scan_all (via cli.main)
  - rule:<id> suppresses all findings of that rule
  - relpath:line:rule fingerprint suppresses exactly one
  - literal value line suppresses by secret value
  - comments and blank lines are ignored
  - --no-ignore bypasses the file entirely
  - human-mode prints suppressed-count warning; --json reports it on stderr
  - ignore file found in BOTH scan root and cwd
  - round-trip: fingerprint from JSON payload matches what goes in the file
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentsweep import ignore as ignore_mod  # noqa: E402
from agentsweep.ignore import IgnoreSet, IGNORE_FILENAME, fingerprint, load  # noqa: E402
from agentsweep.cli import main  # noqa: E402

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GH_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"

# A JSONL line that embeds both fake secrets (never a contiguous token here).
_SECRET_LINE = (
    '{"type":"user","message":{"content":[{"type":"text",'
    f'"text":"key={AWS_KEY} and token {GH_TOKEN}"' + "}]}}\n"
)
# A JSONL line with only the AWS key.
_AWS_ONLY_LINE = (
    '{"type":"user","message":{"content":[{"type":"text",'
    f'"text":"key={AWS_KEY}"' + "}]}}\n"
)


# ---------------------------------------------------------------------------
# Autouse fixture: isolate HOME so tests never touch ~/.claude
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mkroot(tmp_path: Path, content: str = _SECRET_LINE) -> Path:
    root = tmp_path / "history"
    root.mkdir(exist_ok=True)
    (root / "session.jsonl").write_text(content, encoding="utf-8")
    return root


def _scan_json(root: Path, extra_args: list[str] | None = None, capsys=None):
    """Run `agentsweep scan --root ROOT --json [extra_args]` and return
    (exit_code, payload_list, stderr_text)."""
    argv = ["scan", "--root", str(root), "--json"] + (extra_args or [])
    code = main(argv)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    return code, payload, captured.err


# ===========================================================================
# Unit tests: IgnoreSet / load / fingerprint
# ===========================================================================

class TestFingerprint:
    def test_format_is_relpath_line_rule(self):
        assert fingerprint("some/file.jsonl", 5, "aws-access-key") == \
               "some/file.jsonl:5:aws-access-key"

    def test_different_args_produce_different_fingerprints(self):
        fp1 = fingerprint("a.jsonl", 1, "aws-access-key")
        fp2 = fingerprint("a.jsonl", 2, "aws-access-key")
        fp3 = fingerprint("b.jsonl", 1, "aws-access-key")
        fp4 = fingerprint("a.jsonl", 1, "github-pat")
        assert len({fp1, fp2, fp3, fp4}) == 4


class TestIgnoreSetAddLine:
    def test_rule_prefix_goes_to_rules(self):
        ig = IgnoreSet()
        ig.add_line("rule:aws-access-key")
        assert "aws-access-key" in ig.rules
        assert not ig.fingerprints
        assert not ig.values

    def test_rule_prefix_strips_whitespace(self):
        ig = IgnoreSet()
        ig.add_line("rule: aws-access-key ")
        assert "aws-access-key" in ig.rules

    def test_fingerprint_pattern_goes_to_fingerprints(self):
        ig = IgnoreSet()
        ig.add_line("session.jsonl:1:aws-access-key")
        assert "session.jsonl:1:aws-access-key" in ig.fingerprints
        assert not ig.rules
        assert not ig.values

    def test_literal_value_goes_to_values(self):
        ig = IgnoreSet()
        ig.add_line(AWS_KEY)
        assert AWS_KEY in ig.values
        assert not ig.rules
        assert not ig.fingerprints

    def test_comment_lines_are_skipped(self):
        ig = IgnoreSet()
        ig.add_line("# this is a comment")
        ig.add_line("  # indented comment")
        assert not ig.rules and not ig.fingerprints and not ig.values

    def test_blank_lines_are_skipped(self):
        ig = IgnoreSet()
        ig.add_line("")
        ig.add_line("   ")
        assert not ig.rules and not ig.fingerprints and not ig.values

    def test_bool_false_when_empty(self):
        ig = IgnoreSet()
        assert not ig

    def test_bool_true_when_has_rule(self):
        ig = IgnoreSet()
        ig.add_line("rule:aws-access-key")
        assert ig

    def test_bool_true_when_has_fingerprint(self):
        ig = IgnoreSet()
        ig.add_line("session.jsonl:1:github-pat")
        assert ig

    def test_bool_true_when_has_value(self):
        ig = IgnoreSet()
        ig.add_line(AWS_KEY)
        assert ig


class TestIgnoreSetMatches:
    def test_rule_match_suppresses_any_finding_of_that_rule(self):
        ig = IgnoreSet()
        ig.add_line("rule:aws-access-key")
        assert ig.matches("aws-access-key", "whatever", "file.jsonl:1:aws-access-key")

    def test_rule_match_does_not_suppress_other_rules(self):
        ig = IgnoreSet()
        ig.add_line("rule:aws-access-key")
        assert not ig.matches("github-pat", GH_TOKEN, "file.jsonl:1:github-pat")

    def test_fingerprint_match_suppresses_exactly_one_location(self):
        ig = IgnoreSet()
        ig.add_line("session.jsonl:1:aws-access-key")
        # matches the exact fingerprint
        assert ig.matches("aws-access-key", AWS_KEY, "session.jsonl:1:aws-access-key")
        # does NOT match a different line
        assert not ig.matches("aws-access-key", AWS_KEY, "session.jsonl:2:aws-access-key")
        # does NOT match a different file
        assert not ig.matches("aws-access-key", AWS_KEY, "other.jsonl:1:aws-access-key")

    def test_value_match_suppresses_by_secret_content(self):
        ig = IgnoreSet()
        ig.add_line(AWS_KEY)
        assert ig.matches("aws-access-key", AWS_KEY, "session.jsonl:1:aws-access-key")
        # does NOT match a different secret value
        assert not ig.matches("aws-access-key", "AKIAOTHER12345678901", "f:1:aws-access-key")

    def test_no_match_returns_false(self):
        ig = IgnoreSet()
        ig.add_line("rule:aws-access-key")
        assert not ig.matches("github-pat", GH_TOKEN, "f:1:github-pat")


class TestLoad:
    def test_load_from_root_dir(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")

        ig = load([root])
        assert "aws-access-key" in ig.rules
        assert len(ig.sources) == 1

    def test_load_missing_file_returns_empty_set(self, tmp_path):
        ig = load([tmp_path / "no-such-dir"])
        assert not ig
        assert ig.sources == []

    def test_load_deduplicates_same_file_via_two_roots(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")

        # Pass the same directory twice
        ig = load([root, root])
        assert ig.sources.count(next(iter(ig.sources))) == 1  # only once

    def test_load_merges_root_and_cwd(self, tmp_path):
        root = tmp_path / "root"
        cwd = tmp_path / "cwd"
        root.mkdir()
        cwd.mkdir()
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        (cwd / IGNORE_FILENAME).write_text("rule:github-pat\n", encoding="utf-8")

        ig = load([root, cwd])
        assert "aws-access-key" in ig.rules
        assert "github-pat" in ig.rules
        assert len(ig.sources) == 2

    def test_load_ignores_unreadable_file(self, tmp_path):
        # Write a non-UTF-8 bytes file (latin-1 with non-UTF-8 byte)
        root = tmp_path / "root"
        root.mkdir()
        (root / IGNORE_FILENAME).write_bytes(b"rule:aws-access-key\nval\xe9ue\n")
        # Should not raise; will skip the bad file
        ig = load([root])
        # The file is skipped because of UnicodeDecodeError
        assert ig.sources == []


# ===========================================================================
# End-to-end: suppression through cli.main scan
# ===========================================================================

class TestRuleSuppression:
    """rule:<id> line suppresses ALL findings of that rule."""

    def test_rule_suppression_exits_0_when_all_suppressed(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 0
        assert payload == []

    def test_rule_suppression_only_removes_matched_rule(self, tmp_path, capsys):
        # Both AWS and GH tokens present, only AWS suppressed by rule
        root = _mkroot(tmp_path, _SECRET_LINE)
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 1
        rules = {f["rule"] for f in payload}
        assert "aws-access-key" not in rules
        assert "github-pat" in rules

    def test_rule_suppression_stderr_shows_count(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _SECRET_LINE)
        (root / IGNORE_FILENAME).write_text(
            "rule:aws-access-key\nrule:github-pat\n", encoding="utf-8"
        )
        code, payload, err = _scan_json(root, capsys=capsys)
        assert code == 0
        assert "suppressed" in err
        assert "2" in err


class TestFingerprintSuppression:
    """relpath:line:rule fingerprint suppresses exactly one finding."""

    def test_fingerprint_suppresses_exactly_one(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _SECRET_LINE)
        # First scan to get the real fingerprint
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 1
        aws_fp = next(f["fingerprint"] for f in payload if f["rule"] == "aws-access-key")

        # Write the fingerprint as an ignore rule
        (root / IGNORE_FILENAME).write_text(aws_fp + "\n", encoding="utf-8")

        code2, payload2, err2 = _scan_json(root, capsys=capsys)
        assert code2 == 1  # github-pat still found
        assert not any(f["rule"] == "aws-access-key" for f in payload2)
        assert any(f["rule"] == "github-pat" for f in payload2)
        assert "1" in err2 and "suppressed" in err2

    def test_fingerprint_does_not_suppress_different_line(self, tmp_path, capsys):
        """Writing two identical secrets on two lines: fingerprinting line 1
        must not suppress the identical secret on line 2."""
        root = tmp_path / "history"
        root.mkdir()
        (root / "session.jsonl").write_text(
            _AWS_ONLY_LINE + _AWS_ONLY_LINE, encoding="utf-8"
        )
        # First scan to obtain both fingerprints
        code, payload, _ = _scan_json(root, capsys=capsys)
        # Should have two findings at lines 1 and 2
        assert len(payload) == 2
        fp_line1 = next(f["fingerprint"] for f in payload if f["line"] == 1)

        # Suppress only line 1
        (root / IGNORE_FILENAME).write_text(fp_line1 + "\n", encoding="utf-8")

        code2, payload2, err2 = _scan_json(root, capsys=capsys)
        assert len(payload2) == 1
        assert payload2[0]["line"] == 2
        assert "1" in err2 and "suppressed" in err2


class TestLiteralValueSuppression:
    """A bare literal value line suppresses any finding whose secret matches."""

    def test_literal_value_suppresses_finding(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text(AWS_KEY + "\n", encoding="utf-8")
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 0
        assert payload == []

    def test_literal_value_does_not_suppress_different_value(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        # Put a *different* AWS-shaped key in the ignore file
        (root / IGNORE_FILENAME).write_text("AKIAOTHER123456789AB\n", encoding="utf-8")
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 1
        assert any(f["rule"] == "aws-access-key" for f in payload)


class TestCommentsAndBlankLines:
    """Comments and blank lines must be silently ignored."""

    def test_comments_and_blanks_do_not_cause_suppression(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text(
            "# this is a comment\n"
            "\n"
            "   \n"
            "# another comment\n",
            encoding="utf-8",
        )
        code, payload, _ = _scan_json(root, capsys=capsys)
        # Nothing should be suppressed; AWS key still found
        assert code == 1
        assert any(f["rule"] == "aws-access-key" for f in payload)

    def test_ignore_file_with_only_comments_is_inert(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text("# only a comment\n", encoding="utf-8")
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 1


class TestNoIgnoreFlag:
    """--no-ignore bypasses the ignore file entirely."""

    def test_no_ignore_bypasses_rule_suppression(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        code, payload, err = _scan_json(root, extra_args=["--no-ignore"], capsys=capsys)
        assert code == 1
        assert any(f["rule"] == "aws-access-key" for f in payload)
        # suppressed count should NOT appear in stderr
        assert "suppressed" not in err

    def test_no_ignore_bypasses_fingerprint_suppression(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _SECRET_LINE)
        # Scan first to get a fingerprint
        code, payload, _ = _scan_json(root, capsys=capsys)
        aws_fp = next(f["fingerprint"] for f in payload if f["rule"] == "aws-access-key")
        (root / IGNORE_FILENAME).write_text(aws_fp + "\n", encoding="utf-8")

        code2, payload2, _ = _scan_json(root, extra_args=["--no-ignore"], capsys=capsys)
        assert any(f["rule"] == "aws-access-key" for f in payload2)

    def test_no_ignore_bypasses_literal_value_suppression(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text(AWS_KEY + "\n", encoding="utf-8")
        code, payload, _ = _scan_json(root, extra_args=["--no-ignore"], capsys=capsys)
        assert code == 1
        assert any(f["rule"] == "aws-access-key" for f in payload)


class TestSuppressedCountOutput:
    """Suppressed count is reported correctly in both human and --json modes."""

    def test_json_mode_stderr_shows_suppressed_count(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _SECRET_LINE)
        (root / IGNORE_FILENAME).write_text(
            "rule:aws-access-key\nrule:github-pat\n", encoding="utf-8"
        )
        code, payload, err = _scan_json(root, capsys=capsys)
        assert code == 0
        assert payload == []
        assert "suppressed" in err
        assert "2" in err

    def test_json_mode_no_suppressed_when_nothing_ignored(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        # No ignore file
        code, payload, err = _scan_json(root, capsys=capsys)
        assert code == 1
        assert "suppressed" not in err

    def test_human_mode_stderr_shows_suppressed_warning(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _SECRET_LINE)
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        code = main(["scan", "--root", str(root)])
        captured = capsys.readouterr()
        # AWS suppressed; GH still found → exit 1
        assert code == 1
        assert "suppressed by .agentsweepignore" in captured.err

    def test_human_mode_no_warning_when_nothing_suppressed(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        code = main(["scan", "--root", str(root)])
        captured = capsys.readouterr()
        assert "suppressed" not in captured.err


class TestIgnoreFileDiscovery:
    """Ignore file is discovered in scan root AND cwd."""

    def test_ignore_file_in_scan_root(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 0
        assert payload == []

    def test_ignore_file_in_cwd(self, tmp_path, monkeypatch, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        # Write ignore file in a separate cwd directory (not in root)
        cwd = tmp_path / "workdir"
        cwd.mkdir()
        (cwd / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")

        monkeypatch.chdir(cwd)
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 0
        assert payload == []

    def test_ignore_files_in_both_root_and_cwd_are_merged(
            self, tmp_path, monkeypatch, capsys):
        root = _mkroot(tmp_path, _SECRET_LINE)
        cwd = tmp_path / "workdir"
        cwd.mkdir()
        # Root ignores AWS key, cwd ignores GH token
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        (cwd / IGNORE_FILENAME).write_text("rule:github-pat\n", encoding="utf-8")

        monkeypatch.chdir(cwd)
        code, payload, err = _scan_json(root, capsys=capsys)
        assert code == 0
        assert payload == []
        # Both suppressed
        assert "2" in err and "suppressed" in err

    def test_same_dir_as_root_and_cwd_deduplicates(self, tmp_path, monkeypatch, capsys):
        """When cwd == scan root the ignore file must not be counted twice."""
        root = _mkroot(tmp_path, _SECRET_LINE)
        # Rule ignores only AWS; GH token should still be found
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")

        monkeypatch.chdir(root)
        code, payload, err = _scan_json(root, capsys=capsys)
        # GH token still found → exit 1
        assert code == 1
        rules = {f["rule"] for f in payload}
        assert "github-pat" in rules
        assert "aws-access-key" not in rules
        # Only 1 suppressed (not 2), because deduplication of the file
        assert "1" in err and "suppressed" in err


class TestFingerprintRoundTrip:
    """Fingerprint from JSON payload can be pasted into .agentsweepignore (round-trip)."""

    def test_fingerprint_field_matches_ignore_fingerprint_format(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _SECRET_LINE)
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 1
        for item in payload:
            expected = fingerprint(
                # The relpath in the fingerprint is relative to root
                item["fingerprint"].rsplit(":", 2)[0],  # extract relpath portion
                item["line"],
                item["rule"],
            )
            assert item["fingerprint"] == expected

    def test_round_trip_paste_fingerprint_into_ignore_file(self, tmp_path, capsys):
        """Take the fingerprint from the JSON output and use it as an ignore rule."""
        root = _mkroot(tmp_path, _SECRET_LINE)
        # Step 1: scan to get fingerprints
        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 1
        aws_fp = next(f["fingerprint"] for f in payload if f["rule"] == "aws-access-key")
        gh_fp = next(f["fingerprint"] for f in payload if f["rule"] == "github-pat")

        # Step 2: paste both fingerprints into the ignore file
        (root / IGNORE_FILENAME).write_text(
            f"{aws_fp}\n{gh_fp}\n", encoding="utf-8"
        )

        # Step 3: rescan — everything should be suppressed
        code2, payload2, err2 = _scan_json(root, capsys=capsys)
        assert code2 == 0
        assert payload2 == []
        assert "2" in err2 and "suppressed" in err2

    def test_fingerprint_relpath_is_relative_to_root(self, tmp_path, capsys):
        """The relpath portion of the fingerprint must be relative to scan root."""
        root = tmp_path / "history"
        subdir = root / "subdir"
        subdir.mkdir(parents=True)
        (subdir / "session.jsonl").write_text(_AWS_ONLY_LINE, encoding="utf-8")

        code, payload, _ = _scan_json(root, capsys=capsys)
        assert code == 1
        fp = payload[0]["fingerprint"]
        # relpath must be relative (not an absolute path)
        assert not Path(fp.rsplit(":", 2)[0]).is_absolute()
        # Must contain the subdir name
        assert "subdir" in fp


class TestVerbDispatch:
    """Ignore also works when called via the 'scan' verb and legacy --root."""

    def test_scan_verb_respects_ignore(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        code = main(["scan", "--root", str(root), "--json"])
        out = capsys.readouterr().out
        assert code == 0
        assert json.loads(out) == []

    def test_legacy_flag_form_respects_ignore(self, tmp_path, capsys):
        root = _mkroot(tmp_path, _AWS_ONLY_LINE)
        (root / IGNORE_FILENAME).write_text("rule:aws-access-key\n", encoding="utf-8")
        # Legacy: no verb, just --root
        code = main(["--root", str(root), "--json"])
        out = capsys.readouterr().out
        assert code == 0
        assert json.loads(out) == []
