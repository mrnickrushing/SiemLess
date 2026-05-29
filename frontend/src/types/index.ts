export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type AlertStatus = 'open' | 'investigating' | 'resolved' | 'false_positive';
export type IndicatorType = 'ip' | 'domain' | 'hash' | 'url' | 'email' | 'user_agent';

export interface SecurityEvent {
  id: string;
  timestamp: string;
  source_ip: string | null;
  destination_ip: string | null;
  source_port: number | null;
  destination_port: number | null;
  hostname: string | null;
  username: string | null;
  event_type: string;
  severity: Severity;
  category: string;
  log_type: string;
  message: string;
  raw_log: string | null;
  parsed_fields: Record<string, unknown> | null;
  tags: string[];
  rule_id: string | null;
  alert_id: string | null;
  ingested_at: string;
  mitre_tactic: string | null;
  mitre_technique: string | null;
  risk_score?: number;
  normalized_fields?: Record<string, unknown> | null;
}

export interface Alert {
  id: string;
  title: string;
  description: string | null;
  severity: Severity;
  status: AlertStatus;
  rule_id: string | null;
  rule_name: string | null;
  event_ids: string[];
  source_ips: string[];
  affected_users: string[];
  affected_hosts: string[];
  mitre_tactic: string | null;
  mitre_technique: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  assigned_to: string | null;
  notes: string | null;
  false_positive_reason: string | null;
  event_count: number;
  escalated_at: string | null;
  sla_breach_at: string | null;
  hit_count?: number;
  risk_score?: number;
  dedup_key?: string;
}

export interface SavedSearch {
  id: string;
  name: string;
  description: string | null;
  query: string;
  created_at: string;
  updated_at: string;
}

export interface WatchlistEntry {
  id: string;
  entry_type: 'ip' | 'user' | 'hash' | 'domain';
  value: string;
  label: string | null;
  tags: string[] | null;
  notes: string | null;
  created_at: string;
}

export interface CorrelationRule {
  id: string;
  name: string;
  description: string | null;
  severity: Severity;
  category: string;
  condition: Record<string, unknown>;
  threshold: number;
  time_window: number;
  enabled: boolean;
  mitre_tactic: string | null;
  mitre_technique: string | null;
  alert_title_template: string | null;
  alert_description_template: string | null;
  created_at: string;
  updated_at: string;
  trigger_count: number;
  last_triggered: string | null;
}

export interface ThreatIndicator {
  id: string;
  type: IndicatorType;
  value: string;
  confidence: number;
  severity: Severity;
  source: string;
  description: string | null;
  tags: string[];
  first_seen: string;
  last_seen: string;
  active: boolean;
  context: Record<string, unknown> | null;
}

export interface StatsOverview {
  total_events_today: number;
  open_alerts: number;
  active_rules: number;
  threats_detected: number;
  events_last_hour: number;
  critical_alerts: number;
  high_alerts: number;
}

export interface EventsOverTime {
  timestamp: string;
  count: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface TopSource {
  source_ip: string;
  count: number;
  severity_breakdown: Record<string, number>;
}

export interface CategoryDistribution {
  category: string;
  count: number;
}

export interface SeverityDistribution {
  severity: string;
  count: number;
}

export interface DashboardStats {
  overview: StatsOverview;
  events_over_time: EventsOverTime[];
  top_sources: TopSource[];
  category_distribution: CategoryDistribution[];
  severity_distribution: SeverityDistribution[];
  recent_alerts: Alert[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface EventFilters {
  page?: number;
  page_size?: number;
  severity?: Severity;
  category?: string;
  log_type?: string;
  source_ip?: string;
  hostname?: string;
  start_time?: string;
  end_time?: string;
  search?: string;
}

export interface AlertFilters {
  page?: number;
  page_size?: number;
  status?: AlertStatus;
  severity?: Severity;
}

export interface RuleFormData {
  name: string;
  description: string;
  severity: Severity;
  category: string;
  condition: Record<string, unknown>;
  threshold: number;
  time_window: number;
  enabled: boolean;
  mitre_tactic: string;
  mitre_technique: string;
  alert_title_template: string;
  alert_description_template: string;
}

export interface ThreatCheckResult {
  matched: boolean;
  indicator: ThreatIndicator | null;
}

export interface ThreatIndicatorFormData {
  type: IndicatorType;
  value: string;
  confidence: number;
  severity: Severity;
  source: string;
  description: string;
  tags: string[];
}

export interface AlertUpdateData {
  status?: AlertStatus;
  assigned_to?: string;
  notes?: string;
  false_positive_reason?: string;
}

// ── Case Management ──────────────────────────────────────────────
export type CaseStatus = 'open' | 'investigating' | 'resolved' | 'closed';

export interface Case {
  id: string;
  title: string;
  description: string | null;
  status: CaseStatus;
  severity: Severity;
  assigned_to: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  tags: string[] | null;
  linked_alert_count: number;
  linked_event_count: number;
}

export interface CaseComment {
  id: string;
  case_id: string;
  author: string;
  body: string;
  created_at: string;
}

export interface CaseArtifact {
  id: string;
  case_id: string;
  artifact_type: string;
  value: string;
  description: string | null;
  added_by: string;
  created_at: string;
}

export interface CaseTimelineItem {
  ts: string;
  kind: 'event' | 'alert' | 'comment' | 'artifact';
  id: string;
  summary: string;
}

export interface CaseCreate {
  title: string;
  description?: string;
  severity: Severity;
  assigned_to?: string;
  tags?: string[];
}

// ── Compliance ───────────────────────────────────────────────────
export type ComplianceFramework = 'pci_dss' | 'hipaa' | 'gdpr' | 'soc2' | 'nist';
export type ReportStatus = 'pending' | 'completed' | 'failed';

export interface ComplianceReport {
  id: string;
  framework: ComplianceFramework;
  status: ReportStatus;
  generated_at: string | null;
  created_at: string;
  period_start: string | null;
  period_end: string | null;
  summary: Record<string, unknown> | null;
  error: string | null;
}

// ── UEBA ─────────────────────────────────────────────────────────
export interface UserBehaviorProfile {
  id: string;
  username: string;
  typical_hours: number[] | null;
  known_source_ips: string[] | null;
  event_count_30d: number;
  last_activity: string | null;
  updated_at: string;
}

export interface UEBAAnomaly {
  id: string;
  username: string;
  anomaly_type: string;
  score: number;
  detail: Record<string, unknown> | null;
  event_id: string | null;
  detected_at: string;
  acknowledged: boolean;
}

// ── Cloud Connectors ─────────────────────────────────────────────
export type ConnectorType = 'aws_cloudtrail' | 'azure_activity' | 'gcp_logging';

export interface CloudConnector {
  id: string;
  name: string;
  connector_type: ConnectorType;
  config: Record<string, unknown>;
  enabled: boolean;
  last_polled_at: string | null;
  last_error: string | null;
  events_ingested: number;
  created_at: string;
}

// ── Retention ────────────────────────────────────────────────────
export interface RetentionPolicy {
  id: string;
  name: string;
  hot_days: number;
  cold_days: number;
  delete_after_cold: boolean;
  enabled: boolean;
  created_at: string;
}

// ── Playbooks ────────────────────────────────────────────────────
export interface PlaybookStep {
  action: string;
  params: Record<string, unknown>;
}

export interface Playbook {
  id: string;
  name: string;
  description: string | null;
  trigger_on: string;
  conditions: Record<string, unknown> | null;
  steps: PlaybookStep[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
  run_count: number;
  last_run_at: string | null;
}

export interface PlaybookRun {
  id: string;
  playbook_id: string;
  triggered_by: string | null;
  started_at: string;
  finished_at: string | null;
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

// ── Assets ───────────────────────────────────────────────────────
export interface Asset {
  id: string;
  hostname: string;
  ip_addresses: string[] | null;
  os_type: string | null;
  os_version: string | null;
  asset_type: string;
  first_seen: string;
  last_seen: string;
  tags: string[] | null;
  criticality: string;
  cve_count: number;
}

export interface AssetSoftware {
  id: string;
  asset_id: string;
  name: string;
  version: string | null;
  cpe: string | null;
  last_scanned: string;
}

export interface AssetVulnerability {
  id: string;
  asset_id: string;
  cve_id: string;
  cvss_score: number | null;
  description: string | null;
  severity: string;
  published_at: string | null;
  fetched_at: string;
}

// ── Integrations ─────────────────────────────────────────────────
export interface IntegrationConfig {
  id: string;
  name: string;
  integration_type: string;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
}

// ── Threat Feeds ─────────────────────────────────────────────────
export interface ThreatFeedConnector {
  id: string;
  name: string;
  feed_type: string;
  url: string;
  api_key: string | null;
  last_pulled_at: string | null;
  pull_interval_hours: number;
  enabled: boolean;
  indicator_count: number;
  last_error: string | null;
  created_at: string;
}

// ── RBAC ─────────────────────────────────────────────────────────
export interface OrgUser {
  id: string;
  org_id: string;
  username: string;
  email: string | null;
  role: string;
  created_at: string;
}

export interface APIToken {
  id: string;
  username: string;
  description: string | null;
  expires_at: string | null;
  created_at: string;
  raw_token?: string;
}
