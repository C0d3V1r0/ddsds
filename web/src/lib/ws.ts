// - WebSocket-клиент для получения real-time обновлений от агента
import { getAuthToken } from './api';

type Listener = (event: Record<string, unknown>) => void;
type StatusListener = (connected: boolean) => void;

let socket: WebSocket | null = null;
const listeners: Set<Listener> = new Set();
const statusListeners: Set<StatusListener> = new Set();
let heartbeatInterval: ReturnType<typeof setInterval> | null = null;
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
let shouldReconnect = false;

// - Устанавливает WS-соединение с автоматическим переподключением
export function connectWS(): void {
  // - Предотвращаем множественные соединения (StrictMode)
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  shouldReconnect = true;

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  socket = new WebSocket(`${protocol}//${location.host}/ws/live`);

  socket.onmessage = (msgEvent) => {
    // - Парсим JSON безопасно, игнорируя невалидные сообщения
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(msgEvent.data) as Record<string, unknown>;
    } catch {
      return;
    }
    // - Pong-ответы на heartbeat не пробрасываем подписчикам
    if (data.type === 'pong') return;
    listeners.forEach((fn) => fn(data));
  };

  socket.onclose = () => {
    if (heartbeatInterval) clearInterval(heartbeatInterval);
    heartbeatInterval = null;
    statusListeners.forEach((fn) => fn(false));
    // - Переподключение через 3 секунды, только если не вызван disconnectWS
    if (shouldReconnect) {
      reconnectTimeout = setTimeout(connectWS, 3000);
    }
  };

  socket.onopen = () => {
    // - Отправляем токен аутентификации при подключении
    const token = getAuthToken();
    if (token) {
      socket?.send(JSON.stringify({ type: 'auth', token }));
    }
    statusListeners.forEach((fn) => fn(true));
    // - Heartbeat каждые 15 секунд чтобы соединение не закрывалось
    heartbeatInterval = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'ping' }));
      }
    }, 15000);
  };
}

// - Закрывает соединение и останавливает переподключение
export function disconnectWS(): void {
  shouldReconnect = false;
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
  if (socket) {
    socket.close();
    socket = null;
  }
}

// - Подписка на live-события, возвращает функцию отписки
export function onLiveEvent(fn: Listener): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

// - Подписка на статус соединения (connected/disconnected)
export function onStatusChange(fn: StatusListener): () => void {
  statusListeners.add(fn);
  return () => { statusListeners.delete(fn); };
}
