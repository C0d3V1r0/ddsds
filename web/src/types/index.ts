// Доменные типы, соответствующие API-ответам сервера

export interface Metrics {
  id: number;
  timestamp: number;
  cpu_total: number;
  cpu_cores: string;
  ram_used: number;
  ram_total: number;
  disk: string;
  network_rx: number;
  network_tx: number;
  load_avg: string;
}

export interface SecurityEvent {
  id: number;
  timestamp: number;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  source_ip: string;
  description: string;
  raw_log: string;
  action_taken: string;
  resolved: number;
  signal_source?: string;
  explanation_code?: string;
  confidence?: 'low' | 'medium' | 'high';
  recommended_action?: string;
  trace_id?: string;
}

export interface BlockedIP {
  id: number;
  ip: string;
  reason: string;
  blocked_at: number;
  expires_at: number | null;
  auto: number;
}

export interface SecurityIncident {
  id: string;
  title: string;
  type: string;
  source_ip: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'new' | 'investigating' | 'resolved';
  event_count: number;
  suppressed_count: number;
  repeat_count: number;
  first_seen: number;
  last_seen: number;
  latest_event_id: number;
  latest_trace_id?: string;
  latest_action_taken?: string;
  signal_source?: string;
  confidence?: 'low' | 'medium' | 'high';
  recommended_action?: string;
  evidence_types: string[];
  summary: string;
  note_count: number;
  status_updated_at: number;
}

export interface IncidentNote {
  id: number;
  incident_id: string;
  incident_type: string;
  source_ip: string;
  note: string;
  status_at_time: 'new' | 'investigating' | 'resolved';
  created_at: number;
}

export interface IncidentProgressionStep {
  timestamp: number;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  action_taken: string;
  description: string;
}

export interface IncidentEvidenceSummaryItem {
  type: string;
  count: number;
}

export interface IncidentResolutionSummary {
  state: string;
  headline: string;
  note: string;
  updated_at: number;
}

export interface IncidentDetail {
  incident: SecurityIncident;
  related_events: SecurityEvent[];
  blocked_ip: BlockedIP | null;
  audit_entries: ResponseAuditEntry[];
  notes: IncidentNote[];
  progression: IncidentProgressionStep[];
  evidence_summary: IncidentEvidenceSummaryItem[];
  resolution_summary: IncidentResolutionSummary;
}

export interface ResponseAuditEntry {
  id: number;
  timestamp: number;
  trace_id: string;
  stage: string;
  status: string;
  event_type: string;
  source_ip: string;
  action: string;
  command: string;
  details: Record<string, unknown>;
}

export interface ServiceInfo {
  name: string;
  status: 'running' | 'stopped' | 'failed';
  pid: number;
  uptime: number;
  updated_at: number;
}

export interface ProcessInfo {
  pid: number;
  name: string;
  cpu: number;
  ram: number;
  start_time?: number;
}

export interface ProcessActionResult {
  status: string;
  pid: number;
  name: string;
}

export interface LogEntry {
  timestamp: number;
  source: string;
  line: string;
  file: string;
}

export interface LogFilters {
  source?: string;
  limit?: number;
  fromTs?: number | null;
  toTs?: number | null;
  query?: string;
  ip?: string;
  eventType?: string;
}

export interface HealthStatus {
  status: string;
  agent: string;
  db: string;
}

export interface RiskFactor {
  code: string;
  weight: number;
  count?: number;
  age_seconds?: number;
}

export interface RiskScore {
  score: number;
  level: 'low' | 'medium' | 'high' | 'critical';
  factors: RiskFactor[];
  updated_at: number;
}

export interface RiskHistoryPoint {
  timestamp: number;
  score: number;
  level: 'low' | 'medium' | 'high' | 'critical';
  factors: RiskFactor[];
}

export interface MlAnomalyDetectorStatus {
  ready: boolean;
  status: 'running' | 'pending' | 'training' | 'insufficient_data' | 'postponed' | 'failed';
  reason_code: string;
  samples_count: number;
  filtered_samples_count: number;
  discarded_samples_count: number;
  required_samples: number;
  event_count: number;
  max_event_count: number;
  maintenance_event_count: number;
  host_profile: string;
  filter_window_seconds: number;
  maintenance_window_seconds: number;
  dataset_quality_score: number;
  dataset_quality_label: 'low' | 'medium' | 'high';
  dataset_noise_label: 'clean' | 'stressed' | 'noisy';
  weighted_event_pressure: number;
  excluded_windows_count: number;
  updated_at: number;
  next_run_at: number | null;
}

export interface MlStatus {
  anomaly_detector: MlAnomalyDetectorStatus;
  attack_classifier: { ready: boolean };
}

export interface SelfProtectionCheck {
  code: string;
  status: 'healthy' | 'warning' | 'failing';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  recommendation: string;
}

export interface SelfProtectionStatus {
  level: 'low' | 'medium' | 'high' | 'critical';
  healthy_count: number;
  warning_count: number;
  failing_count: number;
  checks: SelfProtectionCheck[];
}

export interface DeploymentStatus {
  role: 'primary' | 'standby';
  node_name: string;
  primary_lock_path: string;
  updated_at: number;
  background_tasks_enabled: boolean;
  active_response_enabled: boolean;
  promote_supported: boolean;
  primary_lock_held: boolean;
  primary_lock_info: {
    path: string;
    exists: boolean;
    locked: boolean;
    owner_node_name: string;
    owner_pid: number;
    updated_at: number;
  };
  failover: {
    enabled: boolean;
    primary_api_url: string;
    check_interval: number;
    failure_threshold: number;
    cooloff_seconds: number;
  };
}

export interface SecurityModeSettings {
  operation_mode: 'observe' | 'assist' | 'auto_defend';
  updated_at: number;
}

export interface TelegramIntegrationSettings {
  configured: boolean;
  bot_username: string;
  bot_name: string;
  chat_bound: boolean;
  chat_title: string;
  notify_auto_block: boolean;
  notify_high_severity: boolean;
  notify_min_severity: 'low' | 'medium' | 'high' | 'critical';
  quiet_hours_start: string;
  quiet_hours_end: string;
  last_error: string;
  updated_at: number;
}

export interface SlackIntegrationSettings {
  configured: boolean;
  notify_auto_block: boolean;
  notify_high_severity: boolean;
  notify_min_severity: 'low' | 'medium' | 'high' | 'critical';
  quiet_hours_start: string;
  quiet_hours_end: string;
  last_error: string;
  updated_at: number;
}
