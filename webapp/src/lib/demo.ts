// Demo mode (VITE_DEMO=1): an in-memory league that implements `Api`, so the
// UI can be developed, reviewed and screenshotted without a Supabase project.
// The data is synthetic; the rules (credited touches, fantasy rules,
// privacy tiers) mirror the SQL so the pages behave like production.
import type { Api } from './api'
import type {
  ActionName, ActionRow, BoxRow, FantasyRule, LeaderRow, Match, PointRow, Participant, Player,
  PlayerProfile, Profile, Publication, Ruleset, Session, Slot, Team,
} from './types'

const SLOTS: Slot[] = ['P1A', 'P2A', 'P1B', 'P2B']
const ME = '00000000-0000-0000-0000-0000000000a1'

function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 2 ** 32
  }
}

const G1: Omit<FantasyRule, 'ruleset_id'>[] = [
  { rule_key: 'kill', label: 'Kill', actions: ['spike', 'overpass'], outcome: 'kill', assist_only: false, points: 1, sort_order: 10 },
  { rule_key: 'ace', label: 'Ace', actions: ['serve'], outcome: 'ace', assist_only: false, points: 1, sort_order: 20 },
  { rule_key: 'dig', label: 'Dig', actions: ['dig'], outcome: null, assist_only: false, points: 1, sort_order: 30 },
  { rule_key: 'assist', label: 'Assist', actions: ['set'], outcome: null, assist_only: true, points: 0.5, sort_order: 40 },
  { rule_key: 'block', label: 'Block', actions: ['block'], outcome: null, assist_only: false, points: 1, sort_order: 50 },
  { rule_key: 'serve_error', label: 'Service error', actions: ['serve'], outcome: 'error', assist_only: false, points: -1, sort_order: 60 },
  { rule_key: 'attack_error', label: 'Attack error', actions: ['spike', 'overpass'], outcome: 'error', assist_only: false, points: -1, sort_order: 70 },
  { rule_key: 'handling_error', label: 'Ball handling', actions: ['set', 'dig', 'ball_handling'], outcome: 'error', assist_only: false, points: -1, sort_order: 80 },
]

interface DemoMatch {
  match: Match
  slots: Record<Slot, number | null>
  points: PointRow[]
  actions: ActionRow[]
  publications: Publication[]
}

function simulate(id: number, seed: number, finalA: number, finalB: number): { points: PointRow[]; actions: ActionRow[] } {
  const r = rng(seed)
  const order: Team[] = []
  let a = 0
  let b = 0
  while (a < finalA || b < finalB) {
    const needA = finalA - a
    const needB = finalB - b
    const last = needA + needB === 1
    const pickA = last ? needA === 1 : needB === 0 || (needA > 0 && r() < needA / (needA + needB))
    if (pickA) a++
    else b++
    order.push(pickA ? 'A' : 'B')
  }
  const points: PointRow[] = []
  const actions: ActionRow[] = []
  let sa = 0
  let sb = 0
  let server: Team = 'A'
  let frame = 200
  order.forEach((winner, i) => {
    const pointNo = i + 1
    const serverSlot = (server === 'A' ? (pointNo % 4 < 2 ? 'P1A' : 'P2A') : (pointNo % 4 < 2 ? 'P1B' : 'P2B')) as Slot
    const touches: Omit<ActionRow, 'match_id' | 'point_no' | 'seq'>[] = []
    const push = (slot: Slot | null, team: Team, action: ActionName, outcome: ActionRow['outcome'] = null, assist = false) =>
      touches.push({ frame: (frame += 30 + Math.floor(r() * 25)), slot, team, action, outcome, is_assist: assist, observed: slot !== null })
    const roll = r()
    if (roll < 0.06) {
      push(serverSlot, server, 'serve', winner === server ? 'ace' : 'error')
    } else {
      push(serverSlot, server, 'serve')
      let side: Team = server === 'A' ? 'B' : 'A'
      const exchanges = 1 + Math.floor(r() * 3)
      for (let k = 0; k < exchanges; k++) {
        const s1 = (side === 'A' ? 'P1A' : 'P1B') as Slot
        const s2 = (side === 'A' ? 'P2A' : 'P2B') as Slot
        const [digger, setter] = r() < 0.5 ? [s1, s2] : [s2, s1]
        const lastEx = k === exchanges - 1
        const ends = lastEx
        const kill = ends && winner === side
        const err = ends && winner !== side
        if (err && r() < 0.15) {
          push(digger, side, 'dig')
          push(setter, side, 'set', 'error')
          break
        }
        push(r() < 0.08 ? null : digger, side, 'dig')
        push(setter, side, 'set', null, kill)
        push(digger, side, r() < 0.12 ? 'overpass' : 'spike', kill ? 'kill' : err ? 'error' : null)
        side = side === 'A' ? 'B' : 'A'
      }
    }
    touches.forEach((t, seq) => actions.push({ ...t, match_id: id, point_no: pointNo, seq }))
    if (winner === 'A') sa++
    else sb++
    points.push({
      match_id: id, point_no: pointNo, set_no: 1, start_frame: touches[0].frame - 20,
      end_frame: frame + 40, serving_team: server, server_slot: serverSlot, near_team: Math.floor(i / 7) % 2 === 0 ? 'A' : 'B',
      winner_team: winner, winner_source: 'next_serve', end_kind: r() < 0.6 ? 'ground' : 'lost',
      score_a_after: sa, score_b_after: sb, flags: r() < 0.05 ? ['unseen_final_attack'] : [],
    })
    server = winner
    frame += 600
  })
  return { points, actions }
}

function makeMatch(id: number, key: string, venue: string, status: Match['status'], a: number, b: number): Match {
  const [d, t] = key.split('_')
  return {
    id, match_key: key, title: null, venue, season: '2026 Autumn', status, detail_public: false,
    match_date: `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`, start_time: `${t.slice(0, 2)}:${t.slice(2)}:00`,
    points_to_win: 21, score_a: a, score_b: b, winner_team: a > b ? 'A' : 'B', n_points: a + b,
    set_complete: true, duration_s: 1500 + (a + b) * 20,
    checks: { points: a + b, set_complete: true, undecided_points: [], side_switch_after_point: [7, 14, 21, 28],
      switch_blocks_ok: true, flagged_points: status === 'draft' ? { '12': ['line_call_overridden:landed_out'] } : {} },
    updated_at: '2026-10-05T20:00:00Z',
  }
}

export function demoApi(): Api {
  const players: Player[] = ['Ari', 'Joan', 'Marc', 'Pau', 'Laia', 'Nil'].map((name, i) => ({
    id: i + 1, display_name: name, user_id: i === 0 ? ME : null, handedness: null, preferred_side: null,
    profile_public: i === 2, active: true,
  }))
  const profiles: Profile[] = [
    { user_id: ME, email: 'ari@example.com', role: 'admin', display_name: 'Ari' },
    { user_id: '00000000-0000-0000-0000-0000000000b2', email: 'laia@example.com', role: 'viewer', display_name: null },
  ]
  const rulesets: Ruleset[] = [{ id: 1, name: 'G1', description: 'Owner-ratified 2026-09-27', is_active: true }]
  let rules: FantasyRule[] = G1.map((r) => ({ ...r, ruleset_id: 1 }))
  const defs: [string, string, Match['status'], number, number, Record<Slot, number | null>][] = [
    ['20260920_1830_bogatell_ari_joan', 'Bogatell', 'published', 21, 12, { P1A: 1, P2A: 2, P1B: 3, P2B: 4 }],
    ['20260927_1900_bogatell_laia_nil', 'Bogatell', 'published', 19, 21, { P1A: 5, P2A: 6, P1B: 1, P2B: 2 }],
    ['20261004_1805_vall_dhebron', "Vall d'Hebron", 'draft', 21, 17, { P1A: null, P2A: null, P1B: null, P2B: null }],
  ]
  const matches: DemoMatch[] = defs.map(([key, venue, status, a, b, slots], i) => {
    const id = i + 1
    const sim = simulate(id, 7 + i * 13, a, b)
    return {
      match: makeMatch(id, key, venue, status, a, b), slots, ...sim,
      publications: [{
        id: id * 10, match_id: id, revision: 1, result: 'applied', content_sha256: `${key.length}f3a9c2e81b7d`.padEnd(64, '0'),
        pipeline_version: '78844e5', git_dirty: false, bundle_path: `match-bundles/${key}/demo.json`,
        video_url: 'https://drive.google.com/file/d/demo/view', n_points: a + b, n_actions: sim.actions.length,
        score: `${a}-${b}`, published_by: 'joan@macbook', published_at: '2026-10-05T20:00:00Z', notes: null,
      }],
    }
  })
  let session: Session | null = { userId: ME, email: 'ari@example.com' }
  const listeners = new Set<(s: Session | null) => void>()
  const isAdmin = () => profiles.find((p) => p.user_id === session?.userId)?.role === 'admin'
  const mySlotIn = (m: DemoMatch) => SLOTS.find((s) => players.find((p) => p.id === m.slots[s])?.user_id === session?.userId)
  const visible = (m: DemoMatch) => m.match.status === 'published' || isAdmin()
  const canDetail = (m: DemoMatch) => isAdmin() || (m.match.status === 'published' && (m.match.detail_public || !!mySlotIn(m)))
  const activeRules = () => rules.filter((r) => rulesets.find((s) => s.id === r.ruleset_id)?.is_active)

  function box(m: DemoMatch): BoxRow[] {
    return SLOTS.map((slot) => {
      const mine = m.actions.filter((a) => a.slot === slot)
      const n = (f: (a: ActionRow) => boolean) => mine.filter(f).length
      const breakdown: BoxRow['breakdown'] = []
      let fantasy = 0
      for (const r of activeRules()) {
        const count = n((a) => r.actions.includes(a.action) && (r.outcome === null || a.outcome === r.outcome) && (!r.assist_only || a.is_assist))
        if (count) {
          breakdown.push({ rule: r.rule_key, label: r.label, count, points: count * r.points })
          fantasy += count * r.points
        }
      }
      const pid = m.slots[slot]
      return {
        slot, team: slot.slice(2) as Team, player_id: pid, display_name: players.find((p) => p.id === pid)?.display_name ?? null,
        serves: n((a) => a.action === 'serve'), aces: n((a) => a.outcome === 'ace'),
        serve_errors: n((a) => a.action === 'serve' && a.outcome === 'error'), digs: n((a) => a.action === 'dig'),
        sets: n((a) => a.action === 'set'), assists: n((a) => a.is_assist),
        attacks: n((a) => a.action === 'spike' || a.action === 'overpass'),
        kills: n((a) => a.outcome === 'kill'), attack_errors: n((a) => (a.action === 'spike' || a.action === 'overpass') && a.outcome === 'error'),
        handling_errors: n((a) => (a.action === 'set' || a.action === 'dig') && a.outcome === 'error'), blocks: 0,
        fantasy: Math.round(fantasy * 10) / 10, breakdown,
      }
    })
  }

  const byId = (id: number) => matches.find((m) => m.match.id === id)
  const delay = <T,>(v: T) => new Promise<T>((res) => setTimeout(() => res(structuredClone(v)), 60))

  return {
    getSession: () => delay(session),
    onAuthChange(cb) {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    async sendCode() {},
    async verifyCode(email) {
      session = { userId: ME, email }
      listeners.forEach((l) => l(session))
    },
    async signOut() {
      session = null
      listeners.forEach((l) => l(null))
    },
    myProfile: (uid) => delay(profiles.find((p) => p.user_id === uid) ?? null),
    myPlayer: (uid) => delay(players.find((p) => p.user_id === uid) ?? null),
    async setMyPrivacy(isPublic) {
      const me = players.find((p) => p.user_id === session?.userId)
      if (me) me.profile_public = isPublic
      return !!me
    },
    players: () => delay([...players].sort((a, b) => a.display_name.localeCompare(b.display_name))),
    matches: () => delay(matches.filter(visible).map((m) => m.match)),
    match: (key) => delay(matches.find((m) => m.match.match_key === key && visible(m))?.match ?? null),
    participants: (ids) => delay(matches.filter((m) => ids.includes(m.match.id) && visible(m)).flatMap((m) =>
      SLOTS.map((slot): Participant => ({ match_id: m.match.id, slot, team: slot.slice(2) as Team, player_id: m.slots[slot], thumb_path: m.match.status === 'draft' ? `thumbs/${m.match.match_key}/${slot}.jpg` : null })))),
    boxScore: (id) => delay(byId(id) && visible(byId(id)!) ? box(byId(id)!) : []),
    points: (id) => delay(byId(id) && canDetail(byId(id)!) ? byId(id)!.points : []),
    actions: (id) => delay(byId(id) && canDetail(byId(id)!) ? byId(id)!.actions : []),
    leaderboard(season) {
      const rows = new Map<number, LeaderRow>()
      for (const m of matches.filter((x) => x.match.status === 'published' && (!season || x.match.season === season))) {
        for (const b of box(m)) {
          if (!b.player_id) continue
          const r = rows.get(b.player_id) ?? { player_id: b.player_id, display_name: b.display_name ?? '?', matches: 0, wins: 0, fantasy: 0, kills: 0, aces: 0, digs: 0, assists: 0, blocks: 0, errors: 0 }
          r.matches++
          r.wins += b.team === m.match.winner_team ? 1 : 0
          r.fantasy = Math.round((r.fantasy + b.fantasy) * 10) / 10
          r.kills += b.kills
          r.aces += b.aces
          r.digs += b.digs
          r.assists += b.assists
          r.errors += b.serve_errors + b.attack_errors + b.handling_errors
          rows.set(b.player_id, r)
        }
      }
      return delay([...rows.values()].sort((a, b) => b.fantasy - a.fantasy))
    },
    seasons: () => delay(['2026 Autumn']),
    async playerProfile(playerId) {
      const p = players.find((x) => x.id === playerId)
      if (!p) return null
      const history = matches.filter((m) => (m.match.status === 'published' || isAdmin()) && SLOTS.some((s) => m.slots[s] === playerId)).map((m) => {
        const slot = SLOTS.find((s) => m.slots[s] === playerId)!
        const b = box(m).find((x) => x.slot === slot)!
        return {
          match_id: m.match.id, match_key: m.match.match_key, match_date: m.match.match_date, start_time: m.match.start_time,
          title: m.match.title, venue: m.match.venue, season: m.match.season, score_a: m.match.score_a, score_b: m.match.score_b,
          team: b.team, slot, won: b.team === m.match.winner_team, fantasy: b.fantasy, kills: b.kills, aces: b.aces, digs: b.digs,
          assists: b.assists, blocks: 0, serves: b.serves, attacks: b.attacks, errors: b.serve_errors + b.attack_errors + b.handling_errors,
        }
      }).sort((a, b) => b.match_date.localeCompare(a.match_date))
      const sum = (k: 'fantasy' | 'kills' | 'aces' | 'digs' | 'assists' | 'blocks' | 'errors' | 'serves' | 'attacks') => Math.round(history.reduce((t, h) => t + h[k], 0) * 10) / 10
      const allowed = isAdmin() || p.profile_public || p.user_id === session?.userId
      const r = rng(playerId * 31)
      const prof: PlayerProfile = {
        player: { id: p.id, display_name: p.display_name, profile_public: p.profile_public, is_me: p.user_id === session?.userId, handedness: null, preferred_side: null },
        totals: { matches: history.length, wins: history.filter((h) => h.won).length, fantasy: sum('fantasy'), kills: sum('kills'), aces: sum('aces'), digs: sum('digs'), assists: sum('assists'), blocks: 0, errors: sum('errors'), serves: sum('serves'), attacks: sum('attacks') },
        history, can_see_analytics: allowed,
        analytics: allowed ? {
          kill_rate: sum('attacks') ? Math.round((sum('kills') / sum('attacks')) * 1000) / 1000 : null,
          attack_error_rate: 0.12, ace_rate: sum('serves') ? Math.round((sum('aces') / sum('serves')) * 1000) / 1000 : null, serve_error_rate: 0.08,
          attack_zones: { '1': 4, '2': 7, '3': 2, '5': 3, '6': 1 },
          landings: Array.from({ length: 18 }, () => ({ x: 0.5 + r() * 7, y: 8.6 + r() * 7, in: r() > 0.15, outcome: r() > 0.6 ? 'kill' : null, source: 'next_touch' })),
          touch_depths: [],
        } : null,
      }
      return delay(prof)
    },
    async updateMatch(id, patch) {
      Object.assign(byId(id)!.match, patch)
    },
    async assignSlot(id, slot, playerId) {
      const m = byId(id)!
      if (playerId !== null && SLOTS.some((s) => s !== slot && m.slots[s] === playerId))
        throw new Error('duplicate key value violates unique constraint "match_participants_match_id_player_id_key"')
      m.slots[slot] = playerId
    },
    async createPlayer(name) {
      const p: Player = { id: players.length + 1, display_name: name, user_id: null, handedness: null, preferred_side: null, profile_public: false, active: true }
      players.push(p)
      return p
    },
    async updatePlayer(id, patch) {
      Object.assign(players.find((p) => p.id === id)!, patch)
    },
    profiles: () => delay(profiles),
    async setRole(uid, role) {
      profiles.find((p) => p.user_id === uid)!.role = role
    },
    matchSource: (id) => delay({ match_id: id, video_filename: `${byId(id)!.match.match_key}.mp4`, video_url: 'https://drive.google.com/file/d/demo/view', video_sha256: 'c0ffee'.padEnd(64, '0'), fps: 25.67, width: 1280, height: 720 }),
    publications: (id) => delay(byId(id)!.publications),
    async thumbUrls(paths) {
      const out: Record<string, string> = {}
      paths.forEach((p, i) => {
        const hue = [205, 160, 25, 340][i % 4]
        out[p] = `data:image/svg+xml;utf8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="96" height="160"><rect width="96" height="160" fill="hsl(${hue},45%,82%)"/><circle cx="48" cy="40" r="18" fill="hsl(${hue},40%,45%)"/><rect x="26" y="62" width="44" height="70" rx="12" fill="hsl(${hue},40%,45%)"/></svg>`)}`
      })
      return out
    },
    bundleUrl: async () => null,
    rulesets: () => delay(rulesets),
    rules: (id) => delay(rules.filter((r) => r.ruleset_id === id).sort((a, b) => a.sort_order - b.sort_order)),
    async setRulePoints(id, key, points) {
      rules = rules.map((r) => (r.ruleset_id === id && r.rule_key === key ? { ...r, points } : r))
    },
    async cloneRuleset(from, name) {
      const id = Math.max(...rulesets.map((r) => r.id)) + 1
      rulesets.push({ id, name, description: `copy of ${rulesets.find((r) => r.id === from)?.name}`, is_active: false })
      rules = [...rules, ...rules.filter((r) => r.ruleset_id === from).map((r) => ({ ...r, ruleset_id: id }))]
      return id
    },
    async activateRuleset(id) {
      rulesets.forEach((r) => (r.is_active = r.id === id))
    },
  }
}
