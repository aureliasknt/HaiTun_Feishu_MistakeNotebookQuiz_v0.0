---
title: Agent Memory
slug: agent-memory
tags:
- agent
- agent-basics
- memory
aliases:
- agent memory
- context window
- agent context
created: '2026-08-11T13:22:41.344032+00:00'
updated: '2026-08-11T13:22:41.344032+00:00'
links:
- agent-loop
- tools-and-tool-calling
- agent-basics
---

**Agent memory** is how an agent remembers: what fits in the context right now, and
what is stored so it survives after the session ends.

Three layers with different natures:

| Layer | Contents | Lost when |
| --- | --- | --- |
| Context window | This turn's conversation + tool results | The session ends |
| Short-term memory | A summary of the running session | The session ends |
| Long-term memory | Facts in files or a database | Deliberately deleted |

**The context window is finite.** Every turn of the [[Agent Loop]] adds new
observations, so the context keeps growing until it is full. The common remedies:
summarize the old parts, or store them outside and read them back when needed.

Distinguish **remembering** from **looking up again**. Putting everything into the
context is expensive and actually drowns out what matters. The better pattern: store
the few facts that will genuinely be useful later, and re-fetch the rest through
[[Tools and Tool Calling|tools]] when required.

Worth storing permanently: decisions and their reasons, user preferences, project
constraints. Not worth it: anything that can be re-read from its source at any time.

## Open questions

How do you decide a single fact deserves long-term memory?

## Sources

Internal teaching material for the [[Agent Basics]] campaign.
