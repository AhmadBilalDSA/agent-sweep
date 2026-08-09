# AgentSweep feature matrix

Generated 2026-08-09. Ratings: **strong** / adequate / weak / missing. Every rating comes from the tool's own docs, description, or a local run, and the basis is stated.

| Capability | AgentSweep | DidILeak | transcript-sentinel | medusa | gitleaks | TruffleHog |
|---|---|---|---|---|---|---|
| Reads AI agent history files | **strong** (31 agents) | adequate (4 agents) | adequate (unspecified) | weak (`.claude/` config, not transcripts) | missing | missing |
| Scans a non-git directory | **strong** | **strong** | **strong** | **strong** | **strong** (`gitleaks dir`) | **strong** (`trufflehog filesystem`) |
| Vendor-specific rule coverage | **strong** (5/5 measured) | unknown | unknown | **strong** (40,000+ patterns claimed) | weak (2/5 measured) | unknown |
| Detects `sk-ant-oat01-` | missing (issue #170 open) | unknown | unknown | unknown | **missing** (tested) | unknown |
| **Redacts in place** | **strong** | missing | missing | missing | missing | missing |
| Corruption-prevention on write | **strong** | n/a | n/a | n/a | n/a | n/a |
| Live credential verification | missing | missing | missing | unknown | missing | **strong** |
| Rotation guidance | **strong** (203 entries) | adequate ("rotation guides") | unknown | unknown | missing | missing |
| Fully offline | **strong** | **strong** | **strong** | unknown | **strong** | weak (verification calls out) |
| Prevention before send | missing | missing | missing | missing | missing | missing |
| Maturity (stars) | 56 | 7 | 3 | 959 | 28,550 | 27,348 |

## Rows where nobody is strong

These are the actual openings.

1. **Prevention before send.** Every tool here cleans up afterwards. Offsend, aigate and phantom-secrets attack this and none has traction (11, 6, 12 stars). The problem is real and unsolved, and it is a different product.
2. **`sk-ant-oat01-` coverage.** Nobody detects the token Claude Code writes to `~/.claude/.credentials.json` after login. AgentSweep issue #170 is open for it. Whoever ships it first can say so truthfully.
3. **Live verification inside agent history.** TruffleHog verifies credentials against the provider; nothing in the agent-history niche does. Verified findings cut false positives, which is the top complaint about every scanner.

## Rows to stop claiming

**"Reads AI agent history"** is no longer a differentiator on its own. Three tools do it now. The defensible version is the count (31) plus redaction, not the capability.

## Caveats

- "unknown" is honest. DidILeak and transcript-sentinel were rated from README and repo description, not from running them. Running both is the obvious next step.
- medusa's rating is from its description only.
- gitleaks' vendor coverage row reflects the **default config**. A tuned config was not tested and could change that row.
