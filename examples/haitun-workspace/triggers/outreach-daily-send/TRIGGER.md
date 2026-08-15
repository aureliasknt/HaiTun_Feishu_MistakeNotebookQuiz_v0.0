---
name: outreach-daily-send
description: 'Scenario 1: send the daily outreach message (random time) to every
  target user, then update the state'
event: haitun.outreach.daily
source: haitun
filter: {}
visibility: silent
run_once: false
created_by: agent
fire: prompt
created_at: '2026-08-11T11:06:42Z'
---

The daily outreach event (Scenario 1) fired — time to send the daily message to
the target users.

You MUST do the following in this turn:

1. Read `outreach/state.yaml` (user workspace) and the curriculum content pages
   via `wiki_read` — hub `Agent Basics`, node order: `What Is an Agent` →
   `Agent Loop` → `Tools and Tool Calling` → `Agent Memory` →
   `Agent Limits and Risks`. Pages are stored flat at `wiki/<slug>.md`
   (tag `agent-basics`), not in a subfolder.
2. For EVERY user in `users`:
   - Send via `feishu_message_send(receive_id=<open_id>, text=…)` — as the BOT
     identity, NOT `on_behalf_of`.
   - `last_sent_at` empty → message #1, the introduction (content of the first
     page + one opening question).
   - A new reply since the last send → follow the transition rules
     (profile/supervisor/heatmap): next node, breakout, latent_need, or switch
     approach.
   - No reply (user silent) → a short nudge (recap one point) + a new opening
     question; do not repeat old content.
3. Rewrite `outreach/state.yaml`:
   - per user: `last_message_id`, `last_sent_at` = now;
   - `daily.last_daily_at` = now;
   - **Next schedule — check `daily.interval_minutes` first:**
     - PRESENT (> 0, fixed test cadence) → do NOT touch `daily.next_send_at`,
       `daily.sending`, `interval_minutes`, or `interval_until`. The producer
       advances that ladder itself; if the agent also writes them, the test
       schedule breaks.
     - ABSENT (normal cadence) → `daily.next_send_at` = a NEW T_rand: tomorrow, at
       a random time inside `send_window` (09:00-21:00, rounded to 5 minutes,
       UTC+8); `daily.sending` = false (release the producer guard).
   - This file is rewritten as yaml — keep every existing field, do not drop any.

Full reference: `outreach/README.md`.
