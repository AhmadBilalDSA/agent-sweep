# Battle card: DidILeak

AgentSweep, 2026-08-09.

## Who they are

`frangelbarrera/DidILeak`, 7 stars, 0 forks, MIT, Python. Created 2026-07-02, last commit 2026-07-06 `[Data]`. Self-described: "Local-first LLM secret scanner, scan ChatGPT, Claude, Cursor & Kimi K3 chat history for leaked API keys, PII & credentials. HTML dashboard + rotation guides."

This is the closest thing to a direct competitor that exists.

## Where they genuinely win

- **ChatGPT web history.** They cover it and AgentSweep does not `[Data, from their description]`. That is a real gap, and ChatGPT has far more users than every coding agent combined.
- **PII, not just credentials.** A broader definition of the problem.
- **HTML dashboard.** Better artefact than terminal output for anyone who wants to show a colleague.
- **They shipped the same idea within three weeks of AgentSweep.** That is validation, not a threat `[Opinion]`.

## Where they lose

- **4 named agents against 31** `[Data]`.
- **No redaction.** Their description says scan, dashboard and rotation guides. Finding is not fixing.
- **34 days without a commit, 0 forks, 7 stars** `[Data]`. No contributor base.

## The honest answer to "why not just use DidILeak?"

If your exposure is ChatGPT web chats, use it, because AgentSweep does not read those at all. If your exposure is a coding agent on your machine, AgentSweep covers 31 of them and can remove what it finds.

## What to watch

Whether it gets another commit. Sixty quiet days makes it an abandoned experiment and the "two competitors in five weeks" framing softens. Continued development makes it the one to track.

## What to steal

ChatGPT and Kimi coverage is a legitimate gap in AgentSweep's source list, and the ChatGPT one is probably the largest single population of leaked keys anywhere `[Opinion]`.
