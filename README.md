# AgentSweep

> Find and redact secrets (API keys, tokens, private keys, DB URLs) that got pasted into your AI coding agent's local history.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/Ishannaik/agent-sweep)

**Status:** alpha. Works on Claude Code today. Codex, Aider, Cursor, Continue via contributed `Source` adapters — see [CONTRIBUTING.md](CONTRIBUTING.md).

## The problem

Claude Code (and every other AI coding CLI) stores your full conversation history as plain-text JSONL on disk — under `~/.claude/projects/` for Claude Code. Anything you paste — an AWS key, a `.env` file, a database URL — sits in clear text indefinitely. A typical dev's history accumulates dozens of secrets over months, often without them realizing.

`agentsweep` scans that history, tells you what leaked, and can redact the secret values in place while preserving the JSONL structure byte-for-byte. It also tells you which keys to rotate, with the right revocation URL for each provider.

## Install

```
pip install agentsweep
```

Requires Python 3.10+. One dependency: [`rich`](https://github.com/Textualize/rich), for the pipeline terminal UI. Output degrades to plain text automatically when piped, and `--json` is always styling-free.

## Usage

Scan (read-only, safe):

```
agentsweep
```

Redact in place (creates `.bak` backups):

```
agentsweep --fix --allow-production
```

Point at an arbitrary folder (e.g. a copy of your history):

```
agentsweep --root /path/to/jsonl-files --fix
```

Machine-readable output:

```
agentsweep --json
```

## Corruption-prevention guarantees

A redactor that corrupts your history is strictly worse than the leak it's fixing. agentsweep enforces these invariants on every `--fix`:

1. **Redaction happens in parsed JSON, not on raw bytes.** Secrets are replaced as string *values* inside the parsed structure, then re-serialized. Structural damage is impossible by construction.
2. **Atomic writes.** Every rewrite goes: temp file → `fsync()` → `os.replace()` over the original. A crash at any instant leaves either the complete old file or the complete new file — never a torn write.
3. **Post-write validation.** Before committing, every non-empty line in the new content must parse as JSON, and the line count must match the original. If either check fails, the write aborts and the original is untouched.
4. **`.bak` backup by default.** Refuses to run if a `.bak` already exists (so prior backups can't be clobbered).
5. **Path containment.** Refuses any target that doesn't resolve inside the source's root.
6. **Symlink rejection.** Refuses symlinks outright.
7. **mtime window.** Refuses files modified in the last 60 seconds (likely an active session). `--force` overrides.
8. **Running-process check.** Refuses if a Claude Code process appears to be running. `--force` overrides.
9. **Alpha-stage production gate.** `--fix` against the default `~/.claude/projects/` root requires `--allow-production` until v1.0.
10. **Audit log.** Every write appends SHA256 before/after and path to `~/.claude/agentsweep-audit.jsonl`.

## Recovery

Every redacted file has a sibling `*.bak` with the original bytes. To undo:

```
mv session.jsonl.bak session.jsonl
```

## What's detected

~20 high-confidence patterns: AWS access keys, GitHub tokens (PAT/OAuth/App/fine-grained), Stripe live/test, OpenAI, Anthropic, Google API, Slack bot/user/webhook, Hugging Face, JWT, PEM private keys, DB URLs with embedded passwords, npm/PyPI/SendGrid/Twilio tokens. Patterns are high-precision — false positives are rare.

## What's NOT detected

- Custom/proprietary secrets without a recognizable prefix.
- Unknown tokens that look like arbitrary base64.
- Secrets split across multiple messages.
- Anything inside a binary/non-UTF-8 file.

For deeper detection, run `gitleaks` or `trufflehog` alongside agentsweep — their rule packs are more exhaustive. agentsweep's value is the **Claude-Code-specific surface**, not the detection engine.

## License

MIT. See LICENSE.
