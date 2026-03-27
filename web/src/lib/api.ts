// HTTP-клиент для взаимодействия с backend API
import type { HealthStatus, Metrics, ServiceInfo, ProcessInfo, ProcessActionResult, LogEntry, SecurityEvent, BlockedIP } from '../types';

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
  anomaly_detector: {
    ready: boolean;
    status: 'running' | 'pending' | 'training' | 'insufficient_data' | 'postponed' | 'failed';
    reason_code: string;
    samples_count: number;
    required_samples: number;
    event_count: number;
    max_event_count: number;
    updated_at: number;
    next_run_at: number | null;
  };
  attack_classifier: { ready: boolean };
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
  logs: (source?: string, limit = 200, fromTs?: number | null, toTs?: number | null) => {
    const params = new URLSearchParams({
      source: source || '',
      limit: String(limit),
    });
    if (fromTs != null) params.set('from_ts', String(fromTs));
    if (toTs != null) params.set('to_ts', String(toTs));
    return get<LogEntry[]>(`/logs?${params.toString()}`);
  },
  securityEvents: (eventType?: string, limit = 100) =>
    get<SecurityEvent[]>(`/security/events?event_type=${encodeURIComponent(eventType || '')}&limit=${limit}`),
  blockedIPs: () => get<BlockedIP[]>('/security/blocked'),
  blockIP: (ip: string, reason: string, duration?: number) =>
    post<{ status: string }>('/security/block', { ip, reason, duration }),
  unblockIP: (ip: string) => post<{ status: string }>('/security/unblock', { ip }),
  mlStatus: () => get<MlStatusResponse>('/ml/status'),
};
