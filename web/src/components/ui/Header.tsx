// - Верхняя панель со статусом агента и переключателем темы
import { useEffect, useState } from 'react';
import { useStore } from '../../stores/store';
import { t } from '../../lib/i18n';
import { formatCurrentTime } from '../../lib/format';

export function Header() {
  const agentStatus = useStore((state) => state.agentStatus);
  const liveStatus = useStore((state) => state.liveStatus);
  const toggleTheme = useStore((state) => state.toggleTheme);
  const toggleLocale = useStore((state) => state.toggleLocale);
  const locale = useStore((state) => state.locale);
  const theme = useStore((state) => state.theme);
  const [now, setNow] = useState(() => new Date());

  const isAgentConnected = agentStatus === 'connected';
  const isLiveConnected = liveStatus === 'connected';

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <header data-testid="app-header" className="min-h-14 border-b border-border flex flex-col gap-2 px-4 py-3 bg-bg-card md:h-14 md:flex-row md:items-center md:justify-end md:px-6 md:py-0">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2" role="status" aria-live="polite" aria-atomic="true">
        {!isAgentConnected && (
          <div data-testid="header-agent-status" className="flex items-center gap-2 text-xs whitespace-nowrap text-accent-red">
            <span className="w-2 h-2 rounded-full bg-accent-red" aria-hidden="true" />
            {t.header.agentDisconnected}
          </div>
        )}
        {!isLiveConnected && (
          <div data-testid="header-live-status" className="flex items-center gap-2 text-xs whitespace-nowrap text-accent-yellow">
            <span className="w-2 h-2 rounded-full bg-accent-yellow" aria-hidden="true" />
            {t.header.liveDisconnected}
          </div>
        )}
        <div className="flex items-center gap-2 text-xs text-text-secondary">
          <span>{t.header.currentTime}</span>
          <span className="font-medium text-text-primary">{formatCurrentTime(now)}</span>
        </div>
        <button
          type="button"
          onClick={toggleLocale}
          className="rounded border border-border px-2.5 py-1 text-xs text-text-secondary hover:text-text-primary hover:bg-bg-card-hover transition-colors"
          aria-label={t.common.language}
          title={t.common.language}
        >
          {locale === 'ru' ? t.header.switchToEn : t.header.switchToRu}
        </button>
        <button
          type="button"
          data-testid="theme-toggle"
          onClick={toggleTheme}
          className="text-text-secondary hover:text-text-primary text-lg transition-colors"
          title={theme === 'dark' ? t.settings.switchToLight : t.settings.switchToDark}
          aria-label={theme === 'dark' ? t.settings.switchToLight : t.settings.switchToDark}
          aria-pressed={theme === 'dark'}
        >
          {theme === 'dark' ? '\u2600\uFE0E' : '\u263E\uFE0E'}
        </button>
      </div>
    </header>
  );
}
