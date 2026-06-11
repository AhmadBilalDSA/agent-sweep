"""Pre-filter correctness + catastrophic-input timing for the full rule set."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentsweep import scanner  # noqa: E402
from agentsweep.scanner import _PREFILTER, scan_text  # noqa: E402


# Large single-line inputs that previously summed to multi-second scans.
BOMBS = {
    "repeated-char": "a" * 50000,
    "curl-flood": "curl " * 10000,
    "assignment-flood": "token=abc123 " * 4000,
    "path-flood": "https://" + "x/" * 20000,
    "hex-blob": "deadbeef" * 8000,
}


@pytest.mark.parametrize("name", list(BOMBS))
def test_no_catastrophic_scan_time(name):
    t0 = time.perf_counter()
    scan_text(BOMBS[name])
    assert time.perf_counter() - t0 < 1.0, f"{name} scan too slow"


def test_full_scan_of_all_bombs_is_fast():
    t0 = time.perf_counter()
    for text in BOMBS.values():
        scan_text(text)
    # Five pathological 50-80KB inputs back to back. Keyword-gating the
    # context rules took this from ~9s to ~1.6s; the floor is now ~60
    # anchored rules each doing one honest linear pass (no backtracking).
    # 3s leaves headroom for slow CI while still catching the old blowup.
    assert time.perf_counter() - t0 < 3.0


def test_prefilter_literals_are_truly_present_in_fixtures():
    """Every prefiltered rule's own fixture must contain a prefilter literal,
    otherwise the gate would skip a real secret. (Belt-and-suspenders on top
    of the parametrized fixture-detection tests.)"""
    from test_ported_rules import FIXTURES  # type: ignore

    for rule_id, kws in _PREFILTER.items():
        fixture = FIXTURES.get(rule_id)
        if fixture is None:
            continue
        low = fixture.lower()
        assert any(k in low for k in kws), \
            f"{rule_id}: fixture lacks any prefilter literal {kws}"


def test_prefilter_only_covers_context_rules():
    # Anchored-prefix rules (glpat-, dop_v1_, AKIA...) don't need gating and
    # must not be accidentally swept in with a bogus literal.
    assert "aws-access-key" not in _PREFILTER
    assert "gitlab-pat" not in _PREFILTER
    # ...but the slow context rules are gated.
    assert "jfrog-api-key" in _PREFILTER
    assert set(_PREFILTER["jfrog-api-key"]) == {
        "jfrog", "artifactory", "bintray", "xray"}


def test_prefilter_does_not_change_findings():
    """Gating must be lossless: a string containing a context keyword still
    runs the rule exactly as before."""
    # snyk rule fires with the keyword present...
    hit = ("snyk_token = "
           "12345678-1234-1234-1234-123456789abc")
    assert any(f.rule == "snyk" for f in scan_text(hit))
    # ...and a uuid with no provider keyword nearby does not.
    assert not any(f.rule == "snyk"
                   for f in scan_text("12345678-1234-1234-1234-123456789abc"))
