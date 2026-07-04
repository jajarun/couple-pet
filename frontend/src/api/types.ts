export interface AuthUser {
  id: number
  nickname: string
}
export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}
export interface Stats {
  grievance: number
  dogfood: number
  miss: number
  intimacy: number
}
export type EventKind = 'action' | 'ai_reaction' | 'real_response' | 'system'
export interface GameEvent {
  id: number
  couple_id: number
  actor_user_id: number | null
  kind: EventKind
  action_type: string | null
  content: string
  parent_event_id: number | null
  created_at: string
}
export interface Avatar {
  id: number
  couple_id: number
  subject_user_id: number
  keeper_user_id: number
  name: string
  appearance: Record<string, unknown>
  persona: Record<string, unknown>
}
export type CoupleState =
  | { couple_id: number; status: 'active'; partner_id: number }
  | { couple_id: number; status: 'pending'; pair_code: string }
  | { couple_id: null; status: 'none' }
export interface ActionBundle {
  events: GameEvent[]
  stats: Stats
}
export interface FeedResponse {
  events: GameEvent[]
  stats: Stats
}
