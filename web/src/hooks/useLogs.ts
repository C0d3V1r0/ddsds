// Хук для загрузки логов с REST + подписка на live-обновления через WS
import { useQuery } from '@tanstack/react-query';
import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import { onLiveEvent } from '../lib/ws';
import type { LogEntry } from '../types';

function isLogInRange(entry: LogEntry, fromTs?: number | null, toTs?: number | null) {
  if (fromTs != null && entry.timestamp < fromTs) return false;
  if (toTs != null && entry.timestamp > toTs) return false;
  return true;
}

export function useLogs(source?: string, limit: number = 200, fromTs?: number | null, toTs?: number | null) {
  const [liveLogs, setLiveLogs] = useState<LogEntry[]>([]);

  const query = useQuery({
    queryKey: ['logs', source, limit, fromTs ?? null, toTs ?? null],
    queryFn: () => api.logs(source, limit, fromTs, toTs),
    refetchInterval: 30000,
  });

  useEffect(() => {
    setLiveLogs([]);
  }, [source, fromTs, toTs]);

  useEffect(() => {
    const unsub = onLiveEvent((event) => {
      if (event.type === 'log') {
        const entry = event.data as unknown as LogEntry;
        if ((!source || entry.source === source) && isLogInRange(entry, fromTs, toTs)) {
          setLiveLogs((prev) => [...prev, entry].slice(-500));
        }
      }
    });
    return unsub;
  }, [source, fromTs, toTs]);

  const clearLive = useCallback(() => setLiveLogs([]), []);

  const allLogs = [...(query.data ?? []), ...liveLogs];

  return { ...query, data: allLogs, liveLogs, clearLive };
}
