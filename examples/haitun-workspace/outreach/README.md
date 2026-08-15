# Outreach — agent-literacy campaign

Goal: raise a group of target users' baseline understanding of agents, with content
drawn from the wiki pages under `wiki/` (tag `agent-basics`).

Two scenarios share one state file, and they run in sequence:

| | Scenario 3 — reactive (**active**) | Scenario 1 — daily outreach (idle) |
| --- | --- | --- |
| Trigger | the user asks about agents/HaiTun | a random time each day |
| Entry point | `channel_events/feishu/agent_literacy_question/map.py` | `channel_events/feishu/outreach_daily/produce.py` |
| Trigger file | `triggers/outreach-confirm-auto/` (`fire=tool`) | `triggers/outreach-daily-send/` (`fire=prompt`) |
| LLM on the user's path | none — static bank + card | yes, the agent writes each message |
| Advances by | the confirmation card's answer | the user's reply |

Scenario 3 comes first because it produces the baseline (profile, heatmap,
counters) that Scenario 1 then teaches against. A user reaching `stage: done`
is ready for handoff.

## Scenario 3 — reactive Q&A + confirmation card

Every time a target user asks about agents, the bot answers and then asks whether
that landed. The answer to that card is what decides the next teaching step.

Three paths, and only the first one is the common case:

```
A. fast path (default, 0 LLM on the user's path)
   DM text → map.py (keyword, <10 ms) → event → TRIGGER fire=tool
   → outreach_confirm_send: bank answer + 理解确认卡 + write last_qa.   < 1 s total.

B. fallback (LLM, rare)
   keyword hit but no bank entry (`bank_miss`), or a learning question with no
   keyword → the background session turn answers it and sends the card itself.

C. callback (button click)
   Channel updates the card instantly (0 LLM) → small turn calls
   outreach_confirm_handle → counters written, pre-composed follow-up sent.
   understood     → an affirmation + "anything else?", no card, no new material
   partial        → re_explain (different angle, real HaiTun example) + a NEW card
   not_understood → restart (simplest wording, no new material) + a NEW card
```

The asymmetry in path C is deliberate:

- A re-explanation is a **fresh claim**, so it carries its own card. Without one, a
  user who is *still* lost has no way to say so and the loop dead-ends.
- `understood` asserts nothing new, so the turn ends with an affirmation and an
  invitation. It does **not** push the next node: this scenario is reactive, so what
  comes next is the user's choice.
- Repeated confusion keeps **re-explaining**. An earlier version swapped in
  `probe_question` after two misses, which quizzed exactly the person who had just
  said twice that they were lost.

### Parts

| Part | Location | Job |
| --- | --- | --- |
| Detector | `channel_events/feishu/agent_literacy_question/map.py` | Keyword match on `im.message.receive_v1`, DM + cohort only |
| Trigger | `triggers/outreach-confirm-auto/TRIGGER.md` | `fire=tool` → no LLM |
| Answer tool | `tools/outreach_confirm_send.py` | Bank answer + card + `last_qa` |
| Callback tool | `tools/outreach_confirm_handle.py` | Record the answer, send the follow-up |
| Shared helpers | `tools/_outreach_confirm.py` | State/bank IO, card builder, EMA, atomic write |
| Answer bank | `outreach/qna_bank.yaml` | The static teaching content |
| Skill | `skills/outreach-confirmation-card/SKILL.md` | The A/B/C protocol for the agent |

### Honest limits

- **Every incoming message still runs one background session turn.** The mapper
  fans out *alongside* the built-in handler (`_AgentEventFanout` runs the built-in
  first), it does not replace it. What this design removes is every LLM call on the
  path the user waits on — not the LLM cost per message.
- **The background turn must stay quiet.** The skill's rule: if this user's
  `last_qa.sent_at` is within `scenario3.dedup_window_seconds` (default 60), reply
  `NO_REPLY` — the token the system prompt defines for "nothing to say", which the
  Feishu channel drops when it is the turn's entire output (`_stream_reply`). The
  ordering is safe — the tool writes `sent_at` in milliseconds, seconds before the
  LLM turn reads it — but it is a time-based guard, not a lock. If the model mixes
  the token into other text the filter deliberately lets it through, so a leaked
  `NO_REPLY` in the chat means the turn said more than the token alone.
- **Bank answers are static.** Quality equals the bank's quality. Fix content by
  editing `qna_bank.yaml`; a keyword with no entry falls to path B.
- **Substring keywords cut both ways.** False positives are harmless (a card is
  cheap). False negatives mean an answer without a card — widen the keywords, or
  let path B catch it.
- **The click still costs one small LLM turn**, because a card action always
  arrives as a turn. The card itself has already updated by then.
- **`OUTREACH_STATE_PATH` is optional.** The mapper and both tools resolve the
  state file the same way: `OUTREACH_STATE_PATH` →
  `WORKSPACE_DIR/outreach/state.yaml` → **this package's own
  `outreach/state.yaml`**. `scripts/dev-feishu.ps1` exports neither env var, so the
  package-relative fallback is what makes the ordinary bring-up work unconfigured.
  Set the env var only to point at a state file outside the package; a value
  pointing at a missing file is ignored rather than allowed to shadow the real one.
  If no state file is found at all, keywords fall back to the built-in list **and
  the cohort filter disappears** — every DM asker then gets the fast path.

## Setup

1. `cp outreach/state.example.yaml outreach/state.yaml`, then fill in each
   target's real `open_id`. Use the helper rather than editing by hand:

   ```bash
   export PSI_FEISHU_APP_ID=cli_...        # never commit these
   export PSI_FEISHU_APP_SECRET=...
   uv run python examples/haitun-workspace/bin/discover_outreach_targets.py --list
   uv run python examples/haitun-workspace/bin/discover_outreach_targets.py --set ou_aaa ou_bbb
   uv run python examples/haitun-workspace/bin/discover_outreach_targets.py --check
   ```

   `--set` preserves per-user progress for ids already in the campaign, so a
   re-run does not resend introduction message #1 to everyone.

2. Start **both** processes with the credentials in the environment:

   ```bash
   powershell -File scripts/dev-feishu.ps1
   ```

**The Feishu channel process is what runs the mappers and synthetic producers**,
not the gateway (see `src/psi_agent/channel/feishu/_agent_events.py`, which starts
them in the channel's TaskGroup). A gateway launched without the Feishu flags will
happily serve the SPA while nothing is ever detected or sent — that is the most
common reason the campaign appears dead. Confirm the channel is up:

```bash
# expect a process whose command line contains: psi-agent channel feishu
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*channel*feishu*' } | Select-Object ProcessId"
```

Verify the detector before trusting it — an empty `map.py` result and a
"deduplicated" delivery look identical in the log:

```text
channel_event_check(action="shape", platform_event="im.message.receive_v1")
channel_event_check(action="probe", event="feishu.agent_literacy.question")
```

The probe sample must carry `message_type: text`, `chat_type: p2p`, a
`sender.sender_id.open_id` **that is in `users`**, and a keyword in the text —
all four are required for the accept branch.

## Prerequisites for an actual send

| Requirement | Check |
| --- | --- |
| Real `open_id`s in `state.yaml` | `discover_outreach_targets.py --check` |
| `PSI_FEISHU_APP_ID` / `PSI_FEISHU_APP_SECRET` set | Both the gateway and the channel read them |
| Feishu channel process running | Command above |

The state file needs no env var (see the resolution order above). To confirm which
file the running channel would actually read:

```bash
# PYTHONIOENCODING is needed on Windows: a repo path containing Chinese cannot be
# printed to a cp1252 console.
PYTHONIOENCODING=utf-8 uv run python -c "import sys; sys.path.insert(0, 'examples/haitun-workspace/tools'); import _outreach_confirm as oc; print(oc.state_path())"
```

The bot also needs the `im:message:send_as_bot` scope, and it can only message
users who have the app installed and are inside its visibility range.

## Content pages

The curriculum lives in the flat wiki (`wiki/<slug>.md`, tag `agent-basics`),
because the `wiki_*` tools do not support subfolders — `wiki_dir()` is always
`<workspace>/wiki`. Hub page: `Agent Basics`. Read pages with `wiki_read`, never
by hand-crafting file paths.

Node order: `What Is an Agent` → `Agent Loop` → `Tools and Tool Calling` →
`Agent Memory` → `Agent Limits and Risks`.

`qna_bank.yaml` is composed **once, offline** from those pages (an LLM may help
write it, then it is frozen). Static answers are consistent and instant; revising
content means editing the file.

## The `scenario3` schema

| Field | Meaning |
| --- | --- |
| `enabled` | `false` → the mapper emits nothing; the campaign goes dormant |
| `keywords` | Case-insensitive substring match against the message text |
| `qa_bank_path` | Bank location, relative to the workspace |
| `followup.mode` | `immediate` (tool sends the follow-up) or `next_question` (defer to the user's next question) |
| `followup.closing` | The **whole** message sent on `understood`. Omit for the default (「很好！还有别的想问的吗？」); set `''` to send nothing |
| `followup.closing_done` | Same, for the answer that graduates the user |
| `card.ask_after_every_answer` | `false` → no card after a re-explanation either, and only path B sends cards |
| `card.probe_question_every` | Every Nth card carries a real probe question instead of self-assessment only |
| `dedup_window_seconds` | How long `last_qa.sent_at` suppresses the background LLM turn (default 60) |

Per-user fields written by the tools: `last_qa` (`qa_id`, `question`, `keyword`,
`topic`, `card_message_id`, `sent_at`, then `answered_at` / `self_assessment`; a
card that follows a re-explanation also carries `recheck: true`),
`answers[]` (capped at the most recent 200), `card_sent_count`,
`confident_streak`, `confident_count`, `not_understood_count`,
`familiarity_est` (local EMA, α=0.35 — the authoritative signal stays the user
profile and supervisor), `stage`, `handed_off_to_scenario1/2`.

`stage`: `qna_reactive` → `done` (written automatically once
`confident_count ≥ thresholds.confident_answers_needed` **and**
`familiarity_est ≥ thresholds.familiarity_done`) → handoff.

## The bank schema

Each entry under `qa_bank:` carries `topic`, `source_page`, `answer` (sent as the
reply), `summary` (one line, shown on the card), and the follow-ups chosen by the
card answer:

| Card answer | `value.action` | What is sent |
| --- | --- | --- |
| ✅ 懂了 | `understood` | `scenario3.followup.closing` — not a bank field |
| 🤔 不太懂 | `partial` | `re_explain` |
| ❌ 没看懂 | `not_understood` | `restart` |

The mapping for the two confused answers is unconditional — they always re-explain.
`probe_question` is used only *on the card* (every `probe_question_every`-th one), to
verify a claimed "understood"; it is never used as a follow-up.

`next_message` is therefore unused by Scenario 3. It is kept in the bank for the
Scenario 1 handoff, where the agent does drive the curriculum forward.

`aliases:` maps any other keyword to a canonical entry; a keyword resolving to
neither is a bank miss.

## Who writes what

- `outreach_confirm_send` / `outreach_confirm_handle` — only the asking user's row.
- The Scenario 1 producer — only the `daily` block.
- The agent (Scenario 1 prompt) — per-user send fields + `daily` schedule.

Both tools re-read the file immediately before writing and write atomically
(temp + replace), because the producer writes the same file. Comments are lost on
every rewrite (`yaml.safe_dump`) — documentation belongs in this file.

## Scenario 1 — daily outreach (idle until handoff)

Still installed and unchanged; it simply does not fire while `daily.next_send_at`
is empty. Reactivate it for users at `stage: done`.

| Field | Meaning |
| --- | --- |
| `send_window.start` / `.end` | Hours sending is allowed (UTC+8), for the daily random cadence |
| `poll_every_minutes` | Producer poll interval. Default 5. For a tight test cadence use 1 |
| `next_send_at` | ISO-8601. The producer emits when `now >= next_send_at` |
| `last_daily_at` | Last send (written by the agent) |
| `sending` | At-most-once guard. Stale > 26 hours → the producer resets it |
| `interval_minutes` | **Test mode**: fixed cadence instead of daily random |
| `interval_until` | End of test mode. Past it, both test fields are dropped and the daily random cadence resumes |

Who owns the schedule is the one part that is easy to get wrong:

- **Normal cadence** — the producer only sets `sending=true`; the agent writes
  `next_send_at` (tomorrow, random time) and releases the guard.
- **Test mode (`interval_minutes`)** — the producer advances `next_send_at` to the
  next grid slot and releases the guard itself, so the ladder keeps running even
  if the agent fails mid-turn. The agent must not touch the schedule fields (see
  TRIGGER step 3). Missed slots are skipped — no burst of catch-up sends.

Example test mode, every 10 minutes until 22:00:

```yaml
daily:
  poll_every_minutes: 1
  next_send_at: '2026-08-11T19:30:00+08:00'
  interval_minutes: 10
  interval_until: '2026-08-11T22:00:00+08:00'
  sending: false
```

## KPI

Two different roots hold the evidence, and mixing them up is the easy mistake:

- **`outreach/state.yaml`** — one shared file in the agent package. Written by the
  two tools, which resolve it package-relative, so it is the same file for every
  target.
- **`<package>/<open_id>/…`** — one workspace **per DM user**, created by the
  Gateway (`--feishu-workspace-root`, see `_feishu_manager._workspace_for`).
  Everything the session hooks write lands here, not in the package root.

| Source | Metric |
| --- | --- |
| `outreach/state.yaml` | `card_sent_count`, `self_assessment` distribution, `confident_streak`, `confident_count` / `not_understood_count`, `familiarity_est`, `stage` transitions |
| Tool results (channel log) | `answered` vs `bank_miss` ratio = `bank_hit_rate` (target ≥ 90% once the bank matures), duplicate answers (must be 0) |
| `<open_id>/wiki/profiles/session-<sha256>.md` | `turns`, per-topic `familiarity` / `depth` / `goal` — the authoritative learning signal |
| `<open_id>/wiki/supervisor/users/<hash>/metrics.jsonl` | Turn count, advice source (live/cache/unavailable), latency |
| `<open_id>/wiki/supervisor/users/<hash>/domains/<domain>.yaml` | `question_count`, `visited_nodes`, `repeated_surface_questions`, `cognitive_history` |

The profile id is `session-<sha256>` (a DM session's identity), not `user-<hash>` —
`_user_profile.py` derives it from the session id when no explicit `profile_id` or
`user_id` is passed.

Graduation is `confident_count ≥ 3` **and** `familiarity_est ≥ 0.7` — with the
caveat that self-assessment must be cross-checked against actual `probe_question`
answers, not taken as proof on its own.

## Known gap: path B cannot read the wiki yet

`wiki_read` resolves against the **turn's** workspace (`get_workspace()` →
`<package>/<open_id>/`), and that per-user directory contains only
`wiki/profiles/` — none of the six `agent-basics` pages. So a bank miss cannot be
answered from the curriculum as the skill instructs; the agent would have to answer
from general knowledge, unsourced.

Path A is unaffected: the tools read `qna_bank.yaml` package-relative and never
call `wiki_*`. Until this is closed, keep the bank covering every configured
keyword (verified: all 10 resolve) so path B stays unused. Options, cheapest first:

1. Copy the six pages into each target's `<open_id>/wiki/` at setup.
2. Have the bank carry the teaching text (already true) and drop the wiki
   instruction from path B.
3. Give the wiki tools an explicit agent-package root for shared curriculum pages.
