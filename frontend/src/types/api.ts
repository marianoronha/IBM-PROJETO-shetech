// Tipos compartilhados entre Guardião e BB Decision

// ---- Guardião ----

export interface RiskSignal {
  signal_id: string
  label: string
  description: string
  evidence: string
}

export interface Anomaly {
  anomaly_id: string
  label: string
  description: string
  score_delta: number
  criterion: string
}

export interface RuleTriggered {
  rule_id: string
  triggered: boolean
  reason: string
}

export interface Intervention {
  paused: boolean
  pix_flow: boolean           // true = fluxo (b): Pix pausado com botão de atendente
  pause_is_temporary: boolean
  scam_type: string | null
  scam_name: string | null
  how_it_works: string | null
  how_applied: string | null
  alert_signals: string[]
  next_step: string
  language_profile: string
  language_profile_label: string
  user_control_note: string
}

export interface GuardiaoResponse {
  risk_score: number
  risk_label: 'baixo' | 'médio' | 'alto' | 'crítico'
  signals: RiskSignal[]
  profile_found: boolean
  anomalies: Anomaly[]
  level1_score: number
  level2_score_delta: number
  requires_intervention: boolean
  requires_human_review: boolean
  rules_triggered: RuleTriggered[]
  intervention: Intervention | null
  intervention_message: string
  followup_message: string
  input_channel: string
  language_profile: string
  transaction_id_analyzed: string | null
}

export interface GuardiaoRequest {
  message: string
  user_id?: string
  input_channel?: string
  transaction_id?: string
  language_profile?: 'standard' | 'low'
  monitoring_consent?: boolean
}

// ---- BB Decision ----

export interface PathSummary {
  label: string
  data: Record<string, unknown>
}

export interface BBDecisionResponse {
  scenario_type: string
  question_understood: string
  current_path: PathSummary
  alternative_path: PathSummary
  delta: Record<string, unknown>
  warnings: string[]
  assumptions: string[]
  narrative: string
  disclaimer: string
  clarification_needed: boolean
  clarification_question: string | null
}

export interface BBDecisionRequest {
  question: string
  user_id?: string
  language_profile?: 'standard' | 'low'
  simulation_consent?: boolean
}

// ---- Erros de API ----

export interface ApiError {
  error: string
  code: string
}
