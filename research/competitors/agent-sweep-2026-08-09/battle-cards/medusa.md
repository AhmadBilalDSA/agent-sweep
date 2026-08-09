# Battle card: medusa (Pantheon-Security)

AgentSweep, 2026-08-09. Filed as adjacent. It is the one that could take the category.

## Who they are

959 stars, 154 forks, AGPL-3.0, Python. Created 2025-11-15, last push 2026-08-03 `[Data]`. Describes itself as an AI-first security scanner, and its current release notes lead with "Claude Code compromise detection: vet `.claude/` hooks, permissions & skills before you clone", plus `medusa secrets scan` and a claimed 40,000+ patterns `[Data, from their description]`.

## Why they matter more than the direct competitors

They are 17x AgentSweep's size, already parse `.claude/`, and already have a secrets command `[Data]`. The distance between what they ship and this niche is one feature `[Opinion]`. DidILeak at 7 stars is not the threat. This is.

## Where they genuinely win

- **Distribution.** 959 stars and 154 forks against 56 and 36.
- **Breadth.** Supply-chain and malicious-config detection, which AgentSweep does not attempt.
- **They are already in the directory.** Anyone who has run medusa on `.claude/` will assume it covers transcripts too.

## Where they lose, as far as is known

- **Their `.claude/` work is about config, hooks and permissions, not transcripts** `[Assumption, from the description]`. Different file, different problem.
- **No redaction claimed.**
- **AGPL-3.0** is a real barrier for commercial adoption where MIT is not `[Opinion]`.

## The honest answer to "why not just use medusa?"

Today, because it vets the configuration rather than reading the conversation, and the leaked key is in the conversation. That answer has a shelf life.

## Unresolved, and it should not stay that way

This card rests on their repo description. Nobody has read medusa's source or run it against a transcript. If it already scans transcripts, the market map in `report.md` is wrong and this is a direct competitor with 17x the reach.

**Next action: install medusa, point it at a seeded Claude Code history, count what it finds.** That single test is worth more than the rest of this research.
