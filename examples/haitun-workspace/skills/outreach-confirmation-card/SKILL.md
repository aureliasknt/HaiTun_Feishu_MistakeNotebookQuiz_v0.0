---
name: outreach-confirmation-card
description: "Use for the agent-literacy campaign (Scenario 3): when a target user asks about agent/LLM/HaiTun topics, when a <feishu_card_action> arrives with handler outreach_confirm, or when the controller @-mentions people to enroll/pause/resume them in the campaign — 加进科普名单/加进 outreach 名单/别再发给他了/暂停某人/恢复某人. Covers answering as the reader's own profession, sending the 理解确认卡 with outreach_confirm_card, the click callback, enrolling targets with outreach_target_add, and pausing them with outreach_target_pause. NOT for adding somebody to a Feishu group chat (拉人进群) — that is feishu-chat; see 「名单 vs 群」 below when the ask is ambiguous."
category: productivity
agent_editable: true
---

# 理解确认卡（场景 3：反应式问答）

目标用户每问一次智能体/海豚相关的问题，就**你亲自回答** + 发一张**理解确认卡**：一行
「这次讲清楚了吗？」加三个按钮（✅ 懂了 / 🤔 不太懂 / ❌ 没看懂），卡面只有这些。
卡片的回答被记入状态，用来决定下一步教什么，并作为交接场景 1、场景 2 的基线。

## When to use

- 目标用户（`outreach/state.yaml` 的 `users`）私聊问到智能体/大模型/海豚等话题。
- 收到 `<feishu_card_action>`，且 `dispatch.handler` 为 `outreach_confirm`。
- 控制人 @ 了几个人、要求把他们加进名单 → 见「用 @ 把人加进名单」。
- 控制人要求对某人停发 / 重新开始 → 见「暂停 / 恢复某个人」。

## When not to use

- 提问者不在 `users` 名单里 → 当普通问答正常回答，不发卡、不写状态。
- 群聊里的提问 → 正常回答即可。卡片和答案都发往 `open_id`（私聊），发到群里会答错地方。
- 场景 1 的每日推送（那是 `outreach-daily-send`，`fire=prompt`）。

## 回答（你来写）

命中关键词时，系统提示里会多出两块内容，都是**读文件生成的，没有任何模型调用**：

- `## 讲解对象` —— 对方的职业与相应的讲法策略（默认是**法务专员**）。
- `<literacy_grounding>` —— 该关键词对应的课程原文：要点、参考讲法、换个角度、最简讲法，
  以及本轮该不该出检验题。

**这两块的用法是不对称的：**

| 块 | 怎么用 |
|---|---|
| `## 讲解对象` | **照做。** 它决定用词与类比 —— 对方读的是权责与后果，不是架构 |
| `<literacy_grounding>` | **取材，不照抄。** 它是事实来源，措辞由你按上面的策略重组 |

照抄原文是这里最容易犯的错：那些句子是写给一般读者的，直接发出去等于把「讲对了」
和「讲进去了」当成一回事。

其余仍按 supervisor advice 的 `response_strategy` 与画像控制深度；用户当前消息里
明确的范围要求优先。**不要**为了找材料去调 `wiki_read`：`agent-basics` 那几页不在
本能力包里，课程原文已经在上面那个块里了。

写完答案就发卡：

```
outreach_confirm_card(open_id=<提问者 open_id>,
                      topic=<grounding 里的 topic，如 what-is-an-agent>,
                      keyword=<命中的关键词>,
                      summary=<一句话概括你刚讲的内容>,
                      question=<用户这次的原话>)
```

`question` 要给：`answers[]` 拿它和自评一起存档，那是「他到底在评价哪个问题」的唯一凭据。
重讲那张卡沿用**原来那个问题**，不要写成「用户说不太懂」——被确认的还是同一个问题。

**不要自己拼卡片 JSON。** 卡面、三个按钮的取值、`qa_id`、`business_context`、
`action_handlers` 全由这个工具生成 —— 手写只要错一个字段，卡片看起来正常，点下去却
找不到 handler。工具已经把 `qa_id` 写进 `last_qa`，旧卡随之作废。

检验题跟着**答案那条消息**走（`顺手检验一下：…`），不上卡：开放题不是三个按钮能回答的，
而且它得和被检验的那段答案一起读。

发完卡**零文本结束**。只有工具返回 `ok=false` 时才回复那条必要的错误。

## 卡片回调（点击）

1. 收到 `<feishu_card_action>` 立刻调 `outreach_confirm_handle(card_action_json=<整段 JSON>)`，
   不要先复述「你点了…」。
2. 工具**只落库**：校验 `qa_id`、记 `answers[]`、更新
   `confident_streak`/`confident_count`/`not_understood_count`/`familiarity_est`、判定过关。
   它**不发任何消息** —— 这一条回复由你写。返回值里 `next_step` 是本轮该做的事，
   `send_new_card` 说明要不要补发新卡。

3. 按点的那个按钮写回复。这一轮的系统提示里有 `<card_click_response>`，
   连同被重讲那一点的课程原文一起：

   | 回答 | 你要做的事 | 新卡 |
   |---|---|---|
   | ❌ 没看懂 | **从最简单的形式重新讲**这同一点：最基础的说法、更短的句子、一次只讲一件事。不引入新材料，也不考问 | 要 |
   | 🤔 不太懂 | **换个角度重讲**这同一点：换一个不同的类比或例子（**不要重复刚才用过的那个**），落到对方职业的具体场景上。不引入新材料，也不考问 | 要 |
   | ✅ 懂了 | 一句真诚的肯定（别浮夸）→ 从 `next_step` 给的候选里挑 2-3 个**新话题**，每个一句话说明为什么和他相关 → 最后问一句还有没有其他问题 | 不要 |

   三条要点：
   - **重讲要真的不一样。** 「不太懂」的意思是上一个讲法没成功，把同样的话再说一遍
     没有任何用；换类比、换切入点、换例子。
   - **重讲完必须补卡**（`send_new_card` 为 `true` 时调 `outreach_confirm_card`）。
     新解释本身也是一个需要验证的说法，否则用户还是没懂时无从表达。新卡的 `qa_id` 会
     写进 `last_qa`，下一次点击校验的是它，旧卡自动作废。新卡与第一张**长得一样**；
     哪一次点击算哪一轮，认的是 `qa_id`，不是卡面文字。
   - **「懂了」不发卡、不擅自开讲下一个话题。** 本场景是**反应式**的：你只把新话题
     摆出来让他挑，讲什么由他决定。连续说不懂也**不要**改成考问——刚说了两次没懂的人
     需要的是解释，不是考试。

4. 工具返回 `ok=false` 时（过期卡、重复提交），只回那条必要的说明，不要重讲。

## 名单 vs 群（先分清再动手）

「把 @张三 加进来」**字面上有两种合理读法**：加进科普名单（本能力包），还是拉进某个飞书群
（`feishu-chat` 的「拉人进群」）。这两件事后果完全不同——一个让人开始每天收到私聊，一个把人
拉进一个群——所以**别靠猜**。

| 线索 | 判定 |
|---|---|
| 提到 名单 / 科普 / 智能体 / outreach / 场景三 / 目标用户 | 本能力包：`outreach_target_add` |
| 提到 群 / 群聊 / 拉进群 / 某个具体群名，或给了 `oc_...` | `feishu-chat`，**不是**这里 |
| 说的是「别再发给他了」「停一停」「暂停」 | 本能力包：`outreach_target_pause` |
| 说的是「踢出群」「移出群」 | `feishu-chat` |
| **两种都说得通、没有任何上述线索** | **反问一句**，见下 |

没有线索时**必须反问**，一句话就够：

> 你是要把他加进智能体科普名单（之后每天会收到推送），还是拉进某个群？

反问一次远好过猜错：猜成名单 = 一个无关同事开始收到机器人私聊；猜成群 = 该进名单的人没进，
控制人以为已经加好了。两种错都要人事后收拾，而问一句只花一轮。

注意**私聊里没有可拉的群**——DM 的 `chat_id` 是这次私聊本身，把它当群去拉人是错的。所以私聊里
的「加进来」偏向名单，但"偏向"不等于确定：仍然按上表判，缺线索就问。

## 用 @ 把人加进名单

控制人（`controller_open_id`）@ 几个人说「把 @张三 加进来」时，用
`outreach_target_add` 写名单，不要手改 `outreach/state.yaml`。

```
outreach_target_add(open_ids=[<mentions 里的 open_id>],
                    caller_open_id=<sender_open_id>,
                    names=[<mentions 里的名字，按顺序对应>])
```

**`open_id` 只能取自 `<feishu_context>` 的 `mentions:` 行。** 正文里的 `@张三` 是
**显示名**——lark 已把 `@_user_N` 占位符换成了名字，id 在渲染中彻底消失，而同名同事
不止一个。按名字猜 id 就是加错人，而加错人意味着一个无关的同事开始每天收到机器人私聊。

几条必须照做的：

- `caller_open_id` 传 `sender_open_id`。少了它工具直接拒（无从鉴权），别自己编。
- 控制人 @ 机器人只是在叫你办事，**把机器人自己的 open_id 从名单里剔掉**——那是寻址，
  不是目标。
- 报 `not_authorized` / `not_configured` 就如实转达并停手，不要换个说法重试：
  前者是「你没这个权限」，后者是「还没设 `controller_open_id`，谁都不能加」。
- 加完**什么都不会发给对方**，这是对的。场景 3 要等他自己在私聊里问起智能体才启动，
  场景 1 则在下一次每日推送时带上他。**把这句告诉控制人**，否则他会把这份安静当成失败。
- 已经在名单里的人会回 `already_a_target`，进度原样保留——不用回避重复添加。

## 暂停 / 恢复某个人

控制人说「先别再发给 @张三 了」用 `outreach_target_pause`；说「可以继续发了」同一个
工具传 `paused=false`。

```
outreach_target_pause(open_ids=[<mentions 里的 open_id>],
                      caller_open_id=<sender_open_id>,
                      paused=True)
```

`open_id` 的来源规则与添加时**完全一致**：只取 `mentions:` 行，不看正文里的名字。

- **暂停会保留全部进度**：`answers[]`、`card_sent_count`、`familiarity_est` 一个不动，
  恢复后从原处继续。所以想让某人停下来，**用暂停，不要把他从名单里删掉**——删除会连同
  几周积累的学习记录一起消失，且不可恢复。
- 两个场景同时停：不再有 grounding、不再发卡、每日推送也跳过他。**连暂停前就已经在屏幕上
  的那张卡，点了也不会再继续教**。
- 恢复方向同样要控制人权限（恢复等于重新开始给人发私聊），报 `not_authorized` 就转达并停手。
- **对方不会收到任何通知**，别对控制人说「已经告知他了」。
- 已经是该状态会回 `already_paused` / `already_active`，什么都没写，不必回避重复操作。

`stage: done` 不是暂停（那只是可交接的标记，过关的人再问还是照样讲、照样发卡），
`scenario3.enabled: false` 是全局关停，不针对某个人。

## 让人不觉得在等

- **先出结论，再展开。** 回答是流式送达的，所以第一句就该是那个定义或结论；
  「让我想想」「这是个好问题」之类的开场把真正的内容推到了后面。
- **答案先行，卡片最后。** 卡是对已读内容的追问，先发卡等于让人对着按钮等文字。
- 不要在答案里预告「我接下来会讲三点」再重讲一遍那三点——说一次就够。

## 阈值

| # | 条件 | 动作 |
|---|------|------|
| 1 | 回答「懂了」 | 你写：肯定 + 几个新话题 + 还有没有别的问题；**不发卡、不推进下一节**（话题由用户定） |
| 2 | 回答「不太懂」 | 你写：换个类比/例子重讲同一点 + 新确认卡 |
| 3 | 回答「没看懂」 | 你写：用最简单的话从头重讲同一点 + 新确认卡，**绝不**推进新内容 |
| 4 | 连续多次非「懂了」 | 仍然按 2/3 重讲，每次换新讲法——**不要**改成考问 |
| 5 | `confident_count` ≥ `thresholds.confident_answers_needed` 且 `familiarity_est` ≥ `familiarity_done` | `stage = done`（工具自动写），可交接场景 1 |

`confident_count` 是自评，**必须**由 `probe_question` 的实际回答交叉验证，不能只凭用户说「懂了」。

## 禁止

- 不要自己拼确认卡的 JSON——一律用 `outreach_confirm_card`。
- 不要照抄 `<literacy_grounding>` 的原文当答案。
- 不要改已发出的旧卡，不要为同一次问答发第二张卡（卡片默认单次消费）。
- 不要用 `on_behalf_of`——这些是机器人自己说的话。
- 不要用 `NO_REPLY` 回避回答。**这一轮就是回答的那一轮**：以前有一条确定性链路会在
  毫秒内替你答完，那时后台这一轮必须闭嘴；那条链路已经移除，你保持沉默就没有人回答了。
  `NO_REPLY` 只用于真正无话可说的场合，也不要拿它当占位符。
- 不要手写 `next_send_at` 之类场景 1 的字段；场景 3 期间 `daily` 处于闲置。

完整参考：`outreach/README.md`。
