// Глобальное состояние приложения (Zustand)
import { create } from 'zustand';
import type { Metrics, SecurityEvent } from '../types';
import type { Locale } from '../lib/i18n';

function getInitialLocale(): Locale {
  if (typeof window === 'undefined') return 'ru';
  const saved = window.localStorage.getItem('nullius-locale');
  if (saved === 'ru' || saved === 'en') return saved;
  return window.navigator.language.toLowerCase().startsWith('ru') ? 'ru' : 'en';
}

interface NulliusStore {
  theme: 'dark' | 'light';
  locale: Locale;
  agentStatus: 'connected' | 'disconnected';
  liveStatus: 'connected' | 'disconnected';
  currentMetrics: Metrics | null;
  recentEvents: SecurityEvent[];
  toggleTheme: () => void;
  toggleLocale: () => void;
  setLocale: (locale: Locale) => void;
  setAgentStatus: (status: 'connected' | 'disconnected') => void;
  setLiveStatus: (status: 'connected' | 'disconnected') => void;
  setCurrentMetrics: (metrics: Metrics | null) => void;
  addSecurityEvent: (event: SecurityEvent) => void;
}

export const useStore = create<NulliusStore>((set) => ({
  theme: 'dark',
  locale: getInitialLocale(),
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
  toggleLocale: () => set((state) => {
    const next = state.locale === 'ru' ? 'en' : 'ru';
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('nullius-locale', next);
    }
    return { locale: next };
  }),
  setLocale: (locale) => set(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('nullius-locale', locale);
    }
    return { locale };
  }),

  setAgentStatus: (status) => set({ agentStatus: status }),
  setLiveStatus: (status) => set({ liveStatus: status }),
  setCurrentMetrics: (metrics) => set({ currentMetrics: metrics }),

  // Храним последние 50 событий для отображения в реальном времени
  addSecurityEvent: (event) => set((state) => ({
    recentEvents: [event, ...state.recentEvents].slice(0, 50),
  })),
}));
