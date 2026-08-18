import { describe, expect, it } from 'vitest'
import { isVisibleWorkbenchSession, withoutBotSession } from './feishuSessions'

const BOT = 'feishu-ou_alice'
const WEB = 'feishu-ou_alice-web-0123456789ab'

describe('isVisibleWorkbenchSession', () => {
  it('hides the bot session so the DM does not leak into the workbench', () => {
    expect(isVisibleWorkbenchSession(BOT, BOT)).toBe(false)
  })

  it('keeps sessions the web app created in the same workspace', () => {
    expect(isVisibleWorkbenchSession(WEB, BOT)).toBe(true)
  })

  it('shows everything in desktop mode (no identity, nothing to hide)', () => {
    expect(isVisibleWorkbenchSession(BOT, '')).toBe(true)
    expect(isVisibleWorkbenchSession(WEB, '')).toBe(true)
  })

  it('matches the bot id verbatim rather than by shape', () => {
    // Another user's bot session must not be hidden by a pattern guess — and a
    // prefix match would wrongly hide every web session too.
    expect(isVisibleWorkbenchSession('feishu-ou_bob', BOT)).toBe(true)
    expect(isVisibleWorkbenchSession('spa-built-session', BOT)).toBe(true)
  })
})

describe('withoutBotSession', () => {
  const sessions = [{ id: BOT }, { id: WEB }, { id: 'feishu-ou_alice-web-cafebabe1234' }]

  it('drops only the bot card and preserves order', () => {
    expect(withoutBotSession(sessions, BOT).map((s) => s.id)).toEqual([
      WEB,
      'feishu-ou_alice-web-cafebabe1234',
    ])
  })

  it('is a copy, never the same array (callers index into it)', () => {
    const out = withoutBotSession(sessions, '')
    expect(out).not.toBe(sessions)
    expect(out.map((s) => s.id)).toEqual(sessions.map((s) => s.id))
  })

  it('can empty the list when the bot session is the only one', () => {
    expect(withoutBotSession([{ id: BOT }], BOT)).toEqual([])
  })
})
