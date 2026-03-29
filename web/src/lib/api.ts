// HTTP-клиент для взаимодействия с backend API
import type { HealthStatus, Metrics, ServiceInfo, ProcessInfo, ProcessActionResult, LogEntry, SecurityEvent, SecurityIncident, BlockedIP, RiskScore, RiskHistoryPoint, LogFilters, ResponseAuditEntry, TelegramIntegrationSettings, SlackIntegrationSettings, SecurityModeSettings, IncidentNote, IncidentDetail, SelfProtectionStatus, DeploymentStatus, MlStatus } from '../types';

const BASE = import.meta.env.VITE_API_URL || '/api';
const UI_TOKEN_STORAGE_KEY = 'nullius_api_token';

function getUiToken(): string {
  try {
    return window.localStorage.getItem(UI_TOKEN_STORAGE_KEY)?.trim() || '';
  } catch {
    return '';
  }
}

function headers(): HeadersInit {
  const token = getUiToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { headers: headers() });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return (await resp.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: headers(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return (await resp.json()) as T;
}

export const api = {
  health: () => get<HealthStatus>('/health'),
  metrics: () => get<Metrics | null>('/metrics'),
  // encodeURIComponent для защиты от инъекций в параметрах
  metricsHistory: (period: string) => get<Metrics[]>(`/metrics/history?period=${encodeURIComponent(period)}`),
  services: () => get<ServiceInfo[]>('/services'),
  processes: () => get<ProcessInfo[]>('/processes'),
  terminateProcess: (pid: number) => post<ProcessActionResult>('/processes/terminate', { pid }),
  forceKillProcess: (pid: number) => post<ProcessActionResult>('/processes/force-kill', { pid }),
  logs: ({ source, limit = 200, fromTs, toTs, query, ip, eventType }: LogFilters = {}) => {
    const params = new URLSearchParams({
      source: source || '',
      limit: String(limit),
    });
    if (fromTs != null) params.set('from_ts', String(fromTs));
    if (toTs != null) params.set('to_ts', String(toTs));
    if (query) params.set('q', query);
    if (ip) params.set('ip', ip);
    if (eventType) params.set('event_type', eventType);
    return get<LogEntry[]>(`/logs?${params.toString()}`);
  },
  securityEvents: (eventType?: string, sourceIp?: string, limit = 100) =>
    get<SecurityEvent[]>(
      `/security/events?event_type=${encodeURIComponent(eventType || '')}&source_ip=${encodeURIComponent(sourceIp || '')}&limit=${limit}`,
    ),
  securityIncidents: (eventType?: string, limit = 20) =>
    get<SecurityIncident[]>(`/security/incidents?event_type=${encodeURIComponent(eventType || '')}&limit=${limit}`),
  securityIncidentDetail: (incidentId: string) =>
    get<IncidentDetail>(`/security/incidents/${encodeURIComponent(incidentId)}`),
  securityIncidentNotes: (incidentId: string, limit = 20) =>
    get<IncidentNote[]>(`/security/incidents/${encodeURIComponent(incidentId)}/notes?limit=${limit}`),
  addSecurityIncidentNote: (incidentId: string, note: string) =>
    post<{ status: string }>(`/security/incidents/${encodeURIComponent(incidentId)}/notes`, { note }),
  updateSecurityIncidentStatus: (incidentId: string, status: SecurityIncident['status']) =>
    post<{ status: SecurityIncident['status'] }>(`/security/incidents/${encodeURIComponent(incidentId)}/status`, { status }),
  securityAudit: (traceId?: string, limit = 50) =>
    get<ResponseAuditEntry[]>(`/security/audit?trace_id=${encodeURIComponent(traceId || '')}&limit=${limit}`),
  blockedIPs: () => get<BlockedIP[]>('/security/blocked'),
  blockIP: (ip: string, reason: string, duration?: number) =>
    post<{ status: string }>('/security/block', { ip, reason, duration }),
  unblockIP: (ip: string) => post<{ status: string }>('/security/unblock', { ip }),
  securityMode: () => get<SecurityModeSettings>('/security/mode'),
  saveSecurityMode: (operationMode: SecurityModeSettings['operation_mode']) =>
    post<SecurityModeSettings>('/security/mode', { operation_mode: operationMode }),
  mlStatus: () => get<MlStatus>('/ml/status'),
  riskScore: () => get<RiskScore>('/risk'),
  riskHistory: (points = 24) => get<RiskHistoryPoint[]>(`/risk/history?points=${points}`),
  selfProtection: () => get<SelfProtectionStatus>('/self-protection'),
  deploymentStatus: () => get<DeploymentStatus>('/deployment'),
  telegramSettings: () => get<TelegramIntegrationSettings>('/integrations/telegram'),
  saveTelegramSettings: (
    token: string,
    notifyAutoBlock: boolean,
    notifyHighSeverity: boolean,
    notifyMinSeverity: TelegramIntegrationSettings['notify_min_severity'],
    quietHoursStart: string,
    quietHoursEnd: string,
  ) =>
    post<TelegramIntegrationSettings>('/integrations/telegram', {
      token,
      notify_auto_block: notifyAutoBlock,
      notify_high_severity: notifyHighSeverity,
      notify_min_severity: notifyMinSeverity,
      quiet_hours_start: quietHoursStart,
      quiet_hours_end: quietHoursEnd,
    }),
  sendTelegramTest: () => post<{ status: string }>('/integrations/telegram/test'),
  slackSettings: () => get<SlackIntegrationSettings>('/integrations/slack'),
  saveSlackSettings: (
    webhookUrl: string,
    notifyAutoBlock: boolean,
    notifyHighSeverity: boolean,
    notifyMinSeverity: SlackIntegrationSettings['notify_min_severity'],
    quietHoursStart: string,
    quietHoursEnd: string,
  ) =>
    post<SlackIntegrationSettings>('/integrations/slack', {
      webhook_url: webhookUrl,
      notify_auto_block: notifyAutoBlock,
      notify_high_severity: notifyHighSeverity,
      notify_min_severity: notifyMinSeverity,
      quiet_hours_start: quietHoursStart,
      quiet_hours_end: quietHoursEnd,
    }),
  sendSlackTest: () => post<{ status: string }>('/integrations/slack/test'),
};
