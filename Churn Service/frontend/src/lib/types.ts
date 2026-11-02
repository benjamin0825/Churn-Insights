export type RiskTier = 'high' | 'medium' | 'low'

export interface Organization {
  id: number
  name: string
  offer_cost: number
  retention_success_rate: number
  months_of_value: number
}

export interface User {
  id: number
  name: string
  email: string
  role: 'owner' | 'analyst'
  is_admin: boolean
  organization: Organization
}

export interface TokenResponse {
  access_token: string
  expires_at: string
  user: User
}

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface Job {
  id: number
  kind: 'demo' | 'train' | 'score' | 'monitor'
  status: JobStatus
  message: string
  params: Record<string, unknown>
  result: Record<string, unknown>
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface DataStatus {
  has_data: boolean
  has_model: boolean
  has_scores: boolean
  dataset: {
    id: number
    source: 'upload' | 'demo'
    created_at: string
    summary: Record<string, number | string>
    warnings: string[]
  } | null
  active_job: Job | null
  /** The most recent job of any kind, finished or not. */
  last_job: Job | null
  training_profiles: string[]
}

export interface Segment {
  segment: string
  customers: number
  avg_probability: number
  high_risk: number
  revenue_at_risk: number
}

export interface Dashboard {
  as_of_week: number
  scored_at: string
  model_version: number
  kpis: {
    customers: number
    high_risk: number
    recommended_for_offer: number
    expected_churners_8w: number
    revenue_at_risk: number
    avg_churn_probability: number
  }
  tiers: { tier: RiskTier; customers: number; revenue_at_risk: number }[]
  by_region: Segment[]
  by_contract: Segment[]
  by_plan: Segment[]
  churn_trend: { week: number; churn_rate: number; customers: number }[]
  drivers: { feature: string; importance: number }[]
  model: Record<string, number | null>
  drift: { status: 'stable' | 'warning' | 'alert'; week: string } | null
}

export type MetricFormat = 'money' | 'cents' | 'int' | 'pct'

export interface MetricCardData {
  key: string
  label: string
  format: MetricFormat
  good_when: 'up' | 'down'
  value: number
  from: number | null
  change: number | null
  flow: boolean
  series: { date: string; value: number }[]
}

export interface ActivityEvent {
  week: number
  weeks_ago: number
  date: string
  kind: 'cancelled' | 'subscribed' | 'cancel_request' | 'paid_late'
  customer_id: number
  /** Display name; set for demo data only, so real customers are never given invented names. */
  name?: string | null
  amount: number | null
  detail: string
}

export interface Overview {
  as_of: string
  period: { weeks: number; start: string; end: string }
  cards: MetricCardData[]
  breakdown: {
    weeks: number
    new_customers: number
    new_mrr: number
    expansions: number
    expansion_mrr: number
    contractions: number
    contraction_mrr: number
    cancellations: number
    churned_mrr: number
    net_mrr_change: number
  }
  activity: ActivityEvent[]
  forecast: {
    model_version: number
    expected_churners: number
    revenue_at_risk: number
    high_risk: number
    medium_risk: number
    recommended_for_offer: number
    customers: number
  } | null
}

export interface CustomerRow {
  customer_id: number
  /** Display name; set for demo data only, so real customers are never given invented names. */
  name?: string | null
  churn_probability: number
  risk_tier: RiskTier
  target_for_retention: boolean
  expected_revenue_at_risk: number
  region: string
  plan: string
  contract_type: string
  internet_service: string
  tenure_weeks: number
  current_charge: number
  top_reasons: string
}

export interface CustomerPage {
  total: number
  page: number
  page_size: number
  as_of_week: number
  model_version: number
  facets: { region: string[]; plan: string[]; contract_type: string[] }
  items: CustomerRow[]
}

export interface Reason {
  feature: string
  description: string
  value: number | string | null
  impact: number
  direction: 'increases risk' | 'decreases risk'
}

export interface CustomerDetail {
  customer_id: number
  /** Display name; set for demo data only, so real customers are never given invented names. */
  name?: string | null
  as_of_week: number
  model_version: number
  score: { churn_probability: number; risk_tier: RiskTier; target_for_retention: boolean; expected_revenue_at_risk: number }
  profile: Record<string, string | number | null>
  reasons: Reason[]
  features: { group: string; items: { name: string; value: number | null }[] }[]
  history: {
    usage: { week: number; date: string; sessions: number; minutes: number; data_gb: number }[]
    billing: { week: number; date: string; amount: number; discount_pct: number; paid_late: boolean; days_late: number }[]
    tickets: { week: number; date: string; category: string; text: string; resolution_hours: number; csat: number }[]
  }
}

export interface CampaignParams {
  offer_cost: number
  retention_success_rate: number
  months_of_value: number
  budget: number | null
  max_customers: number | null
  risk_tiers: RiskTier[]
  min_probability: number
}

export interface CampaignSummary {
  customers_scored: number
  eligible_customers: number
  targeted_customers: number
  campaign_cost: number
  expected_revenue_saved: number
  expected_profit: number
  roi: number | null
  expected_customers_retained: number
  share_of_expected_churners_reached: number
  average_churn_probability: number | null
}

export interface CampaignTarget {
  customer_id: number
  /** Display name; set for demo data only, so real customers are never given invented names. */
  name?: string | null
  churn_probability: number
  risk_tier: RiskTier
  expected_value: number
  expected_revenue_saved: number
  current_charge: number
  region: string
  plan: string
  contract_type: string
  tenure_weeks: number
  top_reasons: string | null
}

export interface CampaignPreview {
  summary: CampaignSummary
  curve: { customers: number; expected_profit: number; cost: number }[]
  as_of_week: number
  top_targets: CampaignTarget[]
}

export interface Campaign {
  id: number
  name: string
  created_at: string
  model_version: number
  as_of_week: number
  params: CampaignParams
  summary: CampaignSummary
  targets_preview?: CampaignTarget[]
}

export interface ModelVersionRow {
  version: number
  stage: 'production' | 'staging' | 'archived'
  created_at: string
  test_roc_auc: number | null
  test_average_precision: number | null
  test_brier: number | null
  test_campaign_profit: number | null
  members: string
}

export interface ModelList {
  production: number | null
  versions: ModelVersionRow[]
  training_profiles: string[]
}

export interface LeaderboardRow {
  model: string
  weight: number | null
  val_roc_auc: number
  test_roc_auc: number
  test_average_precision: number
  trials: number | null
}

export interface ModelDetail {
  version: number
  is_production: boolean
  description: Record<string, unknown>
  test: Record<string, number>
  validation: Record<string, number>
  leaderboard: LeaderboardRow[]
  split: Record<string, number[]>
  rows: Record<string, number>
  promotion: { reason?: string }
  global_importance: Record<string, number>
}

export interface DriftFeature {
  feature: string
  kind: string
  psi: number
  ks_pvalue: number | null
  status: 'stable' | 'warning' | 'alert'
  reference_mean: number | null
  current_mean: number | null
}

export interface DriftReport {
  status: 'stable' | 'warning' | 'alert'
  n_reference: number
  n_current: number
  prediction: { psi: number; status: string; reference_mean: number; current_mean: number } | null
  features: DriftFeature[]
  segments: (DriftFeature & { segment: string })[] | null
  report_file: string
}
