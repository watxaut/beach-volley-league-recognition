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
  }
  history: HistoryRow[]
  can_see_analytics: boolean
  analytics: {
    kill_rate: number | null
    attack_error_rate: number | null
    ace_rate: number | null
    serve_error_rate: number | null
    attack_zones: Record<string, number>
    landings: { x: number | null; y: number; in: boolean | null; outcome: string | null; source: string }[]
    touch_depths: { action: string; y: number }[]
  } | null
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
