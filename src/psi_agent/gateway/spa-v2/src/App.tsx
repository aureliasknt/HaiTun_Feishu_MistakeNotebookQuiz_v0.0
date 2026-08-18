import { useCallback, useEffect, useState } from 'react'
import WorkspaceGate, { type PathPickKind } from './components/WorkspaceGate'
import {
  detectFeishuState,
  loginUrl,
  silentFeishuLogin,
  type FeishuClient,
  type FeishuIdentity,
} from './services/feishuIdentity'
import { enableWorkbenchSurface } from './haitun-agent/uiSurface'
import HaiTunAgentWorkspace from './haitun-agent/HaiTunAgentWorkspace'
import { browseWorkspace, fetchDefaults } from './services/api'
import { BrandLogo } from './haitun-agent/primitives'

const LS_WORKSPACE = 'gw-v2-workspace'
const LS_AGENT = 'gw-v2-agent'

/** Paths that were agent packages, not user workspaces — treat as unset. */
function isLegacyWorkspacePath(path: string): boolean {
  const n = path.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
  if (!n || n === 'workspace') return true
  // Old examples/*-workspace layout (agent pack mistaken for open-folder)
  if (/\/examples\/[^/]+-workspace$/i.test(n)) return true
  if (n.endsWith('/haitun-workspace')) return true
  return false
}

function readSavedWorkspace(): string {
  try {
    const raw = window.localStorage.getItem(LS_WORKSPACE)?.trim() || ''
    if (isLegacyWorkspacePath(raw)) return ''
    return raw
  } catch {
    return ''
  }
}

function readSavedAgent(): string {
  try {
    return window.localStorage.getItem(LS_AGENT)?.trim() || ''
  } catch {
    return ''
  }
}

function writeSavedAgent(path: string) {
  try {
    const clean = path.trim()
    if (clean) window.localStorage.setItem(LS_AGENT, clean)
    else window.localStorage.removeItem(LS_AGENT)
  } catch {
    /* ignore quota */
  }
}

async function pathExistsAsDir(path: string): Promise<boolean> {
  try {
    await browseWorkspace(path, { kind: 'directory' })
    return true
  } catch {
    return false
  }
}

/**
 * spa-v2 root:
 * - Boot from GET /defaults (+ localStorage overrides for workspace / agent).
 * - Pass agent into POST /sessions via HaiTunAgentWorkspace.
 * - Settings can switch workspace or agent package (same PathPicker flow).
 */
export default function App() {
  const [workspace, setWorkspace] = useState('')
  const [defaultAgent, setDefaultAgent] = useState('')
  const [bootstrapping, setBootstrapping] = useState(true)
  const [pickingKind, setPickingKind] = useState<PathPickKind | null>(null)
  const [feishu, setFeishu] = useState<FeishuIdentity | null>(null)
  /** Where the page is running — shown as a badge so the active mode is never a guess. */
  const [feishuClient, setFeishuClient] = useState<FeishuClient>('browser')

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        // 飞书网页应用优先: 命中身份就不再问用户要目录 —— 工作台里没有本机路径可选, 而且
        // 必须落到与机器人同一个 Session (服务端按 open_id 幂等路由)。
        let state = await detectFeishuState()
        if (cancelled) return
        setFeishuClient(state.client)
        // 页面开在飞书客户端里却没有身份 → 就地拿身份。留在桌面模式只会让用户以为
        // 场景 3 坏了 (卡与题库答案全都被 feishuSessionId 的门挡住), 而不是「没登录」。
        if (!state.identity && state.client === 'feishu' && state.configured) {
          // 先试 JSSDK 免登: 客户端里这一步无跳转、零点击。失败 (没 SDK / 兑码被拒) 才整页
          // 跳授权 —— 那在 webview 里既慢又偶尔落到外部浏览器, 所以只当兜底。
          const silent = await silentFeishuLogin(state)
          if (cancelled) return
          if (silent) {
            state = silent
            setFeishuClient(silent.client)
          } else {
            window.location.replace(loginUrl())
            return
          }
        }
        const identity = state.identity
        if (identity) {
          // 必须在首帧之前: 交接文档要求工作台有「任务总览 / 历史任务列表」。
          enableWorkbenchSurface()
          setFeishu(identity)
          setWorkspace(identity.workspace)
          setBootstrapping(false)
          setPickingKind(null)
          return
        }

        const d = await fetchDefaults()
        if (cancelled) return

        const savedAgent = readSavedAgent()
        let agent = ''
        if (savedAgent && (await pathExistsAsDir(savedAgent))) {
          agent = savedAgent
        } else if ((d.agent || '').trim()) {
          agent = d.agent.trim()
          if (savedAgent && savedAgent !== agent) writeSavedAgent('')
        }
        if (!cancelled) setDefaultAgent(agent)

        const fromDefaults = (d.workspace || '').trim()
        const saved = readSavedWorkspace()
        let chosen = ''
        if (saved && (await pathExistsAsDir(saved))) {
          chosen = saved
        } else if (fromDefaults && (await pathExistsAsDir(fromDefaults))) {
          chosen = fromDefaults
        } else if (fromDefaults) {
          chosen = fromDefaults
        }
        if (cancelled) return
        if (saved && saved !== chosen) {
          try {
            if (chosen) window.localStorage.setItem(LS_WORKSPACE, chosen)
            else window.localStorage.removeItem(LS_WORKSPACE)
          } catch {
            /* ignore */
          }
        }
        if (chosen) {
          setWorkspace(chosen)
          setBootstrapping(false)
          setPickingKind(null)
          return
        }
        setBootstrapping(false)
        setPickingKind('workspace')
      } catch {
        if (cancelled) return
        setBootstrapping(false)
        setPickingKind('workspace')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const readyWorkspace = useCallback((path: string) => {
    const clean = path.trim()
    try {
      window.localStorage.setItem(LS_WORKSPACE, clean)
    } catch {
      /* ignore quota */
    }
    setWorkspace(clean)
    setPickingKind(null)
    setBootstrapping(false)
  }, [])

  const readyAgent = useCallback((path: string) => {
    const clean = path.trim()
    writeSavedAgent(clean)
    setDefaultAgent(clean)
    setPickingKind(null)
  }, [])

  const changeWorkspace = useCallback(() => {
    setPickingKind('workspace')
  }, [])

  const changeAgent = useCallback(() => {
    setPickingKind('agent')
  }, [])

  if (bootstrapping) {
    return (
      <div className="workspace-gate" aria-busy="true">
        <div className="workspace-gate-card">
          <BrandLogo size="hero" />
          <p>正在连接 Gateway…</p>
        </div>
      </div>
    )
  }

  // 飞书用户永远不该看到本机目录选择器: 他们的 workspace 由 open_id 决定, 不由手选决定。
  if (pickingKind === 'workspace' && !feishu) {
    return (
      <WorkspaceGate
        kind="workspace"
        initialPath={workspace}
        onReady={readyWorkspace}
        onCancel={workspace ? () => setPickingKind(null) : undefined}
      />
    )
  }

  if (pickingKind === 'agent') {
    return (
      <WorkspaceGate
        kind="agent"
        initialPath={defaultAgent}
        onReady={readyAgent}
        onCancel={() => setPickingKind(null)}
      />
    )
  }

  return (
    <HaiTunAgentWorkspace
      key={feishu ? `feishu:${feishu.sessionId}` : workspace}
      workspace={workspace}
      defaultAgent={defaultAgent}
      // 两个 prop 分工不同: `feishuMode` 决定「这是工作台」(隐藏目录切换、打开总览),
      // `feishuBotSessionId` 只用来把机器人那张卡从任务列表里摘掉。此前是同一个值,
      // 于是新建任务只能复用机器人那条 Session, 两边对话因此混在一起。
      feishuMode={Boolean(feishu)}
      feishuBotSessionId={feishu?.sessionId ?? ''}
      feishuClient={feishuClient}
      feishuUserName={feishu?.name ?? ''}
      // 工作台模式下不给切换入口: 目录由 open_id 决定, 手选只会切错人的数据。
      onChangeWorkspace={feishu ? undefined : changeWorkspace}
      onChangeAgent={feishu ? undefined : changeAgent}
    />
  )
}
