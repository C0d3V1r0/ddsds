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
  last_error: string;
  updated_at: number;
}

export interface SlackIntegrationSettings {
  configured: boolean;
  notify_auto_block: boolean;
  notify_high_severity: boolean;
  last_error: string;
  updated_at: number;
}
