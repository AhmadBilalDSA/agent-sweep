# AgentSweep pricing landscape

Generated 2026-08-09.

## The headline

**Nothing in the direct niche charges anything.** AgentSweep, DidILeak and transcript-sentinel are all free OSS (MIT, MIT, Apache-2.0) `[Data]`. There is no pricing to compare, and no evidence anyone will pay for this specific job `[Data]`.

That is the finding. A competitor charging money would be validation; their absence is not.

## Adjacent category pricing

| Tool | Free tier | Paid | Value metric |
|---|---|---|---|
| gitleaks | Everything, MIT | none for the CLI | n/a |
| TruffleHog | Full OSS engine, AGPL-3.0 | Enterprise, quote-only | seat / org |
| detect-secrets | Everything, Apache-2.0 | none | n/a |
| ggshield / GitGuardian | up to 25 devs | Business, quote-based | per developer |
| Semgrep Secrets | CLI free, cloud to 10 devs | ~$15/dev/mo | per developer |
| Infisical | CLI free, cloud to 5 users | Pro ~$6-8/user/mo, Team ~$18/user/mo | per user |

Tier figures are from a delegated web pass `[Data, unverified against vendor pages]`. The star counts in that same pass matched the GitHub API exactly, but the same document fabricated two issue citations, so treat these numbers as needing a check before anyone quotes them externally `[Assumption]`.

## What the pattern says

Every paid product in the adjacent category charges **per developer for team features**, not for scanning `[Data]`. Scanning is the free tier everywhere, without exception. The money is in centralised triage, dashboards, policy and audit trails.

The implication for AgentSweep is uncomfortable and worth stating plainly: **a better local scanner has no pricing power** `[Opinion]`. The category has already decided that local scanning is free. The only monetisable shapes visible from this data are:

1. **Fleet posture.** "Which of our 200 engineers has secrets sitting in their agent history right now." Per-seat, sold to a security team, not to the developer. Requires reporting off-device, which contradicts the fully-offline promise that is currently the product's headline `[Opinion]`.
2. **Managed rotation.** Detection is free; doing the rotation is the paid part. No competitor does this `[Data]`.
3. **Nothing.** Keep it free and treat it as reputation and distribution.

## Whitespace

There is genuine whitespace at **fleet visibility for AI agent history specifically**, because no vendor addresses it `[Data]`. Whether that is a business or an empty room is unresolved, and 111 monthly downloads is not enough signal to tell `[Opinion]`.

## Data gaps

- No vendor pricing page was fetched directly this run.
- No evidence at all on willingness to pay. Nobody has tried.

## Red flags

- Zero paid competitors in the direct niche.
- The obvious monetisation, fleet reporting, breaks the offline guarantee the product currently leads with.

## Sources

- GitHub REST API for licences and stars, 2026-08-09
- Delegated web pass for tier pricing, unverified, 2026-08-09
