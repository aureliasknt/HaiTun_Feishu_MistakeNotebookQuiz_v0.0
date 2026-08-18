/** 飞书网页应用免登路径的浏览器侧行为。
 *
 * 为什么要真 DOM: 被测的东西**全都**是 window 上的东西 —— `window.h5sdk` / `window.tt`
 * 存不存在决定了走免登还是走授权码回跳, `window.location.origin` 决定请求打到哪。
 * 拿假对象在 node 环境里测, 测的就只是那些假对象本身。
 *
 * @vitest-environment jsdom
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { detectFeishuState, requestAuthCode, silentFeishuLogin } from './feishuIdentity'

type SdkOptions = {
  /** Fire `h5sdk.ready`? `false` models an SDK that loads but never comes up. */
  ready?: boolean
  /** Fire `h5sdk.error` instead of ready. */
  error?: boolean
  /** What `tt.requestAuthCode` yields; `null` means it calls `fail`. */
  code?: string | null
  /** Omit `tt.requestAuthCode` — an old SDK build. */
  withoutApi?: boolean
  /** Omit `h5sdk.config` — an SDK build that needs no signing step. */
  withoutConfig?: boolean
  /** Make `h5sdk.config` invoke `onFail` (bad signature, unregistered domain). */
  configFails?: boolean
}

/** Arguments the SDK's `config` was called with, for asserting the signing contract. */
let configCalls: Record<string, unknown>[] = []

function installSdk(opts: SdkOptions = {}) {
  const w = window as unknown as Record<string, unknown>
  let configured = false
  w.h5sdk = {
    // Real SDK behaviour: `ready` only fires once `config` has succeeded.
    config: opts.withoutConfig
      ? undefined
      : (args: Record<string, unknown>) => {
          configCalls.push(args)
          if (opts.configFails) {
            ;(args.onFail as ((e: unknown) => void) | undefined)?.(new Error('bad signature'))
            return
          }
          configured = true
          readyCbs.forEach((cb) => cb())
          readyCbs.length = 0
        },
    ready: (cb: () => void) => {
      if (opts.ready === false) return
      if (opts.withoutConfig || configured) cb()
      else readyCbs.push(cb)
    },
    error: (cb: (err: unknown) => void) => {
      if (opts.error) cb(new Error('sdk down'))
    },
  }
  w.tt = opts.withoutApi
    ? {}
    : {
        requestAuthCode: (args: {
          appId: string
          success?: (res: { code?: string }) => void
          fail?: (err: unknown) => void
        }) => {
          if (opts.code === null) args.fail?.(new Error('refused'))
          else args.success?.({ code: opts.code ?? 'auth-code-1' })
        },
      }
}

/** `ready` callbacks parked until `config` succeeds — mirrors the real SDK's ordering. */
const readyCbs: (() => void)[] = []

function clearSdk() {
  const w = window as unknown as Record<string, unknown>
  delete w.h5sdk
  delete w.tt
  readyCbs.length = 0
  configCalls = []
}

/** A signature the Gateway would hand back for the current page URL. */
const jsConfigOk = { app_id: 'cli_x', timestamp: 1737000000000, nonce_str: 'n0nce', signature: 'sha1hex' }

/**
 * `/feishu/app/me` answers, in call order.
 *
 * `jsConfig` models the signing endpoint: `null` = refused, which must degrade to the
 * redirect rather than a hang.
 */
function stubFetch(mePayloads: unknown[], jsLoginOk = true, jsConfig: unknown = jsConfigOk) {
  const calls: string[] = []
  const bodies: Record<string, string> = {}
  let meCall = 0
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method || 'GET'} ${url}`)
    if (typeof init?.body === 'string') bodies[url] = init.body
    if (url.endsWith('/feishu/app/js-config')) {
      if (!jsConfig) return { ok: false, json: async () => ({}) } as Response
      return { ok: true, json: async () => jsConfig } as Response
    }
    if (url.endsWith('/feishu/app/js-login')) {
      return { ok: jsLoginOk, json: async () => ({ ok: jsLoginOk }) } as Response
    }
    const body = mePayloads[Math.min(meCall++, mePayloads.length - 1)]
    return { ok: true, json: async () => body } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return Object.assign(calls, { bodies })
}

const unauthenticated = { authenticated: false, configured: true, app_id: 'cli_x' }
const authenticated = {
  authenticated: true,
  configured: true,
  app_id: 'cli_x',
  open_id: 'ou_1',
  session_id: 'sess-1',
  workspace: '/ws/sess-1',
  name: '张三',
  client: 'feishu',
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  clearSdk()
})

describe('detectFeishuState', () => {
  it('reports app_id so the page can call requestAuthCode', async () => {
    stubFetch([unauthenticated])
    const state = await detectFeishuState()
    expect(state.identity).toBeNull()
    expect(state.appId).toBe('cli_x')
    expect(state.configured).toBe(true)
  })

  it('treats a present JSSDK as the in-client signal even if the Gateway says browser', async () => {
    installSdk()
    stubFetch([{ ...unauthenticated, client: 'browser' }])
    expect((await detectFeishuState()).client).toBe('feishu')
  })

  it('falls back to desktop mode when the route is missing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: false, json: async () => ({}) }) as Response),
    )
    const state = await detectFeishuState()
    expect(state).toEqual({ identity: null, configured: false, client: 'browser', appId: '' })
  })
})

describe('requestAuthCode', () => {
  it('returns the code the SDK hands back', async () => {
    installSdk({ code: 'code-42' })
    stubFetch([unauthenticated])
    await expect(requestAuthCode('cli_x')).resolves.toBe('code-42')
  })

  it('signs the page before waiting on ready — ready never fires without config', async () => {
    // The regression this guards: calling `ready` with no `config` hangs inside the
    // Feishu client, which silently demoted the page to desktop mode.
    installSdk({ code: 'code-42' })
    const calls = stubFetch([unauthenticated])
    await expect(requestAuthCode('cli_x')).resolves.toBe('code-42')

    expect(calls).toContain('POST http://localhost:3000/feishu/app/js-config')
    expect(configCalls).toHaveLength(1)
    expect(configCalls[0]).toMatchObject({
      appId: 'cli_x',
      timestamp: 1737000000000,
      nonceStr: 'n0nce',
      signature: 'sha1hex',
    })
  })

  it('signs the current page URL with the fragment stripped', async () => {
    installSdk({ code: 'code-42' })
    const calls = stubFetch([unauthenticated])
    await requestAuthCode('cli_x')
    // A mismatched URL makes Feishu reject the signature, so this is the whole contract.
    const sent = JSON.parse(calls.bodies['http://localhost:3000/feishu/app/js-config'])
    expect(sent.url).toBe('http://localhost:3000/')
    expect(sent.url).not.toContain('#')
  })

  it('is empty when the Gateway will not sign, so the caller redirects', async () => {
    installSdk({ code: 'code-42' })
    stubFetch([unauthenticated], true, null)
    await expect(requestAuthCode('cli_x')).resolves.toBe('')
  })

  it('is empty when config itself fails (bad signature / unregistered domain)', async () => {
    installSdk({ code: 'code-42', configFails: true })
    stubFetch([unauthenticated])
    // onFail must resolve immediately rather than leaving the boot on the timeout.
    await expect(requestAuthCode('cli_x')).resolves.toBe('')
  })

  it('still works on an SDK build with no config step', async () => {
    installSdk({ code: 'code-42', withoutConfig: true })
    const calls = stubFetch([unauthenticated])
    await expect(requestAuthCode('cli_x')).resolves.toBe('code-42')
    expect(calls).not.toContain('POST http://localhost:3000/feishu/app/js-config')
  })

  it('is empty without an SDK, so the caller redirects instead of hanging', async () => {
    await expect(requestAuthCode('cli_x')).resolves.toBe('')
  })

  it('is empty when appId is unknown — requestAuthCode cannot work without it', async () => {
    installSdk()
    await expect(requestAuthCode('')).resolves.toBe('')
  })

  it('is empty when the SDK reports an error', async () => {
    installSdk({ ready: false, error: true })
    stubFetch([unauthenticated])
    await expect(requestAuthCode('cli_x')).resolves.toBe('')
  })

  it('is empty when requestAuthCode fails', async () => {
    installSdk({ code: null })
    stubFetch([unauthenticated])
    await expect(requestAuthCode('cli_x')).resolves.toBe('')
  })

  it('is empty on an SDK build without requestAuthCode', async () => {
    installSdk({ withoutApi: true })
    stubFetch([unauthenticated])
    await expect(requestAuthCode('cli_x')).resolves.toBe('')
  })

  it('gives up after the timeout when ready never fires', async () => {
    installSdk({ ready: false })
    stubFetch([unauthenticated])
    const pending = requestAuthCode('cli_x')
    await vi.advanceTimersByTimeAsync(4000)
    // A stalled SDK must cost seconds, not block boot forever.
    await expect(pending).resolves.toBe('')
  })
})

describe('silentFeishuLogin', () => {
  it('exchanges the code and re-reads the identity — no page transition', async () => {
    installSdk({ code: 'code-42' })
    const calls = stubFetch([unauthenticated, authenticated])
    const first = await detectFeishuState()

    const next = await silentFeishuLogin(first)
    expect(next?.identity).toEqual({
      openId: 'ou_1',
      sessionId: 'sess-1',
      workspace: '/ws/sess-1',
      name: '张三',
      client: 'feishu',
    })
    // Exactly one js-login; the other POST is the signing step config needs.
    expect(calls.filter((c) => c.endsWith('/feishu/app/js-login'))).toHaveLength(1)
  })

  it('is null when the Gateway refuses the code, so the caller can fall back', async () => {
    installSdk({ code: 'code-42' })
    stubFetch([unauthenticated], false)
    expect(await silentFeishuLogin(await detectFeishuState())).toBeNull()
  })

  it('is null when the exchange succeeds but no identity comes back', async () => {
    installSdk({ code: 'code-42' })
    stubFetch([unauthenticated, unauthenticated])
    expect(await silentFeishuLogin(await detectFeishuState())).toBeNull()
  })

  it('never posts a code when there is no SDK', async () => {
    const calls = stubFetch([unauthenticated])
    expect(await silentFeishuLogin(await detectFeishuState())).toBeNull()
    expect(calls.filter((c) => c.startsWith('POST'))).toHaveLength(0)
  })
})
