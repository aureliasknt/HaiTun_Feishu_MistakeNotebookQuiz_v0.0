---
name: outreach-confirm-auto
description: 'Scenario 3: answer an agent-literacy keyword question from the static
  bank and send the understanding-confirmation card (fire=tool, no LLM)'
event: feishu.agent_literacy.question
source: feishu
filter: {}
visibility: silent
run_once: false
created_by: agent
fire: tool
tool: outreach_confirm_send
tool_args: {}
created_at: '2026-08-12T05:20:00Z'
---

Handled entirely by `outreach_confirm_send` — there is no prompt here on purpose.
`fire: tool` calls the tool directly, so the path the user waits on (question →
answer → card) never runs a model.

`tool_args` stays empty: the tool declares `event_payload_json`, so the runtime
injects the envelope payload (`open_id`, `text`, `keyword`, `message_id`,
`chat_id`) into it. Hard-coding args here would pin the trigger to one user.

A keyword with no entry in `outreach/qna_bank.yaml` returns `bank_miss` and sends
nothing; the background LLM turn answers that one and sends the card itself
(path B in the `outreach-confirmation-card` skill).

Full reference: `outreach/README.md`.
