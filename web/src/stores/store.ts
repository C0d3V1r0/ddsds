// Глобальное состояние приложения (Zustand)
import { create } from 'zustand';
import type { Metrics, SecurityEvent } from '../types';

interface NulliusStore {
  theme: 'dark' | 'light';
  agentStatus: 'connected' | 'disconnected';
  liveStatus: 'connected' | 'disconnected';
  currentMetrics: Metrics | null;
  recentEvents: SecurityEvent[];
  toggleTheme: () => void;
  setAgentStatus: (status: 'connected' | 'disconnected') => void;
  setLiveStatus: (status: 'connected' | 'disconnected') => void;
  setCurrentMetrics: (metrics: Metrics | null) => void;
  addSecurityEvent: (event: SecurityEvent) => void;
}

export const useStore = create<NulliusStore>((set) => ({
  theme: 'dark',
  agentStatus: 'disconnected',
  liveStatus: 'disconnected',
  currentMetrics: null,
  recentEvents: [],

  toggleTheme: () => set((state) => {
    const next = state.theme === 'dark' ? 'light' : 'dark';
    // Обновляем data-атрибут для CSS-переменных светлой темы
    document.documentElement.dataset.theme = next;
    return { theme: next };
  }),

  setAgentStatus: (status) => set({ agentStatus: status }),
  setLiveStatus: (status) => set({ liveStatus: status }),
  setCurrentMetrics: (metrics) => set({ currentMetrics: metrics }),

  // Храним последние 50 событий для отображения в реальном времени
  addSecurityEvent: (event) => set((state) => ({
    recentEvents: [event, ...state.recentEvents].slice(0, 50),
  })),
}));
