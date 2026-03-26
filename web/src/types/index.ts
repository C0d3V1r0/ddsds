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
}

export interface BlockedIP {
  id: number;
  ip: string;
  reason: string;
  blocked_at: number;
  expires_at: number | null;
  auto: number;
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
}

export interface LogEntry {
  timestamp: number;
  source: string;
  line: string;
  file: string;
}

export interface HealthStatus {
  status: string;
  agent: string;
  db: string;
}
