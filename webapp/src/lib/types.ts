// Row shapes of the Supabase schema (supabase/migrations/20261006120000_init.sql).
// Kept by hand: the schema is small; `supabase gen types typescript` can
// replace this file once the project exists.

export type Team = 'A' | 'B'
export type Slot = 'P1A' | 'P2A' | 'P1B' | 'P2B'
export type MatchStatus = 'draft' | 'published' | 'hidden'
export type Role = 'admin' | 'viewer'

export interface Profile {
  user_id: string
  email: string | null
  role: Role
  display_name: string | null
}

export interface Player {
  id: number
  display_name: string
  user_id: string | null
  handedness: 'left' | 'right' | null
  preferred_side: 'left' | 'right' | null
  profile_public: boolean
  active: boolean
}

export interface Match {
  id: number
  match_key: string
  title: string | null
  venue: string | null
  season: string | null
  status: MatchStatus
  detail_public: boolean
  match_date: string
  start_time: string | null
  points_to_win: number | null
  score_a: number | null
  score_b: number | null
  winner_team: Team | null
  n_points: number | null
  set_complete: boolean | null
  duration_s: number | null
  checks: MatchChecks | null
  updated_at: string
}

export interface MatchChecks {
  points?: number
  set_complete?: boolean
  undecided_points?: number[]
  side_switch_after_point?: number[]
  switch_blocks_ok?: boolean
  flagged_points?: Record<string, string[]>
}

export interface Participant {
  match_id: number
  slot: Slot
  team: Team
  player_id: number | null
  thumb_path: string | null
}

export interface BoxRow {
  slot: Slot
  team: Team
  player_id: number | null
  display_name: string | null
  serves: number
  aces: number
  serve_errors: number
  digs: number
  sets: number
  assists: number
  attacks: number
  kills: number
  attack_errors: number
  handling_errors: number
  blocks: number
  fantasy: number
  breakdown: { rule: string; label: string; count: number; points: number }[]
}

export interface PointRow {
  match_id: number
  point_no: number
  set_no: number
  start_frame: number
  end_frame: number
  serving_team: Team | null
  server_slot: Slot | null
  near_team: Team | null
  winner_team: Team | null
  winner_source: string | null
  end_kind: string | null
  score_a_after: number
  score_b_after: number
  flags: string[]
}

export type ActionName = 'serve' | 'dig' | 'set' | 'spike' | 'overpass' | 'block' | 'ball_handling'

export interface ActionRow {
  match_id: number
  point_no: number
  seq: number
  frame: number
  slot: Slot | null
  team: Team | null
  action: ActionName
  outcome: 'ace' | 'kill' | 'error' | null
  is_assist: boolean
  observed: boolean
}

export interface LeaderRow {
  player_id: number
  display_name: string
  matches: number
  wins: number
  fantasy: number
  kills: number
  aces: number
  digs: number
  assists: number
  blocks: number
  errors: number
  attacks: number
  attack_errors: number
  serves: number
  points_played: number
  fantasy_per_21: number | null
}

export interface HistoryRow {
  match_id: number
  match_key: string
  match_date: string
  start_time: string | null
  title: string | null
  venue: string | null
  season: string | null
  score_a: number | null
  score_b: number | null
  team: Team
  slot: Slot
  won: boolean | null
  fantasy: number
  kills: number
  aces: number
  digs: number
  assists: number
  blocks: number
  serves: number
  attacks: number
  errors: number
  attack_errors: number
  serve_errors: number
  n_points: number | null
}

/** Kills and errors out of `n` attempts (an attack split, a rally split). */
export interface Tally {
  n: number
  kills: number
  errors: number
}

/** Points won out of points played. */
export interface WonOf {
  n: number
  won: number
}

export interface PlayerAnalytics {
  n_attacks: number
  n_kills: number
  n_attack_errors: number
  n_serves: number
  n_aces: number
  n_serve_errors: number
  kill_rate: number | null
  attack_error_rate: number | null
  ace_rate: number | null
  serve_error_rate: number | null
  /** N4: attacks off the reception (first possession) vs in transition. */
  hit: { reception: Tally; transition: Tally }
  /** N1: side-out / break-point. `own_serve` = points served by the player;
   * `team_*` = the player's team in the matches of the window. */
  rally: { own_serve: WonOf; team_serving: WonOf; team_receiving: WonOf }
  /** N2: serves aimed at the player's team and who took them. */
  serve_in: { opp_serves: number; team_credited: number; mine: number }
  serve_out: { serves: number; unseen: number; to: { player_id: number | null; display_name: string; n: number }[] }
  /** N3: what the player's receptions became (a pass-quality proxy). */
  reception: { n: number; spike: number; overpass: number; error: number; none: number; first_ball_kills: number }
  /** Progress: one entry per attack / serve, oldest first. */
  attack_series: { d: string; r: 'kill' | 'error' | 'other' }[]
  serve_series: { d: string; r: 'ace' | 'error' | 'other' }[]
  attack_zones: Record<string, number>
  landings: Landing[]
  touch_depths: { action: string; y: number }[]
}

export interface PlayerProfile {
  player: {
    id: number
    display_name: string
    profile_public: boolean
    is_me: boolean
    handedness: string | null
    preferred_side: string | null
  }
  totals: {
    matches: number
    wins: number
    fantasy: number
    kills: number
    aces: number
    digs: number
    assists: number
    blocks: number
    errors: number
    serves: number
    attacks: number
    attack_errors: number
    serve_errors: number
    points_played: number
    fantasy_per_21: number | null
  }
  /** The newest five matches overall (oldest first) and the all-time mean:
   * the window does not apply to form. */
  form: { n: number; avg5: number | null; avg_all: number | null; last5: number[] }
  history: HistoryRow[]
  can_see_analytics: boolean
  analytics: PlayerAnalytics | null
}

/** One player's line in a match report. The box-score numbers are league tier;
 * `hit`, `own_serve` and `avg` are analytics tier and come back null when the
 * reader may not see them (`match_report`, migration 20261007130000). `avg` is
 * the player's average over their OTHER published matches (`avg.matches` of
 * them; nulls inside when there are none). */
export interface ReportPlayer {
  slot: Slot
  team: Team
  player_id: number | null
  display_name: string | null
  fantasy: number
  fantasy_per_21: number | null
  serves: number
  aces: number
  serve_errors: number
  digs: number
  sets: number
  assists: number
  attacks: number
  kills: number
  attack_errors: number
  handling_errors: number
  hit: { reception: Tally; transition: Tally } | null
  own_serve: WonOf | null
  avg: { matches: number; fantasy: number | null; kills: number | null; aces: number | null;
         digs: number | null; assists: number | null; errors: number | null; attacks: number | null } | null
}

export interface MatchReport {
  match_id: number
  /** N1 per team: serving = break-point, receiving = side-out. */
  teams: Partial<Record<Team, { serve_n: number; serve_won: number; recv_n: number; recv_won: number }>>
  players: ReportPlayer[]
  /** N2: serves of each team and the credited receiver of each. A team is
   * missing when the reader may not see both players of the receiving pair. */
  serve_targets: Partial<Record<Team, { to: Partial<Record<Slot, number>>; unseen: number }>>
  /** F3: fantasy per point and slot; null unless the play-by-play is visible. */
  timeline: { point_no: number; slot: Slot; pts: number }[] | null
}

/** A time filter, as the database takes it. `lastN` counts the newest N
 * published matches of the reader's scope (league / the player's own). */
export interface WindowParams {
  season: string | null
  from: string | null
  to: string | null
  lastN: number | null
}

/** One attack and where it came down, in the attacker's frame: x 0..8 from
 * their left sideline, y 8 (net) .. 16 (the opponents' baseline). `ex` / `ey`
 * are how far off the spot may be, in metres across / along the court (about
 * one sigma, best effort). The fields after `source` are missing on a
 * database that has not run the landing_confidence migration. */
export interface Landing {
  x: number | null
  y: number | null
  in: boolean | null
  outcome: string | null
  source: string | null
  ex?: number | null
  ey?: number | null
  result?: 'kill' | 'dug' | 'out' | 'net' | 'error' | null
  zone?: number | null
  type?: string | null
}

export interface MatchSource {
  match_id: number
  video_filename: string | null
  video_url: string | null
  video_sha256: string | null
  fps: number | null
  width: number | null
  height: number | null
}

export interface Publication {
  id: number
  match_id: number
  revision: number
  result: 'applied' | 'unchanged'
  content_sha256: string
  pipeline_version: string | null
  git_dirty: boolean | null
  bundle_path: string | null
  video_url: string | null
  n_points: number | null
  n_actions: number | null
  score: string | null
  published_by: string | null
  published_at: string
  notes: string | null
}

export interface Ruleset {
  id: number
  name: string
  description: string | null
  is_active: boolean
}

export interface FantasyRule {
  ruleset_id: number
  rule_key: string
  label: string
  actions: string[]
  outcome: string | null
  assist_only: boolean
  points: number
  sort_order: number
}

export type MatchPatch = Partial<Pick<Match, 'title' | 'venue' | 'season' | 'status' | 'detail_public'>>
export type PlayerPatch = Partial<Pick<Player, 'display_name' | 'user_id' | 'handedness' |
  'preferred_side' | 'active'>>

export interface Session {
  userId: string
  email: string
}
