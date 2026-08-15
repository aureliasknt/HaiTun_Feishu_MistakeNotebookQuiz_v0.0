---
name: outreach-confirmation-card
description: Use for the agent-literacy campaign (Scenario 3): when a target user asks about agent/LLM/HaiTun topics, when a <feishu_card_action> arrives with handler outreach_confirm, or when deciding whether to stay silent because the deterministic path already answered. Covers the answer + 理解确认卡 loop, the bank-miss fallback, and the handoff to Scenario 1.
category: productivity
agent_editable: true
updated_at: 2026-08-12T08:27:02Z
---

# 理解确认卡（场景 3：反应式问答）

目标用户每问一次智能体/海豚相关的问题，就回答 + 发一张**理解确认卡**（懂了 / 不太懂 / 没看懂）。
答案默认来自静态答案库，**用户等待的那条路径上没有大模型**。卡片的回答被记入状态，
用来决定下一步教什么，并作为交接场景 1、场景 2 的基线。

## When to use

- 目标用户（`outreach/state.yaml` 的 `users`）私聊问到智能体/大模型/海豚等话题。
- 收到 `<feishu_card_action>`，且 `dispatch.handler` 为 `outreach_confirm`。

## When not to use

- 提问者不在 `users` 名单里 → 当普通问答正常回答，不发卡、不写状态。
- 群聊里的提问 → 正常回答即可。卡片和答案都发往 `open_id`（私聊），发到群里会答错地方。
- 场景 1 的每日推送（那是 `outreach-daily-send`，`fire=prompt`）。

## 三条路径

### A. 确定性路径（默认，0 LLM）

mapper 命中关键词 → TRIGGER `outreach-confirm-auto` → `outreach_confirm_send`：
发答案 + 发卡 + 写 `last_qa`。全程毫秒级，**你不需要做任何事**。

**你在后台那一轮要做的唯一判断：闭嘴。** 每条私聊消息仍会照常触发一轮 session
（`_AgentEventFanout` 先跑内置 handler 再 fan-out，这是框架下限，不是本方案能去掉的）。
所以每次要回答疑似智能体话题的问题前：

1. 读 `outreach/state.yaml` 里该 `open_id` 的 `last_qa.sent_at`；
2. 若在 `scenario3.dedup_window_seconds`（默认 60 秒）之内 → **本轮保持沉默**：
   按框架约定回 `NO_REPLY`（且**只有**这四个字，不要附带任何其他文字）。
   不要重复回答，不要再发第二张卡。

> 系统提示的 Silent Replies 一节要求「无话可说时只回 `NO_REPLY`」，Channel 会把
> **整段独立**的该 token 吞掉，用户看不到。但它必须是本轮**唯一**的输出——
> 一旦掺进别的文字，过滤器就会放行，用户会看到那四个字。

时序上是安全的：确定性工具在毫秒内写完 `sent_at`，你这一轮要几秒后才读到它。

### B. 大模型兜底（少见）

两种情况：命中关键词但答案库没有对应条目（工具返回 `bank_miss`，什么都没发）；
或者没命中关键词但 `is_learning_question` 为真（例如换了种说法问同一件事）。

这一轮由你正常回答，按 supervisor advice 的 `response_strategy` 组织表达，**然后发确认卡**。

> **先试 `wiki_read`，但别指望它。** 飞书私聊每个 user 有独立 workspace
> （`<能力包>/<open_id>/`），`wiki_read` 解析的是**这一轮的** workspace，而那里通常只有
> `wiki/profiles/`，没有 `agent-basics` 那六页。读不到就**不要**编造来源页名——
> 用 `read` 直接读 `outreach/qna_bank.yaml` 里相邻条目的措辞对齐口径，或者如实按你自己的
> 理解回答但不谎称有来源。详见 `outreach/README.md` 的 "Known gap"。

```
feishu_message_send_card(
  receive_id=<open_id>,                    # 私聊，不是 chat_id
  card_json=<和工具同一套模板：标题「理解确认」+ 三个按钮>,
  business_context_json={"request_type":"outreach_confirm","qa_id":"qa_<时间>_<hash8>",
                         "open_id":…,"user_hash":…,"topic":…,"keyword_hit":…,"answer_summary":…},
  action_handlers_json={"understood":"outreach_confirm",
                        "partial":"outreach_confirm","not_understood":"outreach_confirm"})
```

按钮的 `value.action` 必须是 `understood` / `partial` / `not_understood` 三者之一，
否则回调对不上 handler。发完卡把这次的 `qa_id` 写进该用户的 `last_qa`（否则回调会被
判为 stale card 而拒绝记录），然后**零文本结束**。

反复出现同一类 `bank_miss` 就把它补进 `outreach/qna_bank.yaml`——补库是长期解，
每次让模型现场组织答案不是。

### C. 卡片回调（点击）

1. 收到 `<feishu_card_action>` 立刻调 `outreach_confirm_handle(card_action_json=<整段 JSON>)`，
   不要先复述「你点了…」。
2. 工具内部已完成：校验 `qa_id`、记 `answers[]`、更新
   `confident_streak`/`confident_count`/`not_understood_count`/`familiarity_est`，
   并按回答发出预写的后续：

   | 回答 | 工具发出的内容 |
   |---|---|
   | ✅ 懂了 | 只发一句肯定 + 邀请：「很好！还有别的想问的吗？」**不发卡，也不推进下一节** |
   | 🤔 不太懂 | `re_explain`：换个角度重讲那一点（更简单的类比 + 海豚的真实例子）+ **一张新的确认卡** |
   | ❌ 没看懂 | `restart`：用最简单的话从头重讲这个节点，**绝不推进新材料** + **一张新的确认卡** |

   两条要点：
   - 新解释本身也是一个需要验证的说法，所以它自带确认卡——否则用户还是没懂时无从表达。
     新卡的 `qa_id` 会写进 `last_qa`，下一次点击校验的是它，旧卡自动作废。
   - 「懂了」不推进材料是刻意的：本场景是**反应式**的，下一个话题由用户自己决定。
     连续说不懂也**不会**被换成 probe question——刚说了两次没懂的人需要的是解释，不是考试。
3. **零文本结束**——卡片已经显示选了什么，后续消息也已发出。
   只有工具返回 `ok=false` 时才回复那条必要的错误。

## 策略与阈值

优先级 0→5，每轮只执行一条。1–5 的内容都来自答案库的预写字段，不要现场重写：

| # | 条件 | 动作 |
|---|------|------|
| 0 | 命中关键词 | 路径 A（0 LLM）；`bank_miss` → 路径 B |
| 1 | 回答「懂了」 | 一句肯定 + 邀请再问，结束本轮；**不推进下一节**（话题由用户定） |
| 2 | 回答「不太懂」 | `re_explain` 换个角度（更简单的类比 + 海豚的真实例子）+ 新确认卡 |
| 3 | 回答「没看懂」 | `restart` 用最简单的话从头重讲 + 新确认卡，**绝不**推进新内容 |
| 4 | 连续多次非「懂了」 | 仍然按 2/3 重讲——**不要**改成考问。反复讲不通才升到路径 B 重新组织表达 |
| 5 | `confident_count` ≥ `thresholds.confident_answers_needed` 且 `familiarity_est` ≥ `familiarity_done` | `stage = done`（工具自动写），可交接场景 1 |

`confident_count` 是自评，**必须**由 `probe_question` 的实际回答交叉验证，不能只凭用户说「懂了」。

## 禁止

- 不要改已发出的旧卡，不要为同一次问答发第二张卡（卡片默认单次消费）。
- 不要用 `on_behalf_of`——这些是机器人自己说的话。
- 不要在确定性路径已回答后再重复回答（见 A 的沉默规则），也不要输出 `NO_REPLY` 当占位。
- 不要手写 `next_send_at` 之类场景 1 的字段；场景 3 期间 `daily` 处于闲置。

完整参考：`outreach/README.md`。
