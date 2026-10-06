// The only module that talks to Supabase. Every page goes through `Api`, so
// the demo mode (VITE_DEMO=1, fixtures in demo.ts) can stand in for it.
//
// Access rules live in the database (RLS + security-definer functions); the
// client never decides what a user may see -- it asks, and gets what the
// policies allow (e.g. `points`/`actions` come back empty for a match the
// viewer did not play in unless an admin opened its detail).
import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import type {
  ActionRow, BoxRow, FantasyRule, LeaderRow, Match, MatchPatch, MatchSource, Participant,
  Player, PlayerPatch, PlayerProfile, PointRow, Profile, Publication, Role, Ruleset, Session,
  Slot,
} from './types'

export interface Api {
  // auth
  getSession(): Promise<Session | null>
  onAuthChange(cb: (s: Session | null) => void): () => void
  sendCode(email: string): Promise<void>
  verifyCode(email: string, code: string): Promise<void>
  signOut(): Promise<void>
  // me
  myProfile(userId: string): Promise<Profile | null>
  myPlayer(userId: string): Promise<Player | null>
  setMyPrivacy(isPublic: boolean): Promise<boolean>
  // league reads
  players(): Promise<Player[]>
  matches(): Promise<Match[]>
  match(key: string): Promise<Match | null>
  participants(matchIds: number[]): Promise<Participant[]>
  boxScore(matchId: number): Promise<BoxRow[]>
  points(matchId: number): Promise<PointRow[]>
  actions(matchId: number): Promise<ActionRow[]>
  leaderboard(season: string | null): Promise<LeaderRow[]>
  seasons(): Promise<string[]>
  playerProfile(playerId: number): Promise<PlayerProfile | null>
  // admin
  updateMatch(matchId: number, patch: MatchPatch): Promise<void>
  assignSlot(matchId: number, slot: Slot, playerId: number | null): Promise<void>
  createPlayer(name: string): Promise<Player>
  updatePlayer(playerId: number, patch: PlayerPatch): Promise<void>
  profiles(): Promise<Profile[]>
  setRole(userId: string, role: Role): Promise<void>
  matchSource(matchId: number): Promise<MatchSource | null>
  publications(matchId: number): Promise<Publication[]>
  thumbUrls(paths: string[]): Promise<Record<string, string>>
  bundleUrl(bundlePath: string): Promise<string | null>
  rulesets(): Promise<Ruleset[]>
  rules(rulesetId: number): Promise<FantasyRule[]>
  setRulePoints(rulesetId: number, ruleKey: string, points: number): Promise<void>
  cloneRuleset(fromId: number, name: string): Promise<number>
  activateRuleset(rulesetId: number): Promise<void>
}

// Rows are typed by the `Api` signatures (lib/types.ts mirrors the schema);
// supabase-js is used untyped, so `must` takes the data as unknown and the
// caller's declared return type names it.
type Result = { data: unknown; error: { message: string } | null }

function must<T>(res: Result): T {
  if (res.error) throw new Error(res.error.message)
  return res.data as T
}

/** Friendlier text for the errors people actually hit. */
export function explainError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err)
  if (/signups not allowed|not allowed for otp|user not found/i.test(msg))
    return 'This email has not been invited yet. Ask a league admin to invite you.'
  if (/token has expired|invalid/i.test(msg) && /otp|token/i.test(msg))
    return 'That code is wrong or expired. Request a new one.'
  if (/match_participants_match_id_player_id_key|duplicate key/i.test(msg))
    return 'That player already has another slot in this match.'
  if (/rate limit/i.test(msg)) return 'Too many emails requested. Wait a minute and try again.'
  return msg
}

const MATCH_COLUMNS =
  'id,match_key,title,venue,season,status,detail_public,match_date,start_time,points_to_win,' +
  'score_a,score_b,winner_team,n_points,set_complete,duration_s,checks,updated_at'

export function supabaseApi(url: string, publishableKey: string): Api {
  const sb: SupabaseClient = createClient(url, publishableKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  })
  const toSession = (s: { user: { id: string; email?: string } } | null): Session | null =>
    s ? { userId: s.user.id, email: s.user.email ?? '' } : null

  return {
    async getSession() {
      const { data } = await sb.auth.getSession()
      return toSession(data.session)
    },
    onAuthChange(cb) {
      const { data } = sb.auth.onAuthStateChange((_e, s) => cb(toSession(s)))
      return () => data.subscription.unsubscribe()
    },
    async sendCode(email) {
      const { error } = await sb.auth.signInWithOtp({
        email,
        options: { shouldCreateUser: false, emailRedirectTo: window.location.origin },
      })
      if (error) throw new Error(error.message)
    },
    async verifyCode(email, code) {
      const { error } = await sb.auth.verifyOtp({ email, token: code, type: 'email' })
      if (error) throw new Error(error.message)
    },
    async signOut() {
      await sb.auth.signOut()
    },

    async myProfile(userId) {
      return must(await sb.from('profiles').select('user_id,email,role,display_name')
        .eq('user_id', userId).maybeSingle())
    },
    async myPlayer(userId) {
      return must(await sb.from('players').select('*').eq('user_id', userId).maybeSingle())
    },
    async setMyPrivacy(isPublic) {
      return must(await sb.rpc('set_my_privacy', { p_public: isPublic }))
    },

    async players() {
      return must(await sb.from('players').select('*').order('display_name'))
    },
    async matches() {
      return must(await sb.from('matches').select(MATCH_COLUMNS)
        .order('match_date', { ascending: false }).order('start_time', { ascending: false }))
    },
    async match(key) {
      return must(await sb.from('matches').select(MATCH_COLUMNS).eq('match_key', key).maybeSingle())
    },
    async participants(matchIds) {
      if (!matchIds.length) return []
      return must(await sb.from('match_participants')
        .select('match_id,slot,team,player_id,thumb_path').in('match_id', matchIds))
    },
    async boxScore(matchId) {
      return must(await sb.rpc('match_box_score', { p_match_id: matchId }))
    },
    async points(matchId) {
      return must(await sb.from('points').select('*').eq('match_id', matchId).order('point_no'))
    },
    async actions(matchId) {
      return must(await sb.from('actions')
        .select('match_id,point_no,seq,frame,slot,team,action,outcome,is_assist,observed')
        .eq('match_id', matchId).order('point_no').order('seq'))
    },
    async leaderboard(season) {
      return must(await sb.rpc('leaderboard', { p_season: season }))
    },
    async seasons() {
      const rows: { season: string | null }[] =
        must(await sb.from('matches').select('season').not('season', 'is', null))
      return [...new Set(rows.map((r) => r.season as string))].sort().reverse()
    },
    async playerProfile(playerId) {
      return must(await sb.rpc('player_profile', { p_player_id: playerId }))
    },

    async updateMatch(matchId, patch) {
      must(await sb.from('matches').update(patch).eq('id', matchId))
    },
    async assignSlot(matchId, slot, playerId) {
      must(await sb.from('match_participants').update({ player_id: playerId })
        .eq('match_id', matchId).eq('slot', slot))
    },
    async createPlayer(name) {
      return must(await sb.from('players').insert({ display_name: name }).select('*').single())
    },
    async updatePlayer(playerId, patch) {
      must(await sb.from('players').update(patch).eq('id', playerId))
    },
    async profiles() {
      return must(await sb.from('profiles').select('user_id,email,role,display_name').order('email'))
    },
    async setRole(userId, role) {
      must(await sb.from('profiles').update({ role }).eq('user_id', userId))
    },
    async matchSource(matchId) {
      return must(await sb.from('match_sources').select('*').eq('match_id', matchId).maybeSingle())
    },
    async publications(matchId) {
      return must(await sb.from('match_publications').select('*').eq('match_id', matchId)
        .order('revision', { ascending: false }))
    },
    async thumbUrls(paths) {
      if (!paths.length) return {}
      const { data, error } = await sb.storage.from('match-media').createSignedUrls(paths, 3600)
      if (error) throw new Error(error.message)
      const out: Record<string, string> = {}
      for (const d of data ?? []) if (d.path && d.signedUrl) out[d.path] = d.signedUrl
      return out
    },
    async bundleUrl(bundlePath) {
      const path = bundlePath.replace(/^match-bundles\//, '')
      const { data } = await sb.storage.from('match-bundles').createSignedUrl(path, 600)
      return data?.signedUrl ?? null
    },
    async rulesets() {
      return must(await sb.from('fantasy_rulesets').select('id,name,description,is_active').order('id'))
    },
    async rules(rulesetId) {
      return must(await sb.from('fantasy_rules').select('*').eq('ruleset_id', rulesetId)
        .order('sort_order'))
    },
    async setRulePoints(rulesetId, ruleKey, points) {
      must(await sb.from('fantasy_rules').update({ points })
        .eq('ruleset_id', rulesetId).eq('rule_key', ruleKey))
    },
    async cloneRuleset(fromId, name) {
      return must(await sb.rpc('clone_ruleset', { p_from: fromId, p_name: name }))
    },
    async activateRuleset(rulesetId) {
      must(await sb.rpc('activate_ruleset', { p_ruleset_id: rulesetId }))
    },
  }
}
