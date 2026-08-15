---
title: Tools and Tool Calling
slug: tools-and-tool-calling
tags:
- agent
- agent-basics
- tools
aliases:
- tool calling
- function calling
- agent tools
created: '2026-08-11T13:22:41.339516+00:00'
updated: '2026-08-11T13:22:41.339516+00:00'
links:
- agent-loop
- agent-limits-and-risks
- agent-basics
---

A **tool** is a function an agent is allowed to call in order to touch the world
outside the conversation: read a file, search the web, send a message, run a
command. **Tool calling** is the mechanism — the model emits a tool name plus
structured arguments, and the runtime is what actually executes it.

The flow, one step inside the [[Agent Loop]]:

1. The runtime gives the model a list of tools: name, description, argument schema.
2. The model replies "call `read_file` with `path=...`" — not ordinary prose.
3. The runtime runs that function and returns the result to the model.

The model **does not** execute anything itself. It only proposes; the runtime holds
control. This is the crucial point for safety: limits are enforced in the runtime,
not entrusted to the model's compliance.

The quality of tool descriptions determines the quality of the agent. A vague
description leads the model to pick the wrong tool or the wrong arguments. So one
tool should do one clear job, with a name that explains itself.

Tools are also a real source of risk — actions like deleting data cannot be undone.
See [[Agent Limits and Risks]].

## Open questions

How many tools before the model starts choosing badly?

## Sources

Internal teaching material for the [[Agent Basics]] campaign.
