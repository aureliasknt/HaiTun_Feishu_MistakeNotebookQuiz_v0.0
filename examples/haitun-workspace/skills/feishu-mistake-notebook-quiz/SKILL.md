---
name: feishu-mistake-notebook-quiz
description: "Send rotating mistake-notebook quiz cards and grade clicks. Use for 错题本 question cards, mistake_notebook_grade_answer callbacks, or a setup prompt that @-mentions at least two target users. The first card is prompt+5 minutes; recurring cards use an adjustable interval inside 08:00-22:00 via mistake_notebook_quiz_send_next."
---

# Feishu Mistake Notebook Quiz

This skill sends rotating quiz questions as Feishu interactive cards with four option buttons,
and grades the answer when the recipient taps one. Direct one-off sends use
`feishu_message_send_card`; scheduled cohorts use `mistake_notebook_quiz_send_next`,
`schedule_manage`, and `feishu_bitable_create_record` for answer logging.

This flow is intended to be test-ready and safe for real users. If any required step cannot be
verified, stop and report the issue clearly instead of guessing.

## Core contract

- Each question is sent as one card. The card carries the question text and four buttons, A through D.
- Each button must use one fixed action string: `answer_a`, `answer_b`, `answer_c`, or `answer_d`.
  These are reused for every question and identify which button position was pressed, not which
  question was targeted.
- `action_handlers_json` must list all four action strings and point them to the same handler name:
  `mistake_notebook_grade_answer`.
- `business_context_json` must carry all information needed by the click recipient's own session:
   question id, theme, question text, correct answer, recipient identifier, and write coordinates
   (`app_token`, `table_id`). Do not assume the recipient session has sender-side memory.
   Always read these values fresh from `business_context` for that click.
- The channel already enforces single-use cards and fails closed on unmatched actions. This skill must
  not try to re-implement either behavior.

## Mandatory preflight checks

Before doing anything important, verify the following:

1. The bot is already added as an editor collaborator on the Feishu base. If not, do not proceed with
   a real-user write path. A missing collaborator can trigger an OAuth prompt for the end user.
2. `identity="bot"` is used explicitly when writing records. Never leave it blank and never allow it to
   fall back to a real-user authorization flow.
3. `table_id` is resolved from `feishu_bitable_list_tables(app_token)` by matching the visible table name.
   Never trust a hand-typed or pasted `table_id`.
4. The required fields for the record are known before writing. If the table schema is unknown, inspect it
   first rather than guessing column names.
5. The date value is a millisecond epoch integer, not a date string.
6. The recipient is resolved to a real id before sending. `receive_id` must be an open_id (`ou_…`),
   chat_id (`oc_…`), or email — never a display name like "Aurel佳芬2". Prefer
   `feishu_contact_search(name)` as the default path when all you have is a person's name. Only use
   `feishu_chat_find_member(chat_id, name)` when you specifically know which group they are in and want
   to resolve from that group roster. A new person who cannot be found is a contact-scope problem:
   stop and resolve it rather than guessing or reusing another person's open_id.

If any of these checks cannot be completed, stop. Do not continue with a write or a send that would
create a confusing or unsafe experience for the user.

## Before you write anything

The bot must be added as an editor collaborator on the mistake notebook base itself, inside Feishu,
via the base's own Share button, the same way you would add a person. This is a one-time setup step,
not something to redo per user. Without it, `feishu_bitable_create_record` cannot write with the bot's
own identity and may fall back to asking the person who triggered the write to authorize it personally.
That is acceptable during internal testing, but it is not acceptable for a real user. No quiz recipient
should ever see a Feishu authorization screen.

Never resolve `table_id` from a value someone typed or pasted by hand. Always call
`feishu_bitable_list_tables(app_token)` first and match the real `table_id` to the visible table name,
for example 答题记录. A single mis-typed character can silently point at the wrong table or an empty one.

`日期` must be sent as a millisecond epoch timestamp, an integer, never a date string like
`"2026-08-03"`. Feishu can accept the write and return `ok: true` while silently dropping the entire
record if the column type does not match what was sent. After every write, confirm the row actually
landed with `feishu_bitable_list_records` or an equivalent readback. Do not trust `ok: true` alone as
proof that anything was saved.

## Sending a question

0. Resolve the recipient first. If you only know the person's name, use `feishu_contact_search(name)`
   first. Only use `feishu_chat_find_member(chat_id, name)` when you already know their group and need to
   resolve from that group's member list. Use the returned real id as `receive_id` in the send call below.
   Never pass a display name as `receive_id`: Feishu send APIs accept open_id / chat_id / email only, and a
   name either errors or silently targets nothing.

1. Build the card as legacy-format JSON, using one distinct action string per button:

   ```json
    {"config": {"wide_screen_mode": true},
      "header": {"title": {"tag": "plain_text", "content": "本周错题本 · 外部成果"}, "template": "blue"},
      "elements": [
         {"tag": "markdown", "content": "问题：一个大目标要满足什么条件才算数？"},
         {"tag": "action", "actions": [
            {"tag": "button", "text": {"tag": "plain_text", "content": "A 团队内部认为完成了就算"},
             "value": {"action": "answer_a"}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "B 成果必须来自外部"},
             "value": {"action": "answer_b"}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "C 项目经理确认了就算"},
             "value": {"action": "answer_c"}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "D 有清晰的时间节点就算"},
             "value": {"action": "answer_d"}}
         ]}
      ]}
   ```

2. Build `business_context_json` alongside it:

   ```json
      {"question_id": "q1", "theme": "外部成果",
         "question_text": "一个大目标要满足什么条件才算数？",
         "correct_answer": "B", "employee_open_id": "ou_真实open_id",
         "recipient_name": "收件人显示姓名",
         "app_token": "bascn_xxx", "table_id": "tblxxx"}
   ```

## Question bank

Use these completed examples as the quiz source material when preparing weekly cards.

### 1. 外部成果

- 问题：一个大目标要满足什么条件才算数？
- A. 团队内部认为完成了就算
- B. 成果必须来自外部
- C. 项目经理确认了就算
- D. 有清晰的时间节点就算
- 正确答案：B
- 依据：SOP原文写明大目标的成果都来自于外部，容易被误以为内部认可就够了。

### 2. 价值观

- 问题：为了让自己看起来更努力，把TODO list写得比实际进度快，这属于什么？
- A. 可以接受的小技巧
- B. 红线行为，不允许
- C. 只要后面补上就没关系
- D. 没被发现就不算问题
- 正确答案：B
- 依据：SOP把这一条单独列出来，明确写着弄虚作假为红线。

### 3. 执行力

- 问题：TODO最核心要看哪两点？
- A. 是否写得详细，是否有截止日期
- B. 按时按质按量，有没有给用户带来价值
- C. 完成速度，团队人数
- D. 领导是否满意，字数多少
- 正确答案：B
- 依据：SOP原文直接点名了这两条，容易被简化成只看有没有按时完成。

### 4. 来自评论区的真实分歧

- 问题：员工应该先写TODO再让mentor检查，还是mentor先检查再写？
- A. 先写，mentor之后检查
- B. mentor先检查，员工再写
- C. 每周统一开会检查一次
- D. 不需要mentor检查
- 正确答案：A
- 依据：这道题不是我编的，是张浩在评论区里问了周熠这个确切的问题，周熠回复检查之后要更新，说明是先写后查。这是公司里真实发生过、需要澄清一次的困惑。

### 5. 更新频率

- 问题：TODO list应该在每周哪几天更新？
- A. 每天
- B. 周一、周三、周五
- C. 只在周一
- D. 每两周一次
- 正确答案：B
- 依据：SOP原文写明每人每周周一、周三、周五更新TODO list。

### 6. 更新截止时间

- 问题：TODO list更新应该在什么时间点之前完成？
- A. 上午9点
- B. 中午12点
- C. 下午15点
- D. 下班前不限时间
- 正确答案：C
- 依据：SOP原文写明下午15点以前要更新进真知统一的todo库。

### 7. 更新后的动作

- 问题：更新完TODO list之后，还需要做什么？
- A. 不需要通知任何人
- B. at相应的mentor
- C. 发邮件给全公司
- D. 等对方主动来看
- 正确答案：B
- 依据：SOP原文写明更新后要at相应mentor，不是被动等待。

### 8. 优先级排序

- 问题：以下哪个优先级顺序是正确的？
- A. 重要不紧急排在重要且紧急前面
- B. 重要且紧急排在最前
- C. 不重要不紧急排在第一位
- D. 优先级不重要，随便排都可以
- 正确答案：B
- 依据：SOP原文顺序是重要且紧急、重要不紧急、紧急不重要、不重要不紧急。

### 9. 项目经理反馈时限

- 问题：项目经理收到TODO更新后，应该在多久内给出反馈？
- A. 立刻当场
- B. 24小时内
- C. 一周内
- D. 不强制要求时限
- 正确答案：B
- 依据：SOP原文写明项目经理在收到TODO更新内24小时内反馈。

### 10. 反馈方式建议

- 问题：SOP建议用什么来辅助项目经理给反馈？
- A. 人工逐条手写
- B. HaiTun智能体
- C. 外部咨询公司
- D. 不建议使用任何工具
- 正确答案：B
- 依据：SOP原文写明建议使用HaiTun智能体辅助反馈。

### 11. 大目标的时间跨度

- 问题：一个大目标通常应该在多长时间内完成？
- A. 1到2天
- B. 1周到1个月
- C. 3个月到6个月
- D. 没有时间限制
- 正确答案：C
- 依据：SOP原文写明大目标是在一段较长时间内，3个月到6个月，取得某项成果。

### 12. 大目标需要包含的要素

- 问题：写一个大目标时，除了成果本身，还需要写清楚什么？
- A. 只需要写清楚要做的事情
- B. 事情的描述、时间、标准
- C. 只需要一个截止日期
- D. 只需要负责人姓名
- 正确答案：B
- 依据：SOP原文写明大目标需要有事情的描述、时间、标准。

### 13. 大目标的对齐要求

- 问题：大目标应该和什么对齐？
- A. 不需要对齐任何东西，自己定就行
- B. 组织上一级的大目标
- C. 上一年度的总结
- D. 友商的公开目标
- 正确答案：B
- 依据：SOP原文写明大目标要与组织上一级的大目标对齐。

### 14. 小目标的时间跨度

- 问题：一个小目标通常应该在多长时间内达到？
- A. 1到2天
- B. 1周到1个月
- C. 3个月到6个月
- D. 半年以上
- 正确答案：B
- 依据：SOP原文写明小目标是在一段较短时间内，1周到1个月，达到某个里程碑。

### 15. 小目标的性质

- 问题：小目标一般是什么的拆解？
- A. 大目标的拆解
- B. TODO的拆解
- C. 和大目标没有关系
- D. 只是个人计划，不需要拆解自谁
- 正确答案：A
- 依据：SOP原文写明小目标一般是大目标的拆解。

### 16. 大目标暂时没有小目标怎么办

- 问题：如果一个大目标暂时没有对应的小目标，代表什么？
- A. 这个大目标写错了，必须重写
- B. 该大目标暂时不做
- C. 系统会自动报错
- D. 这种情况不被允许
- 正确答案：B
- 依据：SOP原文写明大目标可以暂时没有小目标对应，代表该大目标暂时不做。

### 17. 大目标和小目标的最低对应关系

- 问题：一个人的所有大目标里，至少要有几个大目标有对应的小目标？
- A. 0个，都可以没有
- B. 至少1个
- C. 必须全部都有
- D. 至少一半
- 正确答案：B
- 依据：SOP原文写明大目标可以拆解为多个小目标，但至少有1个大目标有对应的小目标。

### 18. TODO的时间跨度

- 问题：一个TODO最长不应该超过多少天？
- A. 1天
- B. 3天
- C. 1周
- D. 1个月
- 正确答案：B
- 依据：SOP原文写明TODO是在很短的时间内，1到2天，最长不超过3天。

### 19. TODO的性质

- 问题：TODO一般是什么的拆解？
- A. 大目标的拆解
- B. 小目标的拆解
- C. 和小目标无关，是独立存在的
- D. 项目经理指派的任务
- 正确答案：B
- 依据：SOP原文写明TODO一般是小目标的拆解。

### 20. TODO应该怎么写

- 问题：按照SOP的定义，TODO应该说清楚什么，而不是只说要干什么？
- A. 只需要说要干什么就够了
- B. 什么时间节点干成满足什么标准的什么事
- C. 只需要写一个动词
- D. 谁来做这件事
- 正确答案：B
- 依据：SOP原文写明TODO不是说要干什么，而是说什么时间节点干成满足什么标准的什么事。

### 21. deadline的要求

- 问题：能有deadline的TODO，应该怎么处理？
- A. 可写可不写
- B. 一定要写deadline
- C. 只有大目标需要deadline
- D. deadline由项目经理统一填写
- 正确答案：B
- 依据：SOP原文写明能有deadline的一定要有deadline。

### 22. 持续性TODO的写法

- 问题：对于持续性的TODO，SOP建议怎么写？
- A. 必须拆成多条每天单独记录
- B. 简单写明即可
- C. 不需要记录
- D. 每次都要重新申请审批
- 正确答案：B
- 依据：SOP原文写明持续TODO简单写明即可。

### 23. 小目标粒度过大时怎么处理

- 问题：如果一个小目标的粒度过大，应该怎么办？
- A. 直接删掉这个小目标
- B. 拆解成子目标
- C. 合并进大目标里
- D. 交给项目经理重写
- 正确答案：B
- 依据：SOP原文写明小目标如果粒度过大，可以拆解成子目标。

### 24. TPMF闭环的适用范围

- 问题：TPMF闭环这个标准适用于哪些层级？
- A. 只适用于大目标
- B. 只适用于TODO
- C. 大目标、小目标和子目标都需要
- D. 只适用于项目经理自己的目标
- 正确答案：C
- 依据：SOP原文写明大目标、小目标和子目标都需要以TPMF闭环为标准。

### 25. TPMF闭环强调的视角

- 问题：以TPMF闭环为标准时，应该说清楚什么？
- A. 团队做了哪些事情
- B. 为用户带来什么价值
- C. 花了多少工时
- D. 用了哪些工具
- 正确答案：B
- 依据：SOP原文写明要以用户为中心，说清为用户带来什么价值，而不是要做什么事。

### 26. 目标的验收规则

- 问题：大目标、小目标、子目标要怎样才算完成？
- A. 自己觉得完成了就算
- B. 申请上级验收，验收通过才算完成
- C. 时间到了自动算完成
- D. 项目经理口头确认即可
- 正确答案：B
- 依据：SOP原文写明都需要申请上级验收，验收过了才算完成。

### 27. TPMF小组长的额外要求

- 问题：TPMF小组长的目标闭环里，还需要重点突出什么？
- A. 团队人数的增长
- B. 和友商的比较
- C. 加班时长
- D. 会议次数
- 正确答案：B
- 依据：SOP原文写明TPMF小组长的目标闭环中，还要重点突出和友商的比较。

### 28. TODO标准的牵引原则

- 问题：TODO的标准是以什么为牵引的？
- A. 项目经理的个人喜好
- B. TPMF闭环
- C. 团队投票
- D. 上一次TODO的完成情况
- 正确答案：B
- 依据：SOP原文写明TODO的标准同样以TPMF闭环为牵引。

### 29. 入库格式要求

- 问题：TODO list在录入时有什么统一要求？
- A. 每个人可以用自己习惯的格式
- B. 统一入库，统一格式
- C. 只需要存在自己电脑上
- D. 只有大目标需要统一格式
- 正确答案：B
- 依据：SOP原文写明统一入库，统一格式。

### 30. 个人TODO与小组TODO的关系

- 问题：个人TODO应该和什么保持一致？
- A. 不需要和任何东西保持一致
- B. 小组TODO
- C. 上一季度的个人TODO
- D. 友商的公开计划
- 正确答案：B
- 依据：SOP原文写明个人TODO要与小组TODO对齐。

### 31. 时间点的要求

- 问题：TODO、大目标、小目标里，时间点应该是什么方向的？
- A. 可以是过去已经发生的时间点
- B. 不应该有过去的时间点
- C. 时间点是可选的，不强制
- D. 只有TODO需要注意这一点
- 正确答案：B
- 依据：SOP原文写明所有项，包括todo、大目标与小目标，都不应该有过去的时间点。

### 32. 重要TODO的列出规则

- 问题：所有重要的TODO应该怎么处理？
- A. 挑几个写就行
- B. 都需要列出来
- C. 只写标题不写细节
- D. 由项目经理决定要不要列
- 正确答案：B
- 依据：SOP原文写明所有重要的todo都需要列出来，不重要的可以不列，或者写一个百分比估计。

### 33. TODO list的整体定位

- 问题：SOP里怎么形容TODO list这件事的重要性？
- A. 一个可有可无的记录习惯
- B. 真知管理和考核的重要抓手
- C. 只是给新人练习用的
- D. 主要是用来存档，不影响考核
- 正确答案：B
- 依据：SOP原文开篇第一条就写明TODO list是真知管理和考核的重要抓手，务必认真对待。

3. Call:

   ```text
   feishu_message_send_card(
     receive_id="ou_真实open_id",
     card_json="<card JSON above>",
     business_context_json="<business context above>",
     action_handlers_json='{"answer_a": "mistake_notebook_grade_answer",
                             "answer_b": "mistake_notebook_grade_answer",
                             "answer_c": "mistake_notebook_grade_answer",
                             "answer_d": "mistake_notebook_grade_answer"}'
   )
   ```

4. Confirm the send succeeded before moving on. If `callback_context_saved` comes back false, stop and
   report that the card was not successfully delivered. Do not retry blindly and create duplicate cards.

## Grading a click

Triggered when a `<feishu_card_action>` message arrives.

The channel grades the selected answer deterministically in Python and sends fixed feedback without an
LLM turn. After that feedback is delivered, it shows `⏳ 正在保存你的答案…`, writes the Base row
directly with the bot's tenant token, and verifies it by returned `record_id`. It then edits the visible
status to `✅ 已记录`. Neither grading nor persistence invokes the LLM/session.

1. Check `dispatch.matched`. If it is not `true`, do not grade anything and do not guess a handler.
   Say that the click could not be matched and stop.
2. Read `action.value.action`, one of `answer_a` through `answer_d`, and map it to a letter:
   `answer_a` -> A, `answer_b` -> B, `answer_c` -> C, `answer_d` -> D. Compare that letter against
   `business_context.correct_answer`. This is reading and reasoning, not a tool call.
3. Reply to the user in plain, ordinary language, the way a person would tell a coworker whether they
   got the quiz question right. Build the explanation from `business_context.question_text` and
   `business_context.theme`, but never write those field names, any tool name, or the words
   `dispatch` or `handler` into the reply itself. The data is for the model to reason with, not for the
   user to see named.

   Good: "答对了，成果确实必须来自外部才算数。"
   Good: "这题不对哦。正确答案是 B：成果必须来自外部。大目标要算数，看的是成果是否来自外部、可验证，不是团队内部觉得做完了就算，也不是项目经理点头就算。"
   Bad: any sentence containing a tool name, a field name, or the words "I will", "calling",
   "handler", or "business_context".
4. Read `app_token`, `table_id`, and `recipient_name` from `business_context` and, if the
   coordinates are present, log one row with
   `feishu_bitable_create_record`, `identity="bot"`, using fields that match the table's real column names.
   Write `recipient_name` unchanged to the text column `收件人姓名`; never derive or guess a name
   from an open_id.
   `日期` must be a millisecond epoch timestamp, not a date string. If either `app_token` or `table_id`
   is missing, do not claim the answer was logged. Example:

   ```json
   {"员工": "ou_真实open_id", "收件人姓名": "收件人显示姓名", "题目": "q1", "主题": "外部成果",
    "选择": "C", "正确答案": "B", "判定": "错", "日期": 1754179200000}
   ```

   Then confirm the row actually landed with `feishu_bitable_list_records` before telling the user it was
   logged. `ok: true` alone is not sufficient proof; a type mismatch on any field can cause a silent
   full-record drop.
5. If the answer was wrong, optionally reschedule the same question for next week using the
   `feishu-schedule-message` skill's `fire=tool` pattern, pointed at `feishu_message_send_card` instead of
   the plain-text example in that skill's own docs:

   ```text
   schedule_manage(
     action="create",
     schedule_name="mistake-notebook-q1-retry",
     once_at="2026-08-07 15:00",
     fire="tool",
     tool="feishu_message_send_card",
     tool_args='{"receive_id":"ou_真实open_id","card_json":"...","business_context_json":"...","action_handlers_json":"{\"answer_a\":\"mistake_notebook_grade_answer\",\"answer_b\":\"mistake_notebook_grade_answer\",\"answer_c\":\"mistake_notebook_grade_answer\",\"answer_d\":\"mistake_notebook_grade_answer\"}"}',
     visibility="silent",
     description="错题本 q1 下周复习"
   )
   ```

   This exact usage is not yet demonstrated anywhere in the repo. It should work because `fire=tool`
   resolves the tool name generically, but it should be confirmed once against a real send before being
   relied on in production.

## Setting up the recurring quiz schedule (@ setup trigger)

Trigger: a user asks to set up or reset the quiz and @-mentions the future recipients. The
number of recipients is not fixed; support every request containing **at least two distinct
non-bot users**.

### 1. Read recipients from structured Feishu context

The Feishu channel adds `mentioned_users_json` to `<feishu_context>`. It contains only real,
non-bot mentions and already excludes `饶佳芬的海豚` itself. Use every distinct `open_id` in
that array, preserving message order. Never treat the sender or the bot as a recipient unless
they also appear as a non-bot mention. If fewer than two distinct `ou_...` ids remain, stop and
ask the sender to @ at least two people.

App availability set to “all members” only controls who can access the bot; it is not a target
list. The `mentioned_users_json` ids are the authoritative delivery list for this setup.

### 2. Resolve Base coordinates

Obtain `app_token` from the supplied Feishu Base URL. Call
`feishu_bitable_list_tables(app_token)` and match the visible table name `答题记录` to obtain
the real `table_id`. Never accept a guessed or hand-typed table id.

### 3. Validate the setup time

Use the local schedule clock (`TZ`, normally `Asia/Shanghai`). Compute:

- Convert `message_create_time_ms` from `<feishu_context>` to the configured local timezone.
  This is the authoritative prompt-received time; do not substitute the later tool-call time.
- `first_at = prompt received time + 5 minutes`
- Read an explicitly requested `interval_minutes`; default to `60` when the prompt does not
  specify one. For short testing, use `10` only when requested.
- `recurring_not_before = first_at + interval_minutes`
- Use a one-minute heartbeat cron, `* 8-22 * * *`. The sender—not cron—enforces both
  `interval_minutes` and the inclusive 08:00–22:00 window.

The first card must be both same-day and inside the 08:00–22:00 delivery window. Therefore a
setup prompt is accepted only from **07:55 through 21:55 inclusive**. Outside that range, do
not create partial schedules; explain the allowed setup window.

### 4. Remove the previous cohort

Call `schedule_manage(action="list")`, then delete every existing schedule whose name starts
with `quiz-first-` or `quiz-hourly-`. This includes the legacy `quiz-*-user-N` names. Remove
the whole previous cohort before creating the new one so removed users cannot keep receiving
cards.

### 5. Create two schedules per recipient

Use the complete real recipient `open_id` in each schedule name. Feishu open IDs contain only
characters accepted by `schedule_manage`, and the complete ID avoids suffix collisions. For
every recipient create:

1. One q1/reset one-shot at `first_at`:

```text
schedule_manage(
  action="create",
  schedule_name="quiz-first-<ou_recipient>",
  once_at="<first_at: YYYY-MM-DD HH:MM>",
  fire="tool",
  tool="mistake_notebook_quiz_send_next",
  tool_args='{"receive_id":"<ou_recipient>","app_token":"<app_token>","table_id":"<table_id>","recipient_name":"<display name>","interval_minutes":<interval_minutes>,"window_start":"08:00","window_end":"22:00","reset":true}',
  visibility="silent",
  description="错题本首题（设置后 5 分钟）- <display name>"
)
```

2. One recurring schedule with a one-minute heartbeat:

```text
schedule_manage(
  action="create",
  schedule_name="quiz-hourly-<ou_recipient>",
  cron="* 8-22 * * *",
  fire="tool",
  tool="mistake_notebook_quiz_send_next",
  tool_args='{"receive_id":"<ou_recipient>","app_token":"<app_token>","table_id":"<table_id>","recipient_name":"<display name>","interval_minutes":<interval_minutes>,"window_start":"08:00","window_end":"22:00","not_before":"<recurring_not_before: YYYY-MM-DD HH:MM>"}',
  visibility="silent",
  description="08:00-22:00 每<interval_minutes>分钟错题本 - <display name>"
)
```

`mistake_notebook_quiz_send_next` owns card construction and per-recipient question state. It
sends q1, q2, q3, q4, then wraps to q1, and advances only after Feishu confirms both delivery
and callback-context persistence. Do not embed a static card in the schedules. The
`not_before` guard prevents an early recurring tick near setup time from racing ahead of the
five-minute q1 send.

The heartbeat wakes the tool once per minute. Most wakes return `skipped`; a card is sent only
when at least `interval_minutes` have elapsed since that recipient's last successful send. The
sender also skips every time after 22:00, including 22:01–22:59. Missed sends do not burst or
catch up; the next heartbeat sends at most one card.

Every successful create response must be free of `[Warning: scheduler wake failed ...]`.
`schedule_manage` wakes Gateway's dedicated scheduler immediately after creation. If any wake
warning or create error occurs, stop and report that setup is incomplete; do not claim the
cohort is active.

### 6. Confirm without leaking internals

Only after all `2 × recipient_count` creates succeed, confirm:

- recipient display names (open_ids only when names are unavailable);
- first delivery time (`first_at`);
- daily recurring window 08:00–22:00 and the chosen interval;
- schedules work only while the Gateway/PC is running.

Do not print table ids, callback mappings, card JSON, or full tool arguments.

### Adjusting the interval later

Call `schedule_manage(action="list")`, then view every active `quiz-hourly-...` task. Patch
each task with the same existing `tool_args` except for `interval_minutes`; preserve recipient,
Base coordinates, display name, window, and `not_before`. Keep cron as `* 8-22 * * *`.
Changing `interval_minutes` does not reset question progress. Use `10` for testing and `60`
for normal hourly delivery. Never replace the whole `tool_args` object with only the interval:
`schedule_manage(action="patch")` treats it as a full replacement.

### Updating targets later

Repeat the entire setup. Delete the old cohort first, then create a fresh pair for every newly
@-mentioned recipient. The Base coordinates may be reused only while the same Base/table is
still confirmed.

## Failure handling rules

- If a required tool returns an error, a timeout, or an unexpected shape, do not invent a success story.
  Stop and tell the user that the action could not be completed.
- If the send path does not confirm delivery, do not claim the card was sent.
- If the write path does not confirm a saved row, do not claim the answer was logged.
- If any required field is missing from `business_context`, stop rather than guessing the answer.
- If the action string is not one of the allowed four values, stop rather than mapping it implicitly.
- If the model cannot verify a prerequisite, it should fail closed rather than proceeding with a risky action.

## Send-time output policy (strict)

When the user asks to send a question card, the visible reply must stay minimal and must not leak quiz internals.

- After a successful card send, output exactly `NO_REPLY` (uppercase, no extra text), so the channel sends only the card.
- Never reveal the correct answer before the user clicks.
- Never print internal process text, including tool names, field names, callback status, session status,
   dispatch status, record ids, table ids, or any verification/debug notes.
- Do not print a long preamble plus the card. Send the card as the primary output.
- If send success cannot be confirmed, do not output `NO_REPLY`. In that case, return one short failure message only.
- If send confirmation fails (`callback_context_saved` false or send error), do not claim success; report a
   short failure message and stop.

## Suggested table structure

If the table does not exist yet, suggest these columns, using the same cleanup pattern as
`feishu-mentor-feedback`: clear the table, list fields, delete placeholder fields, and only then write
real data.

| Column | Type | Notes |
|---|---|---|
| 员工 | 文本 / 人员 | open_id or name of who answered |
| 收件人姓名 | 文本 | display name captured from the setup @mention |
| 题目 | 文本 | question_id, e.g. q1 through q4 |
| 主题 | 文本 | 外部成果 / 价值观 / 执行力 / 来自评论区的真实分歧 |
| 选择 | 文本 | A/B/C/D, what they actually picked |
| 正确答案 | 文本 | A/B/C/D, from business_context |
| 判定 | 文本 | 对 / 错 |
| 日期 | 日期 / 文本 | When it was answered |

## Minimum acceptance checklist

The skill is only considered ready for real use when all of the following have been verified:

- A card can be sent successfully and the send response confirms delivery.
- A click can be matched and graded correctly.
- The answer is written to the correct table and can be read back successfully.
- The flow fails safely when a prerequisite is missing or a tool returns an error.
- No user is ever sent to an OAuth authorization screen as part of this workflow.

## Boundaries

- Never trust `dispatch.handler` when `dispatch.matched` is not `true`.
- Never assume the correct answer from memory or from earlier in the conversation; always read it fresh
  from `business_context` on that specific click.
- Only log an answer once per click. The channel already guarantees that a card cannot be double-clicked,
  so this skill does not need its own dedupe logic.
- Do not hand-write `schedules/*/TASK.md` for the retry reminder; always go through `schedule_manage`
  per the `feishu-schedule-message` skill's rules.
- Use the four fixed action strings, `answer_a` through `answer_d`, exactly as written. Do not invent
  per-question action names, since that would require adding new entries to `action_handlers_json` for
  every single question instead of reusing one fixed set of four.
- Never let a real user hit an OAuth authorization prompt for something they did not initiate themselves.
  Confirm the bot is a collaborator on the base and always write with `identity="bot"`.
- Never send `日期` as a string; always send it as a millisecond epoch integer, and always read a write
  back to confirm it landed before reporting success.
- Never trust a hand-typed `table_id`; always resolve it from `feishu_bitable_list_tables` by matching
  the table's visible name.
- Never pass a display name as `receive_id`; always resolve the recipient's open_id first via
  `feishu_chat_find_member` / `feishu_contact_search`.
