---
title: Agent Limits and Risks
slug: agent-limits-and-risks
tags:
- agent
- agent-basics
- risk
aliases:
- agent risks
- agent limitations
- hallucination
created: '2026-08-11T13:22:41.348306+00:00'
updated: '2026-08-11T13:23:06.206466+00:00'
links:
- agent-loop
- what-is-an-agent
- agent-memory
- agent-basics
---

Agents fail in characteristic ways. Recognizing the patterns is part of the basics,
not a footnote.

**Hallucination.** A model can name a file, function, or API that does not exist,
with exactly the same confident tone. The remedy is not a sterner prompt but
verification: read first, don't trust recall.

**Irreversible actions.** Deleting data, messaging other people, changing production
systems — there is no undo. That is why risky actions ask for confirmation first,
while local, easily reverted actions can simply proceed.

**Loops without progress.** An agent can retry the same approach over and over. A
practical rule: after two failures, find the root cause and change approach instead
of patching again.

**Cost and latency.** Every turn of the [[Agent Loop]] is one paid model call. A task
that really needs a fixed flow is cheaper as an ordinary workflow — see
[[What Is an Agent]].

**Full context.** The symptom is subtle: the agent "forgets" the original instruction
because it was pushed out of the context. See [[Agent Memory]].

**Injection through data.** File contents or web pages can carry text disguised as
instructions. External data is treated as data, never as instructions.

## Open questions

Which is better: an agent that asks more often, or one that acts more independently?

## Sources

Internal teaching material for the [[Agent Basics]] campaign.
