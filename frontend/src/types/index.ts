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
