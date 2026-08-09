# Battle card: gitleaks

AgentSweep, 2026-08-09. The most important card here, because gitleaks is what the user already has installed.

## Who they are

28,550 stars, MIT, last push 2026-07-29 `[Data]`. The default secret scanner. Free forever for CLI use.

## Where they genuinely win

- **Ubiquity.** Already in the reader's CI and often on their laptop. Nothing beats a tool you do not have to install.
- **Git history.** Scans every commit ever made. AgentSweep does not do this and should not try.
- **It really does scan plain directories.** `gitleaks dir ~/.claude` works today, on a non-git path `[Data, run locally]`. Do not claim otherwise; it is checkable in ten seconds and being caught destroys the rest of the pitch.
- **Maturity.** Seven years of rule tuning and false-positive work.

## Where they lose

Measured 2026-08-09, five realistic keys in a Claude Code style JSONL file, same directory for both tools `[Data]`:

- gitleaks 8.30.1 found **2 of 5**: `github-pat` and `slack-legacy-bot-token`.
- It missed the Anthropic key, the AWS key and the OpenAI key.
- AgentSweep found **5 of 5**.
- Retested as plain `KEY=value` lines in a `.txt`, the format most favourable to gitleaks: 1 of 3, and only as `generic-api-key`.
- gitleaks does **not** detect `sk-ant-oat01-`, the token Claude Code writes to `~/.claude/.credentials.json` after login `[Data, tested]`.

They also do not redact. gitleaks tells you a secret is there; the file still contains it afterwards.

## The honest answer to "why not just use gitleaks?"

Because on the files this is about, it finds two out of five, and then leaves all five where they were.

That sentence is reproducible, which is why it works. Anyone can plant five keys in a JSONL file and run both. Give them the command rather than asking them to trust the number.

## Where they could kill this

One PR adding vendor rules and a `~/.claude` recipe to their docs closes most of the detection gap `[Opinion]`. The redaction gap is harder, because writing to a user's files needs safety guarantees they have no reason to build.

## Caveat to check before using this externally

Only the **default** gitleaks config was tested. If a tuned config closes the gap, the headline number is misleading. Test that before this card goes anywhere public.
