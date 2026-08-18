# Outreach — agent-literacy campaign

Goal: raise a group of target users' baseline understanding of agents, with content
drawn from the wiki pages under `wiki/` (tag `agent-basics`).

Two scenarios share one state file, and they run in sequence:

| | Scenario 3 — reactive (**active**) | Scenario 1 — daily outreach (idle) |
| --- | --- | --- |
| Trigger | the user asks about agents/HaiTun | a random time each day |
| Entry point | the ordinary DM turn (no mapper, no trigger) | `channel_events/feishu/outreach_daily/produce.py` |
| Trigger file | — | `triggers/outreach-daily-send/` (`fire=prompt`) |
| Who writes the answer | the agent, grounded in the bank | the agent, from the wiki |
| Advances by | the confirmation card's answer | the user's reply |

Scenario 3 comes first because it produces the baseline (profile, heatmap,
counters) that Scenario 1 then teaches against. A user reaching `stage: done`
is ready for handoff.

## Scenario 3 — reactive Q&A + confirmation card

Every time a target user asks about agents, the bot answers and then asks whether
that landed. The answer to that card is what decides the next teaching step.

One answering path, plus the callback:

```
1. answer (the ordinary DM turn — the agent writes it)
   DM text → prompt builder matches a keyword and injects, from files only:
       ## 讲解对象        the reader's profession + how to explain to them
       <literacy_grounding>  the bank entry for that keyword
   → the agent answers in its own words, then calls
     outreach_confirm_card → 理解确认卡 + last_qa repointed at the new qa_id.
   → if it did not, system_after_turn sends that card itself (see below).

2. callback (button click) — the reply is written too
   Channel updates the card instantly (0 LLM) → the turn is grounded the same way
   (a click carries no keyword, so the subject comes from last_qa.keyword) and
   gets <card_click_response>, the job for the button that was pressed
   → outreach_confirm_handle records the answer and returns next_step; it sends
     nothing
   → the model writes the reply:
   understood     → affirmation + real next-topic offers + "anything else?", NO card
   partial        → same point, a DIFFERENT analogy, no new material + a NEW card
   not_understood → same point from the simplest form, no new material + a NEW card
```

There used to be a third path in front of this one: a channel mapper matched the
keyword in under 10 ms, a `fire=tool` trigger called `outreach_confirm_send`, and
the user had the bank's answer plus a card in well under a second, with **no model
on the path they waited on**. It was removed deliberately, and the trade is worth
stating plainly:

- **What was lost.** Sub-second, perfectly consistent answers. The model now writes
  every answer, so time-to-first-token is whatever the turn costs — dominated today
  by the blocking supervisor hook (6–27 s in `metrics.jsonl`), not by this change.
- **What was gained.** A verbatim bank answer cannot be re-framed for the person
  reading it. Scenario 3 teaches one specific cohort, and an answer that is
  technically correct but written as engineering prose does not land with a legal
  officer — see "Who this is explained to" below.
- **What did not change.** The card, byte for byte: same single prompt line, same
  three buttons, same `qa_id` gate, same `last_qa`. `outreach_confirm_handle`
  cannot tell which path sent the card it is validating.

### The card is still guaranteed, just later

Losing that trigger did cost something real, and it is worth being precise about
what: the card stopped being **mechanically** enforced and started depending on the
model following the skill. `fire=tool` triggers fire on *message arrival* — at that
moment there is no answer yet — so no trigger arrangement can send a card "after the
model has answered". A mechanical card and a model-written answer are mutually
exclusive by construction.

`system_after_turn` is where the guarantee moved, because it runs after the final
answer is committed (`session/agent.py` → `run_after_turn`) and receives that
answer. If a turn was grounded but sent no card, `_ensure_confirmation_card` sends
it — in the right order, since the card asks about text the user has already read.

Whether the turn already sent one is decided **from state, not from the clock**:
`_literacy_context` records the `last_qa.qa_id` it saw while building the prompt, and
a different id afterwards means `outreach_confirm_card` ran. The old
`dedup_window_seconds` guard tried to answer a similar question with a seconds
window, and that was a guess about timing rather than a fact about state.

Two consequences worth knowing:

- **The skill still asks the model to send the card**, because a card sent during the
  turn reaches the user sooner. The hook is the floor, not the plan.
- **Every hook-sent card is logged at WARNING.** Each one is a turn that ignored the
  skill, and that count is the only visibility into how often it happens — there was
  previously no way to detect "answered but forgot the card" at all.

One case is deliberately *not* covered: a turn that ends in an error or is aborted
never reaches the hook. There is no answer in that case either, so no card is owed.

Two things went away with the fast path, because both existed only to keep it and
the background turn from answering the same question twice: `dedup_window_seconds`,
and the skill's rule that the background turn must reply `NO_REPLY` inside that
window. That rule is now actively wrong — the DM turn **is** the answering turn, so
a silent one means nobody answers. (The `NO_REPLY` mechanism itself is a framework
feature and is untouched; see `channel/feishu/client.py`.)

The card itself is **one line and three buttons**:「这次讲清楚了吗？」plus ✅ 懂了 /
🤔 不太懂 / ❌ 没看懂. It never repeats the question, the summary or the probe: it is
always sent immediately after the message it is asking about, so echoing that text
only made the user read it twice and pushed the buttons down the screen. Both cards
(the first one and the one after a re-explanation) are therefore identical — a click
is tied to its exchange by `qa_id`, never by what the card says.

The asymmetry in the callback is deliberate:

- A re-explanation is a **fresh claim**, so it carries its own card. Without one, a
  user who is *still* lost has no way to say so and the loop dead-ends.
- `understood` asserts nothing new, so the turn ends with an affirmation, a short
  list of real next topics, and an open question. It does **not** start teaching one:
  this scenario is reactive, so what comes next is the user's choice. The offers come
  from the bank (`suggested_topics`), so every one of them is a topic the campaign can
  actually teach — and never the one just covered.
- Repeated confusion keeps **re-explaining**. An earlier version swapped in
  `probe_question` after two misses, which quizzed exactly the person who had just
  said twice that they were lost. No probe is due on a click at all: it is the same
  point being taught again, not a new exchange.

**Why the follow-up is written rather than picked.** The callback used to send
pre-composed bank text — `restart` for 没看懂, `re_explain` for 不太懂, a fixed
closing for 懂了. Three fixed paragraphs cannot re-explain: "不太懂" means the first
wording did not land, and the second attempt has to differ from *what was actually
said* — which a static string cannot know. Worse, the bank's re-explanation was
written for a general reader, so it dropped the audience framing mid-conversation.
The tool therefore keeps only what a tool can do (the `qa_id` gate, counters, EMA,
graduation) and returns `next_step` / `send_new_card`; the words are the model's.

`followup.mode` is consequently inert: there is no pre-composed text left for
`immediate` and `next_question` to select between. `followup.closing` /
`closing_done` still supply the wording for the web app's `POST /outreach/answer`
response, which has no model behind it.

### Parts

| Part | Location | Job |
| --- | --- | --- |
| Context injector | `systems/system.py` → `_literacy_context` | Keyword match + audience rules + grounding into the prompt (files only, no LLM); records the pre-turn `qa_id` |
| Card guarantee | `systems/system.py` → `_ensure_confirmation_card` | Sends the card after the answer if the turn did not (see below) |
| Context builder | `tools/_outreach_confirm.py` → `literacy_context` | `match_keyword` + `audience_block` + `grounding_block` |
| Card tool | `tools/outreach_confirm_card.py` | Send the card, repoint `last_qa` |
| Callback tool | `tools/outreach_confirm_handle.py` | Record the answer, return `next_step` — sends nothing |
| Shared helpers | `tools/_outreach_confirm.py` | State/bank IO, card builder, EMA, atomic write |
| Answer bank | `outreach/qna_bank.yaml` | The teaching content the answer is grounded in |
| Skill | `skills/outreach-confirmation-card/SKILL.md` | The answer + card protocol for the agent |
| Web app | `gateway/_outreach_api.py` | `GET /outreach/card`, `POST /outreach/answer` |

### Honest limits

- **Time-to-first-token is not ours to fix here.** The dominant wait is the blocking
  `system_before_turn` supervisor hook — 6–27 s in the recorded `metrics.jsonl`,
  spent *before* the model emits anything. Removing a `wiki_read` round-trip (the
  grounding is already in the prompt) and not making the model write ~500 tokens of
  card JSON both help, but neither touches that hook. It is deliberately unchanged:
  the adaptive teaching signal depends on it.
- **The grounding is only as good as the bank.** Fix teaching content by editing
  `qna_bank.yaml`. A keyword the bank cannot resolve yields **no block at all** —
  the agent then answers from general knowledge, unsourced, which is why every
  configured keyword should resolve (all 10 currently do).
- **Substring keywords cut both ways.** A false positive costs an audience block on
  a turn that did not need one; a false negative means an ungrounded answer and no
  card. Widen the keywords rather than accept the latter.
- **The audience rules govern vocabulary, not depth.** How deep to go, whether to
  broaden, and how hard to push stay with the user profile and the supervisor; an
  explicit request in the user's own message outranks both.
- **The click still costs one small LLM turn**, because a card action always
  arrives as a turn. The card itself has already updated by then.
- **`OUTREACH_STATE_PATH` is optional.** The injector and both tools resolve the
  state file the same way: `OUTREACH_STATE_PATH` →
  `WORKSPACE_DIR/outreach/state.yaml` → **this package's own
  `outreach/state.yaml`**. `scripts/dev-feishu.ps1` exports neither env var, so the
  package-relative fallback is what makes the ordinary bring-up work unconfigured.
  Set the env var only to point at a state file outside the package; a value
  pointing at a missing file is ignored rather than allowed to shadow the real one.
  If no state file is found at all, no block is injected for anyone — the campaign
  goes dormant rather than teaching a cohort it cannot identify.

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

   Or skip the shell entirely and enroll by @-mention — see "Enrolling targets by
   @-mention" below. That path needs `controller_open_id` set, so fill it in now:
   it is the one field that decides who may start a daily DM campaign against
   somebody, and while it is empty **every** enrollment request is refused.

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

There is no detector to probe any more: nothing fans out of the channel for
Scenario 3, and nothing fires a trigger. What decides whether a question is
"on-campaign" is the prompt builder, so verify *that* — it needs a state file, a
cohort row for the asker, and a keyword the bank can resolve:

```bash
# Prints the injected block, or nothing at all when the turn is off-campaign.
# PYTHONIOENCODING is needed on Windows: a repo path containing Chinese cannot be
# printed to a cp1252 console.
PYTHONIOENCODING=utf-8 uv run python -c "
import sys; sys.path.insert(0, 'examples/haitun-workspace/tools')
import _outreach_confirm as oc
p = oc.state_path()
print(oc.literacy_context(oc.read_yaml_mapping(p), p, 'ou_REPLACE_ME', '智能体是什么') or '(no block)')
"
```

An empty result means one of those three is missing — check the `open_id` is in
`users` first, since that is the usual cause.

## Enrolling targets by @-mention

Both paths above need an `open_id` in hand, which is exactly what the person running
the campaign does not have: they know colleagues by name and face, and the id lives in
the org directory. So the controller can also just @ them:

```
把 @张三 @李四 加进来
```

The ids come from the `mentions:` line of `<feishu_context>`, which the channel fills
from the Feishu event (`_mention_facts` in `channel/feishu/client.py`). That line
exists **because** the ids are otherwise unrecoverable: lark's normalizer rewrites the
`@_user_N` placeholders in `content_text` into display **names**, and a name is not
unique. The agent must take ids from `mentions:`, never from the message text.

This works in a DM with the bot — the @ picker offers your contacts, not just chat
members — so no group is needed. It works in a group too, but the answer still goes to
the target's own DM.

`outreach_target_add` writes the rows, and it is an **authorization boundary**:

- The caller must equal `controller_open_id`. Anyone else gets `not_authorized`.
- An unset `controller_open_id` refuses everyone (`not_configured`). Fail-closed is
  deliberate: the permissive reading would let any user who reaches the bot sign up
  any colleague they can @.
- The gate lives in the tool, not the skill, because a prompt-level rule is advice and
  this write is not reversible by the person it affects.

Two things it deliberately does not do. It **sends nothing** — a new target starts at
`qna_reactive`, and Scenario 3 activates the next time they ask about agents in their
own DM, while Scenario 1 picks them up on its next daily run. Say that to the
controller, or the silence right after adding reads as a failure. And it **never
resets an existing target**: re-adding reports `already_a_target` and leaves the row's
card history alone, same as `--set`.

The row itself is seeded by `_outreach_confirm.fresh_user`, which the CLI calls too. A
row missing a field is worse than no row: `campaign_turn` still matches it and grounds
their turns, while the counters start from whatever `.get` defaulted to — a broken user
that looks enrolled.

## Stopping the campaign for one person

`outreach_target_pause` sets `status: paused` and touches nothing else, so **both**
scenarios skip that person while their whole history survives:

| | Paused | Removed (`--set` without them) |
| --- | --- | --- |
| Scenario 3 grounding + cards | stops | stops |
| Scenario 1 daily push | stops | stops |
| `answers[]`, counters, `familiarity_est` | **kept** | **deleted** |
| Reversible | yes, `paused=false` | no |

Removing a target used to be the only stop available, and the row *is* the progress —
so the only way to switch somebody off also threw away the learning history the cards
had built. Prefer pausing; remove only when you want the row gone.

The controller @-s them, same as enrolling:

```
先别再发给 @张三 了          # pause
可以继续给 @张三 发了        # resume
```

Both directions sit behind the `controller_open_id` gate, because *resuming* restarts
daily DMs at somebody. The user is **not** notified either way.

`status` is honoured by two readers: `campaign_turn` (which is why a paused user gets
no grounding, no card, and no re-teaching even from a click on a card that was already
on screen) and the Scenario 1 producer's `open_ids` list. `_outreach_confirm.is_paused`
owns the definition; `produce.py` carries a deliberate copy because it is `exec`-ed
standalone with no access to `tools/` — the pair is pinned by a test on each side.

**Only the literal `paused` value pauses.** A missing, empty or unrecognised `status`
stays active, so no row in a live campaign changes behaviour by being upgraded. Worth
knowing because `status` was previously written by the seed and read by **nothing at
all**: setting it by hand did nothing before, and any older note claiming otherwise
was wrong.

Two things a pause is not. `stage: done` is a handoff marker, not a stop — a graduated
user still gets grounding and a card if they ask again. And `scenario3.enabled: false`
is global; it switches the reactive half off for everyone.

## Prerequisites for an actual send

| Requirement | Check |
| --- | --- |
| Real `open_id`s in `state.yaml` | `discover_outreach_targets.py --check` |
| `controller_open_id` set (only to enroll by @-mention) | Empty → every enrollment refused |
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

## Who this is explained to

`scenario3.audience` decides *whose language* the answer is written in. It is the
reason the answer is no longer a file read: the cohort is made of **legal
officers**, and the bank's wording is aimed at a general reader, so sending it
verbatim confused "explained correctly" with "explained to this person".

| Field | Meaning |
| --- | --- |
| `audience.role` | Who is reading. Default `法务专员 (legal officer)`. A user row's own `role` overrides it |
| `audience.strategy` | The ordered rules. Omit for the built-in list; `[]` switches the block off entirely |

The built-in strategy (`_outreach_confirm.DEFAULT_AUDIENCE_STRATEGY`) is written
for how a legal officer already reads: definition before mechanism, as a contract
puts definitions before obligations; analogies from law rather than engineering
(a fixed workflow is *special authority*, an agent is *general authority* — the
agent picks its own steps inside the mandate; a tool call is the fiduciary acting,
since the model only proposes and the runtime executes; memory is the case file;
limits and risks are the disclaimer plus a duty to verify); liability and
consequence instead of architecture; what leaves an auditable trace; no
engineering jargon unless it is immediately translated; boundaries stated openly
(it can fabricate, data can leak, irreversible actions get confirmed first); and
a conclusion first, then short numbered points.

This governs vocabulary and ordering **only**. Depth, whether to broaden the
topic, and how hard to push stay with the user profile and the supervisor, and an
explicit instruction in the user's own message outranks all of it.

A different cohort therefore needs no code change — set `audience.role` and
`audience.strategy` in `state.yaml`.

## Content pages

The teaching content is `qna_bank.yaml`, composed **once, offline** (an LLM may
help write it, then it is frozen). It is injected as `<literacy_grounding>` and is
the answer's source of fact; revising content means editing that file.

Node order: `what-is-an-agent` → `agent-loop` → `tools-and-tool-calling` →
`agent-memory` → `agent-limits-and-risks`.

The bank entries name `source_page: wiki/<slug>.md`, and **those pages are not in
this package** — only `wiki/profiles/` and `wiki/supervisor/` exist under a DM
user's workspace. This used to be a real gap ("path B cannot read the wiki"):
a bank miss was supposed to be answered from the curriculum, and could not be.
Injecting the bank entry closes it — the agent is told, in the block itself, not
to invent a source page, and `wiki_read` is not part of this flow. If the six
pages are ever authored, they belong in the flat wiki (`wiki/<slug>.md`, tag
`agent-basics`; `wiki_dir()` is always `<workspace>/wiki`, subfolders unsupported).

## The `scenario3` schema

| Field | Meaning |
| --- | --- |
| `enabled` | `false` → nothing is injected and no card is sent; the campaign goes dormant |
| `keywords` | Case-insensitive substring match against the message text |
| `qa_bank_path` | Bank location, relative to the workspace |
| `audience.role` / `.strategy` | Who the answer is written for — see "Who this is explained to" |
| `followup.mode` | `immediate` (tool sends the follow-up) or `next_question` (defer to the user's next question) |
| `followup.closing` | The **whole** message sent on `understood`. Omit for the default (「很好！还有别的想问的吗？」); set `''` to send nothing |
| `followup.closing_done` | Same, for the answer that graduates the user |
| `card.ask_after_every_answer` | `false` → no card after a re-explanation either |
| `card.probe_question_every` | Every Nth exchange carries a real probe question, flagged in the grounding block for the **answer message** (the card is buttons only) |

Per-user fields written by the tools: `last_qa` (`qa_id`, `question`, `keyword`,
`topic`, `summary`, `card_message_id`, `sent_at`, then `answered_at` /
`self_assessment`; a card that follows a re-explanation also carries
`recheck: true`),
`answers[]` (capped at the most recent 200), `card_sent_count`,
`confident_streak`, `confident_count`, `not_understood_count`,
`familiarity_est` (local EMA, α=0.35 — the authoritative signal stays the user
profile and supervisor), `stage`, `handed_off_to_scenario1/2`.

`stage`: `qna_reactive` → `done` (written automatically once
`confident_count ≥ thresholds.confident_answers_needed` **and**
`familiarity_est ≥ thresholds.familiarity_done`) → handoff.

`status`: `active` (default) or `paused`. Set by `outreach_target_pause`, and the one
per-user switch both scenarios honour — see "Stopping the campaign for one person".
Only the literal `paused` pauses; anything else, including a missing value, is active.

## The bank schema

Each entry under `qa_bank:` carries `topic`, `source_page`, `answer` (sent as the
reply), `summary` (one line, kept for the card's `business_context` and the handoff —
no longer rendered, since the card is buttons only), and the follow-ups chosen by the
card answer:

| Card answer | `value.action` | What is sent |
| --- | --- | --- |
| ✅ 懂了 | `understood` | `scenario3.followup.closing` — not a bank field |
| 🤔 不太懂 | `partial` | `re_explain` |
| ❌ 没看懂 | `not_understood` | `restart` |

The mapping for the two confused answers is unconditional — they always re-explain.
`probe_question` is appended to the **answer message** on every
`probe_question_every`-th exchange, to verify a claimed "understood"; it is never used
as a follow-up, and never sits on the card — an open question is not something three
buttons can answer, and it has to be read next to the answer it checks.

`next_message` is therefore unused by Scenario 3. It is kept in the bank for the
Scenario 1 handoff, where the agent does drive the curriculum forward.

`aliases:` maps any other keyword to a canonical entry; a keyword resolving to
neither is a bank miss.

## Who writes what

- `outreach_confirm_card` / `outreach_confirm_handle` — only the asking user's row.
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
| Tool results (channel log) | `card_sent` vs `card_send_failed` from `outreach_confirm_card` |
| Session log, `WARNING` | `card missing after the answer, sent by after-turn hook` — how often the model ignores the skill. Should trend to zero; a rising count means the skill needs sharpening, not the hook |
| `<open_id>/wiki/profiles/session-<sha256>.md` | `turns`, per-topic `familiarity` / `depth` / `goal` — the authoritative learning signal |
| `<open_id>/wiki/supervisor/users/<hash>/metrics.jsonl` | Turn count, advice source (live/cache/unavailable), latency |
| `<open_id>/wiki/supervisor/users/<hash>/domains/<domain>.yaml` | `question_count`, `visited_nodes`, `repeated_surface_questions`, `cognitive_history` |

The profile id is `session-<sha256>` (a DM session's identity), not `user-<hash>` —
`_user_profile.py` derives it from the session id when no explicit `profile_id` or
`user_id` is passed.

Graduation is `confident_count ≥ 3` **and** `familiarity_est ≥ 0.7` — with the
caveat that self-assessment must be cross-checked against actual `probe_question`
answers, not taken as proof on its own.

## Keep every keyword resolvable

A keyword with no bank entry injects **no grounding at all**, and the agent then
answers from general knowledge with no curriculum behind it. So the one standing
maintenance rule is that every entry in `scenario3.keywords` must resolve — through
`qa_bank:` or through `aliases:`. All 10 currently do. Check after any edit:

```bash
PYTHONIOENCODING=utf-8 uv run python -c "
import sys; sys.path.insert(0, 'examples/haitun-workspace/tools')
import _outreach_confirm as oc
p = oc.state_path(); state = oc.read_yaml_mapping(p)
bank = oc.read_yaml_mapping(oc.bank_path(state, p))
missing = [k for k in oc.keywords(oc.scenario_config(state)) if oc.resolve_entry(bank, k) is None]
print('unresolved:', missing or 'none')
"
```
