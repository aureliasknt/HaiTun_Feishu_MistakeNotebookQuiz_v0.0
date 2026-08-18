/**
 * spa-v2 interaction surface flags.
 *
 * **赶工临时 / 刻意为之**：总览卡、模板库的组件 / fixture / 状态保留，仅从主导航与
 * 卡片栈暂时摘掉，方便一键恢复。改回 ``true`` 即还原旧交互。
 *
 * 飞书网页应用 (工作台) 是例外：交接文档明确要求「任务总览（当前任务摘要、历史任务列表）」
 * 与「用户可在此查看长期状态、追溯历史」，所以 ``enableWorkbenchSurface()`` 会在工作台模式
 * 启动时把它打开。因为是 ES 模块的 live binding，30 余处 import 处会一并看到新值——前提是
 * **首帧之前**设置 (``App.tsx`` 在 boot effect 里、``setBootstrapping(false)`` 之前调用)。
 *
 * 注意：这面旗子同时管着总览卡和模板库，打开工作台模式也会把 ``模板库`` 一起带回来。
 */
export let SHOW_OVERVIEW_AND_TEMPLATES = false

/** 工作台模式：打开总览卡 (与模板库)。仅在首帧前调用。 */
export function enableWorkbenchSurface(): void {
  SHOW_OVERVIEW_AND_TEMPLATES = true
}

/** Map a task list index → card-stack index (accounts for optional overview at 0). */
export function cardIndexForTask(taskIndex: number): number {
  return SHOW_OVERVIEW_AND_TEMPLATES ? taskIndex + 1 : taskIndex
}

/** Task at a card-stack index, or ``null`` when the slot is the overview card. */
export function taskAtCardIndex<T>(tasks: readonly T[], cardIndex: number): T | null {
  if (SHOW_OVERVIEW_AND_TEMPLATES) {
    if (cardIndex <= 0) return null
    return tasks[cardIndex - 1] ?? null
  }
  return tasks[cardIndex] ?? null
}
