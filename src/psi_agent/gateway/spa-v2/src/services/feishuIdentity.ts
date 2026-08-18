/**
 * 飞书网页应用身份探测 —— 决定这次启动是「工作台模式」还是桌面模式。
 *
 * 桌面版让用户自己挑 workspace 目录; 飞书网页应用里不能这样: 用户没有本机路径可选, 而且必须
 * 看到**自己**那份任务与交付物。所以启动时先问 Gateway 一句 `GET /feishu/app/me`——命中身份
 * 就跳过目录选择, 直接落到与机器人**同一个** Session 上 (服务端走的是 `/feishu/route`,
 * 按 open_id 幂等)。
 *
 * 没有身份时怎么拿到身份, 分两条路:
 *
 * - **JSSDK 免登** (页面开在飞书客户端里): `tt.requestAuthCode` 要一个免登码, POST 给
 *   `/feishu/app/js-login` 由服务端兑成 open_id。整个过程没有跳转, 用户零点击。
 * - **授权码回跳** (普通浏览器, 或免登失败兜底): 整页跳去 `/feishu/app/login`。
 *
 * 免登优先, 因为客户端 webview 里整页跳走再跳回既慢又容易落到外部浏览器。
 *
 * 探测失败一律当作桌面模式: 旧 Gateway 没这条路由 (404), 或没配飞书凭据 (501)。因此这段代码
 * 对既有桌面流程是**零影响**的。
 */

/** Where the page is running. `feishu` = inside the Feishu/Lark client webview. */
export type FeishuClient = 'feishu' | 'browser'

export type FeishuIdentity = {
  openId: string
  /** Session bound to this Feishu user — the same one the bot talks to. */
  sessionId: string
  /** Workspace that Session owns; empty when the Gateway could not report it. */
  workspace: string
  /**
   * Display name from the Feishu profile, for the sidebar account row.
   *
   * May be empty — Feishu only returns a name when the app has the scope and the user
   * filled it in — so callers must keep their own fallback rather than showing a blank.
   */
  name: string
  client: FeishuClient
}

/**
 * Why this exists: one URL serves both 飞书网页应用 (2B) and 本地/桌面 Web 工作台 (2C),
 * and only the identity cookie tells them apart. When that cookie is missing the page
 * used to fall back to 2C **silently** — which is exactly what made 场景 3 look broken.
 * So an unauthenticated answer is a state to report, not just a `null`.
 */
export type FeishuState = {
  identity: FeishuIdentity | null
  /** Gateway has app credentials, so `/feishu/app/login` can actually work. */
  configured: boolean
  client: FeishuClient
  /** App ID the Gateway is configured with — what `tt.requestAuthCode` needs. */
  appId: string
}

type MeResponse = {
  authenticated?: boolean
  open_id?: string
  session_id?: string
  workspace?: string
  name?: string
  configured?: boolean
  client?: string
  app_id?: string
}

/**
 * The slice of the Feishu JSSDK this file uses.
 *
 * Only `requestAuthCode` — deliberately not `getUserInfo`. That one hands back an
 * identity the **page** asserts, which a tampered client could forge. The auth code is
 * opaque here and only the Gateway (holding `app_secret`) can redeem it, so `open_id`
 * still comes from Feishu answering our server.
 */
type FeishuJsSdk = {
  requestAuthCode?: (args: {
    appId: string
    success?: (res: { code?: string }) => void
    fail?: (err: unknown) => void
  }) => void
}

type FeishuH5Sdk = {
  /**
   * Authenticate this page with the SDK. **`ready` does not fire until this succeeds**,
   * which is why the signing round-trip is unavoidable even though we never call
   * `getUserInfo`.
   */
  config?: (args: {
    appId: string
    timestamp: number
    nonceStr: string
    signature: string
    jsApiList: string[]
    onSuccess?: (res: unknown) => void
    onFail?: (err: unknown) => void
  }) => void
  ready?: (cb: () => void) => void
  error?: (cb: (err: unknown) => void) => void
}

type JsConfigResponse = {
  app_id?: string
  timestamp?: number
  nonce_str?: string
  signature?: string
}

/**
 * Resolve the Feishu user behind this browser session.
 *
 * Returns `null` for "not a Feishu web app session" — unauthenticated, route absent,
 * credentials missing, or the Gateway unreachable. Callers treat `null` as desktop mode.
 */
function h5sdk(): FeishuH5Sdk | null {
  const w = window as unknown as { h5sdk?: FeishuH5Sdk }
  return w.h5sdk ?? null
}

function tt(): FeishuJsSdk | null {
  const w = window as unknown as { tt?: FeishuJsSdk }
  return w.tt ?? null
}

/** True when the Feishu/Lark JSSDK is present — the strongest in-client signal. */
function hasFeishuJsSdk(): boolean {
  return Boolean(h5sdk() || tt())
}

export async function detectFeishuState(): Promise<FeishuState> {
  // The client hint is also derived here: the JSSDK is a stronger signal than the
  // User-Agent the Gateway sees, so a positive local check wins.
  const localClient: FeishuClient = hasFeishuJsSdk() ? 'feishu' : 'browser'
  const unknown: FeishuState = {
    identity: null,
    configured: false,
    client: localClient,
    appId: '',
  }
  try {
    const origin = window.location.origin.replace(/\/+$/, '')
    const r = await fetch(origin + '/feishu/app/me', {
      // The identity cookie is HttpOnly, so it must ride along explicitly.
      credentials: 'same-origin',
    })
    if (!r.ok) return unknown
    const body = (await r.json()) as MeResponse
    const client: FeishuClient =
      localClient === 'feishu' || body.client === 'feishu' ? 'feishu' : 'browser'
    const configured = Boolean(body?.configured)
    const appId = (body.app_id || '').trim()
    if (!body?.authenticated) return { identity: null, configured, client, appId }
    const sessionId = (body.session_id || '').trim()
    const openId = (body.open_id || '').trim()
    // A bound session is the whole point; without one there is nothing to pin to.
    if (!sessionId || !openId) return { identity: null, configured, client, appId }
    return {
      identity: {
        openId,
        sessionId,
        workspace: (body.workspace || '').trim(),
        name: (body.name || '').trim(),
        client,
      },
      configured,
      client,
      appId,
    }
  } catch {
    // Route absent (old Gateway) or unreachable → plain desktop workbench.
    return unknown
  }
}

/** How long to wait on `h5sdk.ready` before falling back to the redirect hop. */
const SDK_READY_TIMEOUT_MS = 4000

/**
 * Fetch the `h5sdk.config` signature for **this exact page URL**.
 *
 * The URL is part of the signed string, so it must match the address bar verbatim
 * minus the `#` fragment — a mismatch makes `config` fail, and a failed `config` means
 * `ready` never fires at all.
 *
 * Resolves `null` on any refusal (credentials missing, Feishu unreachable); callers
 * then fall back to the redirect hop.
 */
export async function fetchJsConfig(): Promise<JsConfigResponse | null> {
  try {
    const origin = window.location.origin.replace(/\/+$/, '')
    const r = await fetch(origin + '/feishu/app/js-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ url: window.location.href.split('#')[0] }),
    })
    if (!r.ok) return null
    const body = (await r.json()) as JsConfigResponse
    if (!body?.signature || !body.nonce_str || !body.timestamp) return null
    return body
  } catch {
    return null
  }
}

/**
 * Ask the JSSDK for a one-time auth code.
 *
 * Two steps, in this order: `config` authenticates the page, and only then does `ready`
 * fire. Skipping `config` is why this used to hang until the timeout inside the Feishu
 * client — `ready` was waiting on an authentication that never happened.
 *
 * Resolves `''` for every "can't do it here" case — no SDK, no signature, `ready` never
 * fires, the call fails. Callers treat that as "fall back to the redirect", so a stalled
 * SDK costs a few seconds rather than hanging the boot forever.
 */
export async function requestAuthCode(appId: string): Promise<string> {
  const sdk = h5sdk()
  if (!appId || !sdk?.ready) return ''
  // `config` is required for `ready`; without a usable signature there is nothing to
  // wait for, so bail before arming the timer.
  const config = sdk.config ? await fetchJsConfig() : null
  if (sdk.config && !config) return ''
  return new Promise<string>((resolve) => {
    let settled = false
    const done = (code: string) => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      resolve(code)
    }
    const timer = window.setTimeout(() => done(''), SDK_READY_TIMEOUT_MS)
    try {
      // `error` fires when the SDK itself fails to come up; without it a broken SDK
      // would only surface as the timeout above.
      sdk.error?.(() => done(''))
      sdk.ready?.(() => {
        const api = tt()
        if (!api?.requestAuthCode) {
          done('')
          return
        }
        api.requestAuthCode({
          appId,
          success: (res) => done((res?.code || '').trim()),
          fail: () => done(''),
        })
      })
      if (sdk.config && config) {
        sdk.config({
          appId: config.app_id || appId,
          timestamp: Number(config.timestamp),
          nonceStr: config.nonce_str || '',
          signature: config.signature || '',
          // Empty on purpose: `requestAuthCode` is not a gated JSAPI, so nothing needs
          // declaring here. `config` is called for its authentication effect alone.
          jsApiList: [],
          onFail: () => done(''),
        })
      }
    } catch {
      done('')
    }
  })
}

/**
 * Trade an auth code for the identity cookie. Returns whether it stuck.
 *
 * The response body is ignored on purpose: `open_id` / `session_id` come from the
 * follow-up `/feishu/app/me`, so there is exactly one place that decides who you are.
 */
export async function jsLogin(code: string): Promise<boolean> {
  if (!code) return false
  try {
    const origin = window.location.origin.replace(/\/+$/, '')
    const r = await fetch(origin + '/feishu/app/js-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ code }),
    })
    return r.ok
  } catch {
    return false
  }
}

/**
 * In-client sign-in with no page transition: auth code → cookie → fresh `/me`.
 *
 * Returns `null` when the SDK route is unavailable or the exchange is refused; the
 * caller then falls back to `loginUrl()`.
 */
export async function silentFeishuLogin(state: FeishuState): Promise<FeishuState | null> {
  const code = await requestAuthCode(state.appId)
  if (!code) return null
  if (!(await jsLogin(code))) return null
  const next = await detectFeishuState()
  return next.identity ? next : null
}

/** Start the OAuth hop; Feishu returns the browser to the workbench when done. */
export function loginUrl(): string {
  return window.location.origin.replace(/\/+$/, '') + '/feishu/app/login'
}
