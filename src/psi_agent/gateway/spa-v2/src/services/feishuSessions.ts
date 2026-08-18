/**
 * 飞书工作台的会话可见性 —— 哪些 Session 该出现在任务列表里。
 *
 * 工作台与机器人共用**一个 workspace** (用户画像 / llm_wiki / Supervisor / 交付物因此共享),
 * 但**不共用对话**: 页面新建的每个任务都是一条独立 Session, 历史按 session_id 存, 于是机器人
 * 私聊里说的话不会流进网页任务, 反之亦然。
 *
 * 唯一的例外是机器人那条会话本身 —— 它和网页任务落在同一个 workspace 下, 所以
 * `sessionMatchesWorkspace` 会把它一并捞出来。它必须被摘掉: 留着就等于把私聊逐字搬进工作台
 * (用户明确不要两边混在一起), 而且那张卡还带着一份**不该**从这里删的历史。
 *
 * 判定用**逐字比对 open_id 派生出的那个 id**, 而不是「看起来像不像机器人会话」的模式匹配:
 * 前者由服务端 `/feishu/app/me` 给出, 只可能命中一条; 后者会随命名规则漂移, 一旦误判就会把
 * 用户自己的任务藏起来。
 */

/** 机器人那条会话的 id (来自 `/feishu/app/me` 的 `session_id`), 桌面模式下为空。 */
export type BotSessionId = string

/**
 * 该 Session 该出现在工作台的任务列表里吗。
 *
 * `botSessionId` 为空 (桌面模式, 或 Gateway 没报) 时一律放行 —— 没有身份就没有要藏的东西,
 * 桌面流程因此零影响。
 */
export function isVisibleWorkbenchSession(
  sessionId: string,
  botSessionId: BotSessionId,
): boolean {
  if (!botSessionId) return true
  return sessionId !== botSessionId
}

/** 摘掉机器人那条会话后的列表; 顺序保持不变 (调用方按它算卡片下标)。 */
export function withoutBotSession<T extends { id: string }>(
  sessions: readonly T[],
  botSessionId: BotSessionId,
): T[] {
  if (!botSessionId) return [...sessions]
  return sessions.filter((s) => isVisibleWorkbenchSession(s.id, botSessionId))
}
