// HTTP-клиент для взаимодействия с backend API
import type { HealthStatus, Metrics, ServiceInfo, ProcessInfo, LogEntry, SecurityEvent, BlockedIP } from '../types';

const BASE = import.meta.env.VITE_API_URL || '/api';

function headers(): HeadersInit {
  return { 'Content-Type': 'application/json' };
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { headers: headers() });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: headers(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json() as Promise<T>;
}

// Ответ ML-модуля: готовность детектора аномалий и классификатора атак
interface MlStatusResponse {
  anomaly_detector: { ready: boolean };
  attack_classifier: { ready: boolean };
}

export const api = {
  health: () => get<HealthStatus>('/health'),
  metrics: () => get<Metrics | null>('/metrics'),
  // encodeURIComponent для защиты от инъекций в параметрах
  metricsHistory: (period: string) => get<Metrics[]>(`/metrics/history?period=${encodeURIComponent(period)}`),
  services: () => get<ServiceInfo[]>('/services'),
  processes: () => get<ProcessInfo[]>('/processes'),
  logs: (source?: string, limit = 200) =>
    get<LogEntry[]>(`/logs?source=${encodeURIComponent(source || '')}&limit=${limit}`),
  securityEvents: (eventType?: string, limit = 100) =>
    get<SecurityEvent[]>(`/security/events?event_type=${encodeURIComponent(eventType || '')}&limit=${limit}`),
  blockedIPs: () => get<BlockedIP[]>('/security/blocked'),
  blockIP: (ip: string, reason: string, duration?: number) =>
    post<{ status: string }>('/security/block', { ip, reason, duration }),
  unblockIP: (ip: string) => post<{ status: string }>('/security/unblock', { ip }),
  mlStatus: () => get<MlStatusResponse>('/ml/status'),
};
