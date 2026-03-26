// - Хук для подписки на WebSocket-события с автоотпиской
import { useEffect } from 'react';
import { onLiveEvent, onStatusChange } from '../lib/ws';
import { useStore } from '../stores/store';
import type { SecurityEvent, Metrics } from '../types';

// - Рантайм-проверка структуры метрик
function isMetrics(data: unknown): data is Metrics {
  if (typeof data !== 'object' || data === null) return false;
  const d = data as Record<string, unknown>;
  return typeof d.cpu_total === 'number' && typeof d.ram_used === 'number';
}

// - Рантайм-проверка структуры события безопасности
function isSecurityEvent(data: unknown): data is SecurityEvent {
  if (typeof data !== 'object' || data === null) return false;
  const d = data as Record<string, unknown>;
  return typeof d.severity === 'string' && typeof d.type === 'string';
}

export function useWebSocket() {
  const setCurrentMetrics = useStore((s) => s.setCurrentMetrics);
  const addSecurityEvent = useStore((s) => s.addSecurityEvent);
  const setLiveStatus = useStore((s) => s.setLiveStatus);

  useEffect(() => {
    // - WebSocket-статус не равен статусу агента, храним его отдельно
    const unsubStatus = onStatusChange((connected) => {
      setLiveStatus(connected ? 'connected' : 'disconnected');
    });

    const unsubEvents = onLiveEvent((event) => {
      if (event.type === 'metrics' && isMetrics(event.data)) {
        setCurrentMetrics(event.data);
      } else if (event.type === 'security_event' && isSecurityEvent(event.data)) {
        addSecurityEvent(event.data);
      }
    });

    return () => {
      unsubEvents();
      unsubStatus();
    };
  }, [setCurrentMetrics, addSecurityEvent, setLiveStatus]);
}
