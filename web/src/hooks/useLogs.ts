// Хук для загрузки логов с REST + подписка на live-обновления через WS
import { useQuery } from '@tanstack/react-query';
import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import { onLiveEvent } from '../lib/ws';
import type { LogEntry } from '../types';

export function useLogs(source?: string, limit: number = 200) {
  const [liveLogs, setLiveLogs] = useState<LogEntry[]>([]);

  const query = useQuery({
    queryKey: ['logs', source, limit],
    queryFn: () => api.logs(source, limit),
    refetchInterval: 30000,
  });

  useEffect(() => {
    const unsub = onLiveEvent((event) => {
      if (event.type === 'log') {
        const entry = event.data as unknown as LogEntry;
        if (!source || entry.source === source) {
          setLiveLogs((prev) => [...prev, entry].slice(-500));
        }
      }
    });
    return unsub;
  }, [source]);

  const clearLive = useCallback(() => setLiveLogs([]), []);

  const allLogs = [...(query.data ?? []), ...liveLogs];

  return { ...query, data: allLogs, liveLogs, clearLive };
}
