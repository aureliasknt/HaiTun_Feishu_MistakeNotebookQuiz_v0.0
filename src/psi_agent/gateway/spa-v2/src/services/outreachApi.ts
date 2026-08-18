/**
 * 场景 3 的理解确认卡在工作台里的两个调用 —— 取待确认卡、作答。
 *
 * 提问**不**从这里走: 场景 3 的问答由机器人私聊那一轮的模型完成 (它答完自己调
 * ``outreach_confirm_card`` 发卡), 页面只负责显示与答完那张卡。曾经有一个
 * ``askLiteracyQuestion``, 它调 ``POST /outreach/ask`` 去触发一条零大模型的确定性
 * 发卡链路 —— 那条链路已整体移除, 该端点也随之下线。
 *
 * 身份**不**在这里传: ``open_id`` 由 Gateway 从 HttpOnly cookie 解析 (见
 * ``_outreach_api``), 所以页面无法替别人作答。因此每个请求都必须带
 * ``credentials: 'same-origin'``。
 */

const G = () => window.location.origin.replace(/\/+$/, '')

export type PendingCard = {
  qaId: string
  /** The one line the card shows, e.g.「这次讲清楚了吗？」— server-owned, so both surfaces match. */
  prompt: string
  keyword: string
  topic: string
}

export type CardAnswer = 'understood' | 'partial' | 'not_understood'

type CardResponse = {
  available?: boolean
  qa_id?: string
  prompt?: string
  keyword?: string
  topic?: string
}

export type AnswerResult = {
  ok: boolean
  graduated: boolean
  /** Closing line to show after the answer lands; may be empty. */
  closing: string
}

/** The card awaiting this user's confirmation, or `null` when there is none. */
export async function fetchPendingCard(): Promise<PendingCard | null> {
  try {
    const r = await fetch(G() + '/outreach/card', { credentials: 'same-origin' })
    if (!r.ok) return null
    const body = (await r.json()) as CardResponse
    if (!body?.available || !body.qa_id) return null
    return {
      qaId: body.qa_id,
      // Falling back to the same wording as the server keeps an older Gateway from
      // rendering a card with no question on it.
      prompt: body.prompt || '这次讲清楚了吗？',
      keyword: body.keyword || '',
      topic: body.topic || '',
    }
  } catch {
    return null
  }
}

/**
 * Record one self-assessment.
 *
 * Throws on refusal (409 for a stale or already-answered `qa_id`) so the card can
 * tell the user why nothing happened instead of silently looking answered.
 */
export async function answerPendingCard(qaId: string, answer: CardAnswer): Promise<AnswerResult> {
  const r = await fetch(G() + '/outreach/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ qa_id: qaId, answer }),
  })
  const body = (await r.json().catch(() => ({}))) as { error?: string; graduated?: boolean; closing?: string }
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`)
  return { ok: true, graduated: Boolean(body.graduated), closing: body.closing || '' }
}
