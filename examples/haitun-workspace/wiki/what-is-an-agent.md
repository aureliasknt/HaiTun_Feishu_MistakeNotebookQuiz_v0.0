---
title: What Is an Agent
slug: what-is-an-agent
tags:
- agent
- agent-basics
- concept
aliases:
- agent definition
- agent vs chatbot
created: '2026-08-11T13:21:44.742382+00:00'
updated: '2026-08-11T13:21:44.742382+00:00'
links:
- agent-limits-and-risks
- agent-loop
- agent-basics
---

An **agent** is a system that is given a goal and then chooses its own sequence of
actions to reach it — with a language model as the decision maker.

Three levels that often get confused:

| Form | Who decides the steps | Example |
| --- | --- | --- |
| Chatbot | No steps; it just replies | Ordinary question and answer |
| Workflow | A human, when writing the flow | A fixed if-else pipeline |
| Agent | The model, while running | Find a file, read it, fix it, test it |

The defining trait of an agent is **deciding at runtime**. A branching workflow is
still not an agent if a human wrote every branch in advance. An agent picks its own
branch based on what it has just seen.

The consequence: an agent is more flexible but less predictable. That is why
[[Agent Limits and Risks]] is required reading, not an appendix. The machinery
inside an agent is described in [[Agent Loop]].

## Open questions

When is a task better served by a plain workflow than by an agent?

## Sources

Internal teaching material for the [[Agent Basics]] campaign.
