# Pipeline terminal UI for agentsweep

**Date:** 2026-06-11 · **Status:** approved (chat) · **Owner:** Ishan

## Goal

Replace agentsweep's plain `print()` output with a staged-pipeline terminal UI
(hacker/security-tool aesthetic) built on `rich`, without changing any logic,
exit code, or the `--json` contract.

## Decisions made

- **Dependency:** add `rich` as a runtime dependency. Drop the "zero
  dependencies" badge/claim from the README.
- **Aesthetic:** hacker/security-tool (red/yellow accents, box-drawing,
  banner), per user selection.
- **Shape:** every human run renders as a 5-stage pipeline:
  `[1/5] DISCOVER → [2/5] SCAN → [3/5] FINDINGS → [4/5] REDACT → [5/5] ROTATE`,
  each stage resolving to ✔ (green) / ✘ (red) / ⊘ (dim, skipped) / ⚠ (yellow).

## Stage behavior

| Stage | Scan-only, clean | Scan-only, findings | --fix, findings |
|---|---|---|---|
| DISCOVER | ✔ source · N files · root | same | same |
| SCAN | ✔ N files · M strings · t s | same | same |
| FINDINGS | ✔ "no secrets found" | ✘ count + red table (rule, masked, file, line) | same |
| REDACT | ⊘ nothing to redact | ⊘ "run with --fix" | per-file OK/SKIP/FAIL rows; ✘ if a gate blocks |
| ROTATE | ⊘ nothing to rotate | ⚠ + ACTION REQUIRED panel | same |

Rotation guidance panel (red double border) now renders whenever findings
exist, not only after `--fix` — rotating matters even before redacting.
This is the one deliberate behavior addition.

Safety-gate refusals (production root, Claude Code running) render as yellow
panels on **stderr**. Panel body lines stay under ~70 chars so the test
phrases `default production root` and `--allow-production` never wrap.

## Invariants (unchanged)

- `--json`: machine-clean JSON on stdout, no banner, no ANSI, no rich.
- Exit codes: 0 clean / 1 findings (scan) / 2 gate-blocked or write errors.
- Raw secret values are never printed — masked only (already true).
- Errors and skips go to stderr.
- Auto-degrade: rich disables color/animation when output is piped;
  icons and boxes fall back to ASCII when the stream encoding can't
  encode them (Windows cp1252 pipes).

## Structure

- New `src/agentsweep/ui.py` — owns ALL presentation (banner, stage lines,
  findings table, redact rows, panels). No business logic.
- `cli.py` keeps argparse + orchestration, calls `ui.*`. scanner/redactor/
  sources/preflight untouched.

## Testing

- All existing tests pass unchanged (gate test asserts stderr phrases).
- New: `--json` output parses as JSON and contains no ANSI escapes;
  exit code 1 on findings / 0 clean; raw secret absent from human stdout;
  pipeline stages present in human output.
