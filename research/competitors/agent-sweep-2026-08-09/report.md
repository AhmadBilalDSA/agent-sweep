# AgentSweep competitive report

Generated 2026-08-09. Every claim is tagged `[Data]`, `[Estimate]`, `[Assumption]` or `[Opinion]`. An untagged number is a bug.

## Executive summary

The belief this research was aimed at was "nobody else scans AI agent history for secrets", and it is no longer true `[Data]`. Two direct competitors appeared in the last five weeks, and AgentSweep leads them 56 stars to 7 and 3, so the wedge was real but the window is closing `[Data]`. The incumbent threat is weaker than it looks: `gitleaks dir` does scan non-git directories, but on an identical Claude Code history file gitleaks 8.30.1 found 2 of 5 planted keys where AgentSweep found 5 of 5 `[Data, measured 2026-08-09]`. The market has a citable validating incident in CVE-2026-21852, "Claude Code Leaks Data via Malicious Environment Configuration Before Trust Confirmation" `[Data]`. The strongest defensible position is not detection, which is commoditised, but in-place redaction with corruption-prevention guarantees, which no competitor in this niche ships `[Data on competitors' own descriptions, Opinion on defensibility]`.

## Market concentration

**Fragmented, and newly contested** `[Opinion, from the data below]`.

The general secret-scanning category is consolidated around gitleaks and TruffleHog at roughly 28k stars each `[Data]`. The AI-agent-history niche has no incumbent at all: the largest entrant is AgentSweep at 56 `[Data]`. That is a niche where the leader is 500x smaller than the adjacent category leader, which means the niche is either too small to matter or too new to have been noticed `[Opinion]`. The arrival of two competitors in five weeks argues for too new `[Estimate]`.

## Pass 1: the field

### Direct competitors

Tools that read local AI agent history specifically. All figures fetched from the GitHub API on 2026-08-09 `[Data]`.

| Tool | Stars | Created | Last push | Lang | Licence | What it does |
|---|---|---|---|---|---|---|
| **AgentSweep** | 56 | 2026-06-11 | 2026-08-09 | Python | MIT | Scan + **redact**, 31 agents, 202 rules, offline |
| DidILeak | 7 | 2026-07-02 | 2026-07-06 | Python | MIT | Scan ChatGPT/Claude/Cursor/Kimi history, HTML dashboard, rotation guides |
| transcript-sentinel | 3 | 2026-08-03 | 2026-08-04 | Go | Apache-2.0 | Interactive TUI auditing agent transcripts, histories, local state |
| densyy/github-secret-scanner | 1 | 2026-08-02 | 2026-08-02 | ? | none | Agent *skill* wrapping git-history scanning |

DidILeak has not been touched in 34 days and has 0 forks `[Data]`. transcript-sentinel is 6 days old `[Data]`. Neither is dead and neither is established `[Opinion]`.

### Adjacent, which matters more

| Tool | Stars | Angle | Why it competes |
|---|---|---|---|
| Pantheon-Security/medusa | 959 | AI-first scanner, "Claude Code compromise detection", 40,000+ patterns | 17x AgentSweep's stars, already inside `.claude/`, could add history scanning in a sprint `[Opinion]` |
| Offsend | 11 | `.offsend.yml` keeps secrets *out* of AI context, syncs ignore files | Prevention rather than cleanup, which is the better product if it works `[Opinion]` |
| jricramc/aigate | 6 | Local proxy + Claude Code hook blocking secrets pre-send | Same prevention wedge, dormant since 2026-04-04 `[Data]` |
| unixwzrd/Secrets-Kit | 4 | Keychain-backed runtime secrets on macOS | Removes the reason keys are on disk at all |

**medusa is the competitor to actually watch** `[Opinion]`. It already ships Claude Code security features, has 959 stars and 154 forks, and pushed on 2026-08-03 `[Data]`. Adding transcript scanning to a scanner that already parses `.claude/` is a small step `[Estimate]`.

### The real incumbent: doing it with gitleaks

The skill's own warning is that the most common way a dev tool dies is losing to a default. So this was measured rather than argued.

**Method** `[Data, 2026-08-09]`: five realistic high-entropy keys (Anthropic `sk-ant-api03-`, AWS `AKIA…`, GitHub `ghp_`, OpenAI `sk-proj-`, Slack `xoxb-`) planted in a JSONL file shaped like a Claude Code session, in a non-git directory. Then gitleaks 8.30.1 `dir` and AgentSweep 0.1.9 `scan --root` over the same directory.

| | gitleaks 8.30.1 | AgentSweep 0.1.9 |
|---|---|---|
| Found | **2 of 5** | **5 of 5** |
| Which | `github-pat`, `slack-legacy-bot-token` | anthropic, aws-access-key, github-pat, openai, slack-bot |
| Missed | Anthropic, AWS, OpenAI | none |

Re-tested in the format most favourable to gitleaks, plain `.txt` with `KEY=value` lines: gitleaks found 1 of 3, and only as `generic-api-key` rather than a vendor rule `[Data]`.

Separately, gitleaks 8.30.1 does **not** detect `sk-ant-oat01-`, the Claude Code OAuth token `[Data, tested]`. That is the token stored at `~/.claude/.credentials.json` after login, so it is the single credential most likely to be sitting in a Claude Code user's home directory.

**Reading this honestly.** The workflow gap is smaller than the detection gap. Anyone can type `gitleaks dir ~/.claude` today and it runs `[Data]`. What they cannot do is get the vendor-specific coverage or any redaction. So the pitch is not "there is no way to do this", it is "the way you already have misses most of it" `[Opinion]`.

## Pass 2: what customers say

**DATA GAP, and it is the significant one.** The delegated research returned ten quotes attributed to Reddit, Hacker News, DEV and GitGuardian, but the source links resolved only to bare domains (`reddit.com/r/ClaudeAI`, `dev.to`, `github.com`) rather than to individual posts `[Data]`. Unverifiable quotes are not evidence, so none are reproduced here. The vocabulary list below is therefore tagged `[Assumption]` and needs a second pass with a tool that returns deep links before any of it goes into landing-page copy.

Candidate vocabulary, unverified `[Assumption]`: "transcript residue", "shadow storage", "allow-rule leaks", "context ingestion".

What is verified:

- **CVE-2026-21852**, "Claude Code Leaks Data via Malicious Environment Configuration Before Trust Confirmation", affected product `claude-code` `[Data, MITRE CVE record fetched 2026-08-09]`. This is the citable proof that the category is real and not a hypothetical.
- **ashlrai/phantom-secrets**, 12 stars `[Data]`, a synthetic-token-proxy approach: replace real keys in `.env` with placeholders and inject the real value at the network layer. That is a genuinely different answer to the same problem, and if it works it is strictly better than cleanup `[Opinion]`.

## Pass 3: go-to-market

AgentSweep traction `[Data, 2026-08-09]`: 56 stars, 36 forks, PyPI 111 downloads last month, 10 last week, 4 last day.

The fork-to-star ratio of 0.64 is extremely high for a CLI tool `[Data]`. Forks usually track contributors rather than users, and this repo has run a heavy good-first-issue programme, so the ratio likely reflects contributor recruitment succeeding while user acquisition has not `[Estimate]`. 111 monthly downloads against 56 stars says the same thing: people are starring and forking it, and few are running it `[Opinion]`.

**That is the finding that matters more than any competitor.** The constraint is not the field getting crowded, it is that almost nobody is using the tool `[Opinion]`.

On channels, per the standing rule: Hacker News and Product Hunt are worth mining for sentiment and are dead as launch distribution. No channel recommendation is made here, because that needs live research this run did not complete `[Assumption]`.

## Where to compete

1. **Redaction, not detection** `[Opinion]`. Detection is commoditised by two 28k-star tools. No direct competitor's own description mentions redacting in place `[Data, from their GitHub descriptions]`. AgentSweep's corruption-prevention invariants (atomic replace, mandatory backup, post-write validation, line-count preservation) are the hard part to copy.
2. **Vendor coverage as a measurable claim** `[Opinion]`. "gitleaks finds 2 of these 5, we find 5" is a reproducible benchmark, and reproducibility is what makes a comparison survive contact with a skeptic.
3. **The 31-agent surface** `[Data]`. DidILeak covers 4 named agents, transcript-sentinel is unspecified. Breadth is defensible for as long as the agent ecosystem keeps fragmenting.

## Where not to compete

1. **Do not fight gitleaks on general secret scanning** `[Opinion]`. 28,550 stars, MIT, everyone has it.
2. **Do not claim the space is empty.** It is not, and a reviewer who finds DidILeak in thirty seconds discounts everything else said `[Opinion]`.
3. **Do not build prevention-by-proxy** `[Opinion]`. Offsend, aigate and phantom-secrets are all there already, and it is a different product with a different failure mode.

## Moat assessment

**Weak-to-moderate, and eroding** `[Opinion]`.

Nothing here is technically hard to copy: 202 regexes and 31 file-path parsers are a weekend for a competent team `[Estimate]`. What is not a weekend is the redaction safety work and the verified-source list. The real asset is being 8x the size of the nearest direct competitor while the category is still forming `[Data]`, and that only converts into a moat if usage grows before medusa notices the niche `[Opinion]`.

## What would have to be true for this analysis to be wrong

1. If the two direct competitors are abandoned experiments rather than early entrants, the "window is closing" framing is alarmist. DidILeak going another 60 days without a commit would settle it.
2. If gitleaks' misses are an artefact of the default config, and a `--config` with vendor rules closes the gap, the headline benchmark weakens sharply. I did not test a tuned gitleaks config, and that is the most likely way this report is wrong.
3. If PyPI downloads undercount real usage because most users run from source or via `uvx`, the "nobody uses it" conclusion is wrong.
4. If medusa's "Claude Code compromise detection" already reads transcripts, it is a direct competitor with 959 stars rather than an adjacent one, and the market map is wrong. I read its description, not its source.

## Red flags

- Two direct competitors in five weeks, in a niche that had none `[Data]`.
- 111 PyPI downloads a month against 56 stars and 36 forks `[Data]`. Interest is not converting into use.
- medusa at 959 stars is one feature away from this niche `[Opinion]`.
- No competitor in the direct niche charges anything, so there is no evidence anyone will pay `[Data]`.

## Yellow flags

- 14 of 31 sources are experimental and unverified against a real install `[Data, from README]`. A competitor that verifies theirs can attack the headline number.
- gitleaks not detecting `sk-ant-oat01-` is an opportunity today and a one-PR fix for them `[Opinion]`.

## Data gaps

1. **No verified customer quotes.** The delegated pass returned unlinkable quotes; none were used. This is the biggest hole and blocks any positioning copy.
2. **No X/Twitter signal.** `grok` returned HTTP 402, "Grok Build usage balance exhausted" `[Data]`, and it is the only tool on this box that reaches X.
3. **No tuned-gitleaks comparison.** Only the default config was tested.
4. **No pricing data for the direct niche**, because nothing in it is paid.
5. **medusa not inspected beyond its description.**

## Method note

Delegated research was cross-checked rather than trusted, and it mattered. The agent that produced the incumbent table returned star counts matching the GitHub API exactly, and in the same output attributed Anthropic OAuth detection to gitleaks issue #1842 and PR #1846. Those are really "Help with exit-code" and "bad gitleaks config causes regex panic" `[Data]`, and gitleaks does not detect that token `[Data, tested]`. Real fetched numbers and fabricated citations arrived in one document. Every specific claim in this report was re-verified against an API or a local run.

## Sources

- GitHub REST API, all star/fork/date figures, fetched 2026-08-09
- MITRE CVE record for CVE-2026-21852, fetched 2026-08-09
- pypistats.org API for agentsweep downloads, fetched 2026-08-09
- gitleaks 8.30.1, downloaded from the project's GitHub release and run locally
- AgentSweep 0.1.9 at commit `9ce11ef`, run locally
