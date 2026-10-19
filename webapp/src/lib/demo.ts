// Demo mode (VITE_DEMO=1): an in-memory league that implements `Api`, so the
// UI can be developed, reviewed and screenshotted without a Supabase project.
// The data is synthetic; the rules (credited touches, fantasy rules,
// privacy tiers) mirror the SQL so the pages behave like production.
import type { Api } from './api'
import { blobDataUrl } from './feedback'
import { hitSplit, longestRally, playerAnalytics, pointFantasy, serveRows, serveTargets, teamRally, type Seat, type Touch } from './analytics'
import {
  competitionRank, dayState, lineupPoints, lineupProblem, NO_HISTORY_PRICE, standings, suggestedPrices, type PriceSample,
} from './fantasy'
import type {
  ActionName, ActionRow, BoxRow, FantasyDay, FantasyDayPage, FantasyDaySummary, FantasyFixture, FantasyFixturePlayer,
  FantasyLineup, FantasyRule, Feedback, FixtureMismatch, LeaderRow, Match, MatchType, PointRow, Participant,
  Pass, Player, PlayerProfile, Profile, Publication, ReportPlayer, Ruleset, Serve, Session, Slot, Team, WindowParams,
} from './types'


const SLOTS: Slot[] = ['P1A', 'P2A', 'P1B', 'P2B']
const ME = '00000000-0000-0000-0000-0000000000a1'
/** Every demo attack plays the same drawn clip (public/demo-clip.mp4): no footage of real people ships with the app. */
const DEMO_CLIP = 'clips/demo/attack.mp4'

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
  { rule_key: 'block', label: 'Kill block', actions: ['block'], outcome: 'kill', assist_only: false, points: 1, sort_order: 50 },
  { rule_key: 'serve_error', label: 'Service error', actions: ['serve'], outcome: 'error', assist_only: false, points: -1, sort_order: 60 },
  { rule_key: 'attack_error', label: 'Attack error', actions: ['spike', 'overpass'], outcome: 'error', assist_only: false, points: -1, sort_order: 70 },
  { rule_key: 'handling_error', label: 'Ball handling', actions: ['set', 'dig', 'ball_handling'], outcome: 'error', assist_only: false, points: -1, sort_order: 80 },
]

type DemoAction = ActionRow & { touch_number: number; spike_type?: 'hard' | 'touch' | null }

interface DemoMatch {
  match: Match
  slots: Record<Slot, number | null>
  /** Slots the admin marked unknown (no player, stats kept in the match). */
  unknown: Slot[]
  points: PointRow[]
  actions: DemoAction[]
  publications: Publication[]
}

function simulate(id: number, seed: number, finalA: number, finalB: number): { points: PointRow[]; actions: DemoAction[] } {
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
  const actions: DemoAction[] = []
  let sa = 0
  let sb = 0
  let server: Team = 'A'
  let frame = 200
  order.forEach((winner, i) => {
    const pointNo = i + 1
    const serverSlot = (server === 'A' ? (pointNo % 4 < 2 ? 'P1A' : 'P2A') : (pointNo % 4 < 2 ? 'P1B' : 'P2B')) as Slot
    const touches: Omit<DemoAction, 'match_id' | 'point_no' | 'seq'>[] = []
    const push = (slot: Slot | null, team: Team, action: ActionName, touchNo: number, outcome: ActionRow['outcome'] = null, assist = false) =>
      touches.push({ frame: (frame += 30 + Math.floor(r() * 25)), slot, team, action, outcome, is_assist: assist, observed: slot !== null, touch_number: touchNo })
    const roll = r()
    if (roll < 0.06) {
      push(serverSlot, server, 'serve', 0, winner === server ? 'ace' : 'error')
    } else {
      push(serverSlot, server, 'serve', 0)
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
          push(digger, side, 'dig', 1)
          push(setter, side, 'set', 2, 'error')
          break
        }
        push(r() < 0.08 ? null : digger, side, 'dig', 1)
        push(setter, side, 'set', 2, null, kill)
        push(digger, side, r() < 0.12 ? 'overpass' : 'spike', 3, kill ? 'kill' : err ? 'error' : null)
        side = side === 'A' ? 'B' : 'A'
      }
    }
    // every attack gets the type a flight read would give it: a free ball
    // reads touch, and about one spike in ten is not read (no extra draw
    // from the generator, so the simulated matches stay what they were)
    for (const t of touches) {
      if (t.action === 'overpass') t.spike_type = 'touch'
      if (t.action === 'spike') t.spike_type = t.frame % 10 === 0 ? null : t.frame % 10 < 5 ? 'hard' : 'touch'
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

function makeMatch(id: number, key: string, venue: string, status: Match['status'], a: number, b: number,
                   type: MatchType | null): Match {
  const [d, t] = key.split('_')
  return {
    id, match_key: key, title: null, venue, season: '2026 Autumn', status, detail_public: false,
    match_type: type, is_tournament: type === null ? null : id === 1,
    tournament_level: id === 1 ? 'regional' : null,
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
    // fantasy-only members: accounts that play no match
    { user_id: '00000000-0000-0000-0000-0000000000c1', email: 'sergi@example.com', role: 'viewer', display_name: 'Sergi' },
    { user_id: '00000000-0000-0000-0000-0000000000c2', email: 'marta@example.com', role: 'viewer', display_name: 'Marta' },
  ]
  const rulesets: Ruleset[] = [{ id: 1, name: 'G1', description: 'Owner-ratified 2026-09-27', is_active: true }]
  let rules: FantasyRule[] = G1.map((r) => ({ ...r, ruleset_id: 1 }))
  type Def = [string, string, Match['status'], number, number, MatchType | null, Record<Slot, number | null>, Slot[]?]
  const defs: Def[] = [
    ['20260920_1830_bogatell_ari_joan', 'Bogatell', 'published', 21, 12, 'mixed', { P1A: 1, P2A: 2, P1B: 3, P2B: 4 }],
    ['20260927_1900_bogatell_laia_nil', 'Bogatell', 'published', 19, 21, 'mixed', { P1A: 5, P2A: 6, P1B: 1, P2B: 2 }],
    ['20261004_1805_vall_dhebron', "Vall d'Hebron", 'draft', 21, 17, null, { P1A: null, P2A: null, P1B: null, P2B: null }],
    ['20260906_1000_bogatell_ari_marc', 'Bogatell', 'published', 21, 15, 'male', { P1A: 1, P2A: 3, P1B: 2, P2B: 4 }],
    ['20260913_1730_bogatell_joan_pau', 'Bogatell', 'published', 17, 21, null, { P1A: 2, P2A: 4, P1B: 1, P2B: null }, ['P2B']],
  ]
  const venues = [...new Set(defs.map((d) => d[1]))]
  const matches: DemoMatch[] = defs.map(([key, venue, status, a, b, type, slots, unknown = []], i) => {
    const id = i + 1
    const sim = simulate(id, 7 + i * 13, a, b)
    return {
      match: makeMatch(id, key, venue, status, a, b, type), slots, unknown, ...sim,
      publications: [{
        id: id * 10, match_id: id, revision: 1, result: 'applied', content_sha256: `${key.length}f3a9c2e81b7d`.padEnd(64, '0'),
        pipeline_version: '78844e5', git_dirty: false, bundle_path: `match-bundles/${key}/demo.json`,
        video_url: 'https://drive.google.com/file/d/demo/view', n_points: a + b, n_actions: sim.actions.length,
        score: `${a}-${b}`, published_by: 'joan@macbook', published_at: '2026-10-05T20:00:00Z', notes: null,
      }],
    }
  })
  const feedback: Feedback[] = [{
    id: 1, user_id: ME, kind: 'bug', message: 'On my phone the attack map is cut off on the right.', page: '/players/1',
    context: { viewport: '390x844' }, screenshots: [], status: 'done', admin_note: 'Fixed: the map now scales to the screen.',
    created_at: '2026-10-07T18:20:00Z', author: { email: 'ari@example.com', display_name: 'Ari' },
  }]
  const shots: Record<string, string> = {}
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
  /** The matches a window keeps, newest first (the SQL `window_matches`). */
  const windowed = (list: DemoMatch[], w: WindowParams, type: MatchType | null = null) => {
    const kept = list
      .filter((m) => (!w.season || m.match.season === w.season) && (!w.from || m.match.match_date >= w.from)
        && (!w.to || m.match.match_date <= w.to) && (!type || m.match.match_type === type))
      .sort((a, b) => `${b.match.match_date}${b.match.start_time}`.localeCompare(`${a.match.match_date}${a.match.start_time}`))
    return w.lastN ? kept.slice(0, w.lastN) : kept
  }
  const delay = <T,>(v: T) => new Promise<T>((res) => setTimeout(() => res(structuredClone(v)), 60))

  // ── the fantasy game: the SQL of 20261019100000, over the demo league ──
  const at = (days: number, hour: number, minute = 0) => {
    const d = new Date()
    d.setDate(d.getDate() + days)
    d.setHours(hour, minute, 0, 0)
    return d.toISOString()
  }
  const fDays: FantasyDay[] = [
    { id: 1, season: '2026 Autumn', name: 'Match day 1', status: 'open', squad_size: 3, budget: 25, captain_multiplier: 2, opened_at: '2026-09-15T09:00:00Z' },
    { id: 2, season: '2026 Autumn', name: 'Match day 2', status: 'open', squad_size: 3, budget: 25, captain_multiplier: 2, opened_at: at(-1, 9) },
    { id: 3, season: '2026 Autumn', name: 'Match day 3', status: 'draft', squad_size: 3, budget: 25, captain_multiplier: 2, opened_at: null },
  ]
  const fixtures: FantasyFixture[] = [
    { id: 1, match_day_id: 1, scheduled_at: '2026-09-20T16:30:00Z', venue: 'Bogatell', match_id: 1, fantasy_published: true, cancelled: false },
    { id: 2, match_day_id: 1, scheduled_at: '2026-09-27T17:00:00Z', venue: 'Bogatell', match_id: 2, fantasy_published: true, cancelled: false },
    { id: 3, match_day_id: 2, scheduled_at: at(2, 10), venue: 'Bogatell', match_id: null, fantasy_published: false, cancelled: false },
    { id: 4, match_day_id: 2, scheduled_at: at(2, 11, 30), venue: 'Bogatell', match_id: null, fantasy_published: false, cancelled: false },
    { id: 5, match_day_id: 3, scheduled_at: at(9, 10), venue: "Vall d'Hebron", match_id: null, fantasy_published: false, cancelled: false },
  ]
  const fxPlayers: FantasyFixturePlayer[] = ([
    [1, 1, 'A'], [1, 2, 'A'], [1, 3, 'B'], [1, 4, 'B'],
    [2, 5, 'A'], [2, 6, 'A'], [2, 1, 'B'], [2, 2, 'B'],
    [3, 1, 'A'], [3, 3, 'A'], [3, 4, 'B'], [3, 5, 'B'],
    [4, 2, 'A'], [4, 6, 'A'],                    // their opponents are guests nobody can pick
    [5, 1, 'A'], [5, 2, 'A'], [5, 5, 'B'], [5, 6, 'B'],
  ] as [number, number, Team][]).map(([fixture_id, player_id, team]) => ({ fixture_id, player_id, team }))
  const prices = new Map<string, { price: number; is_override: boolean }>()
  const lineups: (FantasyLineup & { day: number; user: string; updated_at: string })[] = [
    { day: 1, user: ME, player_ids: [1, 3, 5], captain: 1, updated_at: '2026-09-19T20:00:00Z' },
    { day: 1, user: '00000000-0000-0000-0000-0000000000c1', player_ids: [2, 4, 6], captain: 2, updated_at: '2026-09-19T21:00:00Z' },
    { day: 1, user: '00000000-0000-0000-0000-0000000000c2', player_ids: [1, 2, 6], captain: 6, updated_at: '2026-09-20T08:00:00Z' },
    { day: 2, user: '00000000-0000-0000-0000-0000000000c1', player_ids: [3, 4, 2], captain: 3, updated_at: at(0, 8) },
  ]
  const nameOf = (uid: string) => profiles.find((p) => p.user_id === uid)?.display_name ?? '?'
  const dayFixtures = (day: number) => fixtures.filter((f) => f.match_day_id === day)
  const dayPlayerIds = (day: number) => [...new Set(fxPlayers
    .filter((fp) => dayFixtures(day).some((f) => f.id === fp.fixture_id)).map((fp) => fp.player_id))]
  /** Published matches, newest first, per player (the price's history). */
  const priceHistory = () => {
    const h = new Map<number, PriceSample[]>()
    const published = windowed(matches.filter((m) => m.match.status === 'published'), { season: null, from: null, to: null, lastN: null })
    for (const m of published) for (const b of box(m)) {
      if (b.player_id) h.set(b.player_id, [...(h.get(b.player_id) ?? []), { fantasy: b.fantasy, n_points: m.match.n_points ?? 0 }])
    }
    return h
  }
  const priceOf = (day: number, player: number) =>
    prices.get(`${day}:${player}`)?.price ?? suggestedPrices(priceHistory()).get(player) ?? NO_HISTORY_PRICE
  for (const d of fDays.filter((x) => x.status === 'open')) for (const p of dayPlayerIds(d.id)) prices.set(`${d.id}:${p}`, { price: priceOf(d.id, p), is_override: false })
  /** SQL `fantasy_player_points`: fixtures published to fantasy, by player. */
  const dayPoints = (day: number) => {
    const out = new Map<number, number>()
    for (const f of dayFixtures(day).filter((x) => x.fantasy_published && !x.cancelled && x.match_id !== null)) {
      const m = byId(f.match_id!)
      if (!m || m.match.status !== 'published') continue
      for (const b of box(m)) if (b.player_id) out.set(b.player_id, Math.round(((out.get(b.player_id) ?? 0) + b.fantasy) * 10) / 10)
    }
    return out
  }
  const stateOf = (d: FantasyDay) => dayState(d.status, dayFixtures(d.id), new Date())
  const dayScores = (day: FantasyDay) => {
    const pts = dayPoints(day.id)
    return lineups.filter((l) => l.day === day.id)
      .map((l) => ({ user: l.user, points: lineupPoints(l, day.captain_multiplier, (p) => pts.get(p)) }))
  }
  const seeDay = (d: FantasyDay | undefined) => !!d && (d.status === 'open' || isAdmin())
  const mismatch = (f: FantasyFixture): FixtureMismatch => {
    const m = f.match_id === null ? undefined : byId(f.match_id)
    const inMatch = m ? SLOTS.map((s) => m.slots[s]).filter((x): x is number => x !== null) : []
    const inFixture = fxPlayers.filter((fp) => fp.fixture_id === f.id).map((fp) => fp.player_id)
    const name = (id: number) => players.find((p) => p.id === id)!.display_name
    return { missing: inFixture.filter((p) => !inMatch.includes(p)).map(name).sort(),
             extra: inMatch.filter((p) => !inFixture.includes(p)).map(name).sort() }
  }
  const lockedNow = (day: number) => {
    const d = fDays.find((x) => x.id === day)!
    return stateOf(d).locked
  }
  const adminOnly = () => {
    if (!isAdmin()) throw new Error('admins only')
  }

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
      SLOTS.map((slot): Participant => ({ match_id: m.match.id, slot, team: slot.slice(2) as Team, player_id: m.slots[slot], is_unknown: m.unknown.includes(slot), thumb_path: m.match.status === 'draft' ? `thumbs/${m.match.match_key}/${slot}.jpg` : null })))),
    boxScore: (id) => delay(byId(id) && visible(byId(id)!) ? box(byId(id)!) : []),
    points: (id) => delay(byId(id) && canDetail(byId(id)!) ? byId(id)!.points : []),
    actions: (id) => delay(byId(id) && canDetail(byId(id)!) ? byId(id)!.actions : []),
    leaderboard(w, type) {
      const rows = new Map<number, Required<LeaderRow>>()
      for (const m of windowed(matches.filter((x) => x.match.status === 'published'), w, type ?? null)) {
        for (const b of box(m)) {
          if (!b.player_id) continue
          const r: Required<LeaderRow> = rows.get(b.player_id) ?? { player_id: b.player_id, display_name: b.display_name ?? '?', matches: 0, wins: 0, fantasy: 0, kills: 0, aces: 0, digs: 0, assists: 0, blocks: 0, errors: 0, attacks: 0, attack_errors: 0, serves: 0, points_played: 0, fantasy_per_21: null, serve_errors: 0, recv_points: 0, recv_won: 0, serve_points: 0, serve_won: 0 }
          const rally = teamRally(m.points)[b.team]
          r.matches++
          r.wins += b.team === m.match.winner_team ? 1 : 0
          r.fantasy = Math.round((r.fantasy + b.fantasy) * 10) / 10
          r.kills += b.kills
          r.aces += b.aces
          r.digs += b.digs
          r.assists += b.assists
          r.errors += b.serve_errors + b.attack_errors + b.handling_errors
          r.attacks += b.attacks
          r.attack_errors += b.attack_errors
          r.serves += b.serves
          r.points_played += m.match.n_points ?? 0
          r.serve_errors += b.serve_errors
          r.recv_points += rally?.recv_n ?? 0
          r.recv_won += rally?.recv_won ?? 0
          r.serve_points += rally?.serve_n ?? 0
          r.serve_won += rally?.serve_won ?? 0
          rows.set(b.player_id, r)
        }
      }
      for (const r of rows.values()) r.fantasy_per_21 = r.points_played ? Math.round((r.fantasy / r.points_played) * 210) / 10 : null
      return delay([...rows.values()].sort((a, b) => b.fantasy - a.fantasy))
    },
    seasons: () => delay(['2026 Autumn']),
    async playerProfile(playerId, w) {
      const p = players.find((x) => x.id === playerId)
      if (!p) return null
      const mine = matches.filter((m) => visible(m) && SLOTS.some((s) => m.slots[s] === playerId))
      const inWindow = windowed(mine, w)
      const row = (m: DemoMatch) => {
        const slot = SLOTS.find((s) => m.slots[s] === playerId)!
        const b = box(m).find((x) => x.slot === slot)!
        return { m, slot, b }
      }
      const history = inWindow.map(row).map(({ m, slot, b }) => ({
        match_id: m.match.id, match_key: m.match.match_key, match_date: m.match.match_date, start_time: m.match.start_time,
        title: m.match.title, venue: m.match.venue, season: m.match.season, score_a: m.match.score_a, score_b: m.match.score_b,
        team: b.team, slot, won: b.team === m.match.winner_team, fantasy: b.fantasy, kills: b.kills, aces: b.aces, digs: b.digs,
        assists: b.assists, blocks: 0, serves: b.serves, attacks: b.attacks, errors: b.serve_errors + b.attack_errors + b.handling_errors,
        attack_errors: b.attack_errors, serve_errors: b.serve_errors, n_points: m.match.n_points,
      }))
      type Sum = 'fantasy' | 'kills' | 'aces' | 'digs' | 'assists' | 'blocks' | 'errors' | 'serves' | 'attacks' | 'attack_errors' | 'serve_errors'
      const sum = (k: Sum) => Math.round(history.reduce((t, h) => t + h[k], 0) * 10) / 10
      const pointsPlayed = history.reduce((t, h) => t + (h.n_points ?? 0), 0)
      const allowed = isAdmin() || p.profile_public || p.user_id === session?.userId
      const r = rng(playerId * 31)
      const all = mine.map(row).map((x) => x.b.fantasy)       // newest first
      const last5 = all.slice(0, 5).reverse()
      const seats: Seat[] = [...inWindow].reverse().map((m) => {
        const slot = SLOTS.find((s) => m.slots[s] === playerId)!
        return {
          slot, team: slot.slice(2) as Team, date: m.match.match_date, points: m.points, touches: m.actions,
          who: (sl) => ({ player_id: m.slots[sl], display_name: players.find((x) => x.id === m.slots[sl])?.display_name ?? sl }),
        }
      })
      const prof: PlayerProfile = {
        player: { id: p.id, display_name: p.display_name, profile_public: p.profile_public, is_me: p.user_id === session?.userId, handedness: null, preferred_side: null },
        totals: {
          matches: history.length, wins: history.filter((h) => h.won).length, fantasy: sum('fantasy'), kills: sum('kills'),
          aces: sum('aces'), digs: sum('digs'), assists: sum('assists'), blocks: 0, errors: sum('errors'), serves: sum('serves'),
          attacks: sum('attacks'), attack_errors: sum('attack_errors'), serve_errors: sum('serve_errors'),
          points_played: pointsPlayed, fantasy_per_21: pointsPlayed ? Math.round((sum('fantasy') / pointsPlayed) * 210) / 10 : null,
        },
        form: {
          n: all.length, avg5: last5.length ? Math.round((last5.reduce((a, b) => a + b, 0) / last5.length) * 100) / 100 : null,
          avg_all: all.length ? Math.round((all.reduce((a, b) => a + b, 0) / all.length) * 100) / 100 : null, last5,
        },
        history, can_see_analytics: allowed,
        analytics: allowed ? {
          ...playerAnalytics(seats),
          attack_zones: { '1': 4, '2': 7, '3': 2, '5': 3, '6': 1 },
          landings: Array.from({ length: 22 }, (_, i) => {
            const k = r()
            const y = 8.6 + r() * 7
            const free = r() < 0.2
            // where the ball was hit: a spike near the net, a free ball from deeper
            const start = {
              sx: 0.8 + r() * 6.4, sy: free ? 2 + r() * 4 : 5.2 + r() * 2.2, sex: 0.4, sey: 0.7,
              a: free ? 'overpass' : 'spike', p: r() < 0.6 ? 1 : 2, d: seats.length ? seats[i % seats.length].date : null,
            }
            const type = free ? 'touch' : i % 7 === 6 ? null : i % 2 ? 'touch' : 'hard'
            // a clip follows the touches of its match: the player's own attacks
            // (they played those matches) and an admin; a shared profile shows none
            const clip = isAdmin() || p.user_id === session?.userId ? DEMO_CLIP : null
            const spot = { ...start, x: 0.5 + r() * 7, y, zone: 2, type, clip }
            // depth is the weak axis, and worse far from the camera
            if (k < 0.55) return { ...spot, ex: 0.4, ey: 0.7, in: null, outcome: null, result: 'dug' as const, source: 'next_touch' }
            if (k < 0.8) return { ...spot, ex: 0.3, ey: 0.3 + (y - 8) * 0.1, in: true, outcome: 'kill', result: 'kill' as const, source: 'ball_death' }
            if (k < 0.92) return { ...spot, x: r() > 0.5 ? 9.4 : -1.2, ex: 0.3, ey: 0.3 + (y - 8) * 0.1, in: false, outcome: 'error', result: 'out' as const, source: 'ball_death' }
            return { ...start, type, clip, x: null, y: null, in: null, outcome: 'error', result: 'net' as const, source: null }
          }),
          touch_depths: [],
          // receptions land close together, defenses are scattered; a few went straight over
          passes: Array.from({ length: 34 }, (_, i): Pass => {
            const recv = i % 2 === 0
            const jitter = (sd: number) => (r() + r() + r() - 1.5) * 2 * sd
            const went = r() > 0.12
            return {
              k: recv ? 'reception' : 'defense',
              sx: Math.min(8, Math.max(0, 4 + jitter(2.2))), sy: recv ? 1.5 + r() * 3.5 : 2 + r() * 4, sex: 0.4, sey: 0.7,
              x: went ? Math.min(8, Math.max(0, 4.3 + jitter(recv ? 0.6 : 1.5))) : null,
              y: went ? Math.min(8.4, Math.max(2, 6.6 + jitter(recv ? 0.5 : 1.2))) : null,
              ex: went ? 0.4 : null, ey: went ? 0.7 : null,
              to: went ? (r() > 0.85 ? 'spike' : 'set') : null,
              d: seats.length ? seats[i % seats.length].date : null,
            }
          }),
          // the serves the tiles count, each with a drawn spot: an ace falls deep
          // or on a line, an error past the baseline, wide or in the net, and
          // about one serve in ten has a receiver nobody saw
          serves: serveRows(seats).map((sv): Serve => {
            const k = r()
            const across = 0.6 + r() * 6.8
            if (sv.r === 'error') {
              const spot = k < 0.4 ? { x: across, y: 16.4 + r() * 0.9 } : k < 0.7 ? { x: r() > 0.5 ? 8.7 : -0.6, y: 10 + r() * 5 } : { x: across, y: 7.6 }
              return { ...sv, ...spot, ex: null, ey: null, src: 'ground', in: false }
            }
            if (sv.r === 'ace') {
              return { ...sv, x: r() > 0.5 ? 0.5 + r() : 6.5 + r(), y: 13 + r() * 2.6, ex: null, ey: null, src: sv.to ? 'reception' : 'ground', in: sv.to ? null : true }
            }
            if (k < 0.1 || !sv.to) return { ...sv, x: null, y: null, ex: null, ey: null, src: null, in: null }
            return { ...sv, x: across, y: 10.5 + r() * 4.5, ex: 0.4, ey: 0.9, src: 'reception', in: null }
          }),
        } : null,
      }
      return delay(prof)
    },
    async matchReport(id) {
      const m = byId(id)
      if (!m || !visible(m)) return null
      const fantasyOf = (t: Touch, assist: boolean) => activeRules().reduce((sum, rule) =>
        sum + (rule.actions.includes(t.action) && (rule.outcome === null || t.outcome === rule.outcome) && (!rule.assist_only || assist) ? rule.points : 0), 0)
      const assistIds = new Set(m.actions.filter((a) => a.is_assist).map((a) => `${a.point_no}:${a.seq}`))
      const detail = canDetail(m)
      const timeline = detail
        ? pointFantasy(m.actions, fantasyOf, (t) => assistIds.has(`${t.point_no}:${t.seq}`)) : null
      // Analytics tier, as in SQL: a player's numbers show with the play-by-play,
      // or when they are the reader's own / shared; a number that splits a team
      // total needs BOTH teammates visible.
      const slotOk = (slot: Slot) => {
        const pl = players.find((x) => x.id === m.slots[slot])
        return detail || (!!pl && (pl.profile_public || pl.user_id === session?.userId))
      }
      const teamOk = (team: Team) => SLOTS.filter((s) => s.slice(2) === team).every(slotOk)
      const players_: ReportPlayer[] = box(m).map((b) => {
        const others = b.player_id === null ? [] : matches.filter((o) => o.match.status === 'published' && o.match.id !== m.match.id
          && SLOTS.some((s) => o.slots[s] === b.player_id)).map((o) => box(o).find((x) => o.slots[x.slot] === b.player_id)!)
        const mean = (f: (x: BoxRow) => number) => others.length ? Math.round((others.reduce((t, x) => t + f(x), 0) / others.length) * 100) / 100 : null
        return {
          slot: b.slot, team: b.team, player_id: b.player_id, display_name: b.display_name, fantasy: b.fantasy,
          fantasy_per_21: m.match.n_points ? Math.round((b.fantasy / m.match.n_points) * 210) / 10 : null,
          serves: b.serves, aces: b.aces, serve_errors: b.serve_errors, digs: b.digs, sets: b.sets, assists: b.assists,
          attacks: b.attacks, kills: b.kills, attack_errors: b.attack_errors, handling_errors: b.handling_errors,
          hit: slotOk(b.slot) ? hitSplit(m.actions, b.slot) : null,
          own_serve: !teamOk(b.team) ? null : {
            n: m.points.filter((p) => p.winner_team && p.server_slot === b.slot).length,
            won: m.points.filter((p) => p.server_slot === b.slot && p.winner_team === b.team).length },
          avg: b.player_id === null || !slotOk(b.slot) ? null : {
            matches: others.length, fantasy: mean((x) => x.fantasy), kills: mean((x) => x.kills), aces: mean((x) => x.aces),
            digs: mean((x) => x.digs), assists: mean((x) => x.assists),
            errors: mean((x) => x.serve_errors + x.attack_errors + x.handling_errors), attacks: mean((x) => x.attacks),
          },
        }
      })
      const targets = serveTargets(m.points, m.actions)
      for (const team of ['A', 'B'] as Team[]) if (!teamOk(team === 'A' ? 'B' : 'A')) delete targets[team]
      // League tier, like the result: two counts and a point number.
      return delay({ match_id: m.match.id, teams: teamRally(m.points), players: players_, serve_targets: targets, timeline,
        longest_rally: longestRally(m.points, m.actions) })
    },
    async updateMatch(id, patch) {
      const next = { ...byId(id)!.match, ...patch }
      // the checks of 20261014120000
      if (next.venue !== null && !venues.includes(next.venue)) throw new Error('matches_venue_fkey')
      if (next.tournament_level !== null && !next.is_tournament) throw new Error('matches_level_needs_tournament')
      Object.assign(byId(id)!.match, patch)
    },
    venues: () => delay([...venues].sort((a, b) => a.localeCompare(b))),
    async addVenue(name) {
      if (!isAdmin()) throw new Error('new row violates row-level security policy for table "venues"')
      if (venues.some((v) => v.toLowerCase() === name.toLowerCase())) throw new Error('venues_name_ci')
      venues.push(name)
    },
    async assignSlot(id, slot, playerId, unknown = false) {
      const m = byId(id)!
      if (!unknown && playerId !== null && SLOTS.some((s) => s !== slot && m.slots[s] === playerId))
        throw new Error('duplicate key value violates unique constraint "match_participants_match_id_player_id_key"')
      m.slots[slot] = unknown ? null : playerId
      m.unknown = m.unknown.filter((s) => s !== slot).concat(unknown ? [slot] : [])
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
    async sendFeedback(userId, report) {
      const paths: string[] = []
      for (const image of report.images) {
        const path = `${userId}/${feedback.length}-${paths.length}.jpg`
        shots[path] = await blobDataUrl(image)
        paths.push(path)
      }
      feedback.unshift({
        id: feedback.length + 1, user_id: userId, kind: report.kind, message: report.message.trim(),
        page: report.page, context: report.context, screenshots: paths, status: 'open', admin_note: null,
        created_at: new Date().toISOString(),
        author: { email: profiles.find((p) => p.user_id === userId)?.email ?? null, display_name: null },
      })
    },
    myFeedback: (userId) => delay(feedback.filter((f) => f.user_id === userId)),
    allFeedback: () => delay([...feedback]),
    async setFeedbackStatus(id, status, note) {
      Object.assign(feedback.find((f) => f.id === id)!, { status, admin_note: note })
    },
    clipUrl: async (path) => (path === DEMO_CLIP ? '/demo-clip.mp4' : null),
    async feedbackUrls(paths) {
      return Object.fromEntries(paths.filter((p) => shots[p]).map((p) => [p, shots[p]]))
    },

    fantasyDays(season = null) {
      const rows: FantasyDaySummary[] = fDays.filter((d) => seeDay(d) && (!season || d.season === season)).map((d) => {
        const st = stateOf(d)
        const scores = dayScores(d)
        const top = scores.length ? Math.max(...scores.map((x) => x.points)) : null
        return {
          id: d.id, season: d.season, name: d.name, status: d.status, ...st,
          n_fixtures: dayFixtures(d.id).filter((f) => !f.cancelled).length,
          has_lineup: lineups.some((l) => l.day === d.id && l.user === session?.userId),
          my_points: scores.find((x) => x.user === session?.userId)?.points ?? null,
          leader: st.locked && top !== null ? scores.filter((x) => x.points === top).map((x) => nameOf(x.user)).sort().join(', ') : null,
          leader_points: st.locked ? top : null,
        }
      })
      return delay(rows.sort((a, b) => (b.locks_at ?? '9').localeCompare(a.locks_at ?? '9') || b.id - a.id))
    },
    fantasyDay(id) {
      const d = fDays.find((x) => x.id === id)
      if (!seeDay(d)) return delay(null)
      const st = stateOf(d!)
      const pts = dayPoints(id)
      const history = priceHistory()
      const suggested = suggestedPrices(history)
      const scores = dayScores(d!)
      const ranks = competitionRank(scores.map((x) => x.points))
      const mine = lineups.find((l) => l.day === id && l.user === session?.userId)
      const page: FantasyDayPage = {
        day: { id: d!.id, season: d!.season, name: d!.name, status: d!.status, squad_size: d!.squad_size, budget: d!.budget,
               captain_multiplier: d!.captain_multiplier, ...st },
        me: { manager: nameOf(session?.userId ?? '') === '?' ? null : nameOf(session!.userId) },
        fixtures: dayFixtures(id).sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)).map((f) => {
          const m = f.match_id === null ? undefined : byId(f.match_id)
          const shown = m && (m.match.status === 'published' || isAdmin())
          return { id: f.id, scheduled_at: f.scheduled_at, venue: f.venue, cancelled: f.cancelled, fantasy_published: f.fantasy_published,
                   match_key: shown ? m!.match.match_key : null, score_a: shown ? m!.match.score_a : null, score_b: shown ? m!.match.score_b : null,
                   players: fxPlayers.filter((fp) => fp.fixture_id === f.id).map((fp) => ({ player_id: fp.player_id, team: fp.team })) }
        }),
        players: dayPlayerIds(id).map((pid) => {
          const p = prices.get(`${id}:${pid}`)
          const samples = history.get(pid) ?? []
          const points = samples.slice(0, 10).reduce((t, x) => t + x.n_points, 0)
          return {
            player_id: pid, display_name: players.find((x) => x.id === pid)!.display_name,
            price: p?.price ?? suggested.get(pid) ?? NO_HISTORY_PRICE, is_override: p?.is_override ?? false,
            per21: points ? Math.round((samples.slice(0, 10).reduce((t, x) => t + x.fantasy, 0) / points) * 210) / 10 : null,
            form: samples.slice(0, 5).map((x) => x.fantasy).reverse(), points: pts.get(pid) ?? null,
          }
        }).sort((a, b) => b.price - a.price || a.display_name.localeCompare(b.display_name)),
        my_lineup: mine ? { player_ids: mine.player_ids, captain: mine.captain, updated_at: mine.updated_at,
                            points: scores.find((x) => x.user === mine.user)?.points ?? null } : null,
        lineups: !st.locked ? null : scores.map((x, i) => {
          const l = lineups.find((y) => y.day === id && y.user === x.user)!
          return { manager: nameOf(x.user), is_me: x.user === session?.userId, player_ids: l.player_ids, captain: l.captain,
                   points: x.points, rank: ranks[i] }
        }).sort((a, b) => a.rank - b.rank || a.manager.localeCompare(b.manager)),
        n_lineups: lineups.filter((l) => l.day === id).length,
      }
      return delay(page)
    },
    fantasyStandings(season = null) {
      const days = fDays.filter((d) => d.status === 'open' && (!season || d.season === season))
        .map((d) => ({ d, st: stateOf(d) })).filter((x) => x.st.locked)
        .map(({ d, st }) => ({ locks_at: st.locks_at!, final: st.final,
                               scores: dayScores(d).map((x) => ({ manager: nameOf(x.user), points: x.points })) }))
      const me = nameOf(session?.userId ?? '')
      return delay(standings(days).map((r) => ({ ...r, is_me: r.manager === me })))
    },
    async saveLineup(id, playerIds, captain) {
      const d = fDays.find((x) => x.id === id)
      if (!d || d.status !== 'open') throw new Error('this match day is not open')
      if (lockedNow(id)) throw new Error('this match day is locked')
      if (nameOf(session!.userId) === '?') throw new Error('choose your manager name first')
      const playing = dayFixtures(id).filter((f) => !f.cancelled).map((f) => f.id)
      const inDay = fxPlayers.filter((fp) => playing.includes(fp.fixture_id)).map((fp) => fp.player_id)
      const problem = lineupProblem(d, playerIds, captain, (p) => (inDay.includes(p) ? prices.get(`${id}:${p}`)?.price : undefined))
      if (problem) throw new Error(problem)
      const row = { day: id, user: session!.userId, player_ids: playerIds, captain, updated_at: new Date().toISOString() }
      const i = lineups.findIndex((l) => l.day === id && l.user === row.user)
      if (i >= 0) lineups[i] = row
      else lineups.push(row)
    },
    async setMyName(name) {
      const v = name.trim()
      if (v.length < 2 || v.length > 30) throw new Error('a name has 2 to 30 characters')
      if (profiles.some((p) => p.user_id !== session?.userId && p.display_name?.toLowerCase() === v.toLowerCase()))
        throw new Error('that name is taken')
      profiles.find((p) => p.user_id === session?.userId)!.display_name = v
      return v
    },
    fantasyDayRows: () => delay(isAdmin() ? [...fDays].sort((a, b) => b.id - a.id) : fDays.filter((d) => d.status === 'open')),
    async createFantasyDay(day) {
      adminOnly()
      if (fDays.some((d) => d.season === day.season && d.name === day.name)) throw new Error('fantasy_match_days_season_name_key')
      const row: FantasyDay = { ...day, id: Math.max(0, ...fDays.map((d) => d.id)) + 1, status: 'draft', opened_at: null }
      fDays.push(row)
      return structuredClone(row)
    },
    async updateFantasyDay(id, patch) {
      adminOnly()
      const d = fDays.find((x) => x.id === id)!
      if (d.status === 'open' && (['squad_size', 'budget', 'captain_multiplier'] as const).some((k) => k in patch && patch[k] !== d[k]))
        throw new Error('the rules of an open match day are fixed')
      Object.assign(d, patch)
    },
    async deleteFantasyDay(id) {
      adminOnly()
      if (fDays.find((d) => d.id === id)?.status !== 'draft') throw new Error('only a draft match day can be deleted')
      fDays.splice(fDays.findIndex((d) => d.id === id), 1)
      for (const f of dayFixtures(id)) fixtures.splice(fixtures.indexOf(f), 1)
    },
    fantasyFixtures: (dayId) => delay(fixtures.filter((f) => (dayId === undefined || f.match_day_id === dayId) && seeDay(fDays.find((d) => d.id === f.match_day_id)))
      .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at))),
    fixturePlayers: (ids) => delay(fxPlayers.filter((fp) => ids.includes(fp.fixture_id))),
    async addFixture(dayId, scheduledAt, venue, list) {
      adminOnly()
      if (lockedNow(dayId)) throw new Error('the match day is locked')
      for (const team of ['A', 'B'] as Team[]) if (list.filter((p) => p.team === team).length > 2) throw new Error('a side has two players')
      if (new Set(list.map((p) => p.player_id)).size !== list.length) throw new Error('fantasy_fixture_players_pkey')
      const id = Math.max(0, ...fixtures.map((f) => f.id)) + 1
      fixtures.push({ id, match_day_id: dayId, scheduled_at: scheduledAt, venue, match_id: null, fantasy_published: false, cancelled: false })
      fxPlayers.push(...list.map((p) => ({ ...p, fixture_id: id })))
      if (fDays.find((d) => d.id === dayId)!.status === 'open')
        for (const p of list) if (!prices.has(`${dayId}:${p.player_id}`)) prices.set(`${dayId}:${p.player_id}`, { price: priceOf(dayId, p.player_id), is_override: false })
    },
    async updateFixture(id, patch) {
      adminOnly()
      const f = fixtures.find((x) => x.id === id)!
      if (patch.scheduled_at && patch.scheduled_at !== f.scheduled_at && lockedNow(f.match_day_id)) throw new Error('the match day is locked')
      if (patch.cancelled && f.fantasy_published) throw new Error('fantasy_fixtures_published_needs_match')
      Object.assign(f, patch)
    },
    async deleteFixture(id) {
      adminOnly()
      const f = fixtures.find((x) => x.id === id)!
      if (fDays.find((d) => d.id === f.match_day_id)!.status === 'open') throw new Error('the match day is open: cancel the fixture instead')
      fixtures.splice(fixtures.indexOf(f), 1)
    },
    async setFantasyPrice(dayId, playerId, price) {
      adminOnly()
      if (fDays.find((d) => d.id === dayId)?.status !== 'draft') throw new Error('prices are fixed once the match day is open')
      if (price === null) prices.delete(`${dayId}:${playerId}`)
      else prices.set(`${dayId}:${playerId}`, { price: Math.round(price * 2) / 2, is_override: true })
    },
    async openFantasyDay(dayId) {
      adminOnly()
      const d = fDays.find((x) => x.id === dayId)!
      if (d.status !== 'draft') throw new Error('the match day is already open')
      if (!dayPlayerIds(dayId).length) throw new Error('add the fixtures and their players first')
      if (dayState('open', dayFixtures(dayId), new Date()).locked) throw new Error('its first match has already started')
      for (const p of dayPlayerIds(dayId)) if (!prices.has(`${dayId}:${p}`)) prices.set(`${dayId}:${p}`, { price: priceOf(dayId, p), is_override: false })
      d.status = 'open'
      d.opened_at = new Date().toISOString()
    },
    async linkFixtureMatch(id, matchId) {
      adminOnly()
      const f = fixtures.find((x) => x.id === id)!
      if (matchId === null) {
        Object.assign(f, { match_id: null, fantasy_published: false })
        return mismatch(f)
      }
      if (f.cancelled) throw new Error('the fixture was cancelled')
      if (fixtures.some((x) => x.id !== id && x.match_id === matchId)) throw new Error('fantasy_fixtures_match_id_key')
      Object.assign(f, { fantasy_published: f.fantasy_published && f.match_id === matchId, match_id: matchId })
      return mismatch(f)
    },
    async fixtureMismatch(id) {
      return mismatch(fixtures.find((x) => x.id === id)!)
    },
    async publishFixtureToFantasy(id, on) {
      adminOnly()
      const f = fixtures.find((x) => x.id === id)!
      if (on) {
        if (f.cancelled) throw new Error('the fixture was cancelled')
        if (f.match_id === null) throw new Error('link the fixture to its match first')
        if (byId(f.match_id)?.match.status !== 'published') throw new Error('publish the match first')
      }
      f.fantasy_published = on
    },
  }
}
