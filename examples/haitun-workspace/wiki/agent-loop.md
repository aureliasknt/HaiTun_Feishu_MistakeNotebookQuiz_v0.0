---
title: Agent Loop
slug: agent-loop
tags:
- agent
- agent-basics
- architecture
aliases:
- agent loop
- observe think act
- react loop
created: '2026-08-11T13:21:44.746148+00:00'
updated: '2026-08-11T13:21:44.746148+00:00'
links:
- what-is-an-agent
- tools-and-tool-calling
- agent-memory
- agent-basics
---

The **agent loop** is the cycle repeated until the goal is met:
**observe → think → act → observe the result**. This is the machinery that makes
an [[What Is an Agent|agent]] different from a single ordinary model call.

One turn of the loop:

1. **Observe** — gather the current state: the user's request, results of earlier
   tools, the contents of a file just read.
2. **Think** — the model decides the next step: which tool, which arguments, or
   stop because the work is done.
3. **Act** — run one [[Tools and Tool Calling|tool call]].
4. **Feedback** — the result of the action comes back in as a new observation.

The important part: **the result of an action re-enters the context**, so the loop
can correct itself. An agent that misread a file can tell from the error and change
approach. Without that feedback, an agent guesses once and stops.

The loop is also the source of two practical problems: the context grows every turn
(see [[Agent Memory]]), and a loop can spin without progress — which is why there
is always a cap on the number of steps.

## Open questions

How do you tell that an agent is finished versus stuck?

## Sources

Internal teaching material for the [[Agent Basics]] campaign.
