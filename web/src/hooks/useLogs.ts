// Хук для загрузки логов с REST + подписка на live-обновления через WS
import { useQuery } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { onLiveEvent } from '../lib/ws';
import type { LogEntry, LogFilters } from '../types';

function isLogInRange(entry: LogEntry, fromTs?: number | null, toTs?: number | null) {
  if (fromTs != null && entry.timestamp < fromTs) return false;
  if (toTs != null && entry.timestamp > toTs) return false;
  return true;
}

function matchesInvestigationQuery(entry: LogEntry, query?: string, ip?: string, eventType?: string) {
  const line = entry.line.toLowerCase();
  if (query && !line.includes(query.toLowerCase())) return false;
  if (ip && !entry.line.includes(ip)) return false;

  if (!eventType) return true;
  if (eventType === 'ssh_brute_force') return entry.source === 'auth' && /failed password/i.test(entry.line);
  if (eventType === 'sqli') return entry.source === 'nginx' && /union\s+select|or\s+1\s*=\s*1|select\s+.*\s+from/i.test(entry.line);
  if (eventType === 'xss') return entry.source === 'nginx' && /<script|javascript:|onerror=|onload=/i.test(entry.line);
  if (eventType === 'path_traversal') return entry.source === 'nginx' && /\.\.\/|\.\.\\|%2e%2e/i.test(entry.line);
  if (eventType === 'port_scan') return /UFW BLOCK|UFW AUDIT|iptables|nftables|kernel:/i.test(entry.line);
  return true;
}

export function useLogs({
  source,
  limit = 200,
  fromTs,
  toTs,
  query: textQuery,
  ip,
  eventType,
}: LogFilters = {}) {
  const [liveLogs, setLiveLogs] = useState<LogEntry[]>([]);

  const logsQuery = useQuery({
    queryKey: ['logs', source, limit, fromTs ?? null, toTs ?? null, textQuery ?? '', ip ?? '', eventType ?? ''],
    queryFn: () => api.logs({ source, limit, fromTs, toTs, query: textQuery, ip, eventType }),
    refetchInterval: 30000,
  });

  useEffect(() => {
    setLiveLogs([]);
  }, [source, fromTs, toTs, textQuery, ip, eventType]);

  useEffect(() => {
    const unsub = onLiveEvent((event) => {
      if (event.type === 'log') {
        const entry = event.data as unknown as LogEntry;
        if ((!source || entry.source === source) && isLogInRange(entry, fromTs, toTs) && matchesInvestigationQuery(entry, textQuery, ip, eventType)) {
          setLiveLogs((prev) => [...prev, entry].slice(-500));
        }
      }
    });
    return unsub;
  }, [source, fromTs, toTs, textQuery, ip, eventType]);

  const clearLive = () => setLiveLogs([]);

  const allLogs = [...(logsQuery.data ?? []), ...liveLogs];

  return { ...logsQuery, data: allLogs, liveLogs, clearLive };
}
