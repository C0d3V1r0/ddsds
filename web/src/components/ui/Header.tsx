// - Верхняя панель со статусом агента и переключателем темы
import { useStore } from '../../stores/store';
import { t } from '../../lib/i18n';

export function Header() {
  const agentStatus = useStore((state) => state.agentStatus);
  const liveStatus = useStore((state) => state.liveStatus);
  const toggleTheme = useStore((state) => state.toggleTheme);
  const theme = useStore((state) => state.theme);

  const isAgentConnected = agentStatus === 'connected';
  const isLiveConnected = liveStatus === 'connected';

  return (
    <header data-testid="app-header" className="h-14 border-b border-border flex items-center justify-between px-6 bg-bg-card">
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-wider text-text-secondary">{t.header.statusLabel}</div>
      </div>
      <div className="flex items-center gap-4" role="status" aria-live="polite" aria-atomic="true">
        <div data-testid="header-agent-status" className={`flex items-center gap-2 text-xs ${
          isAgentConnected ? 'text-accent-green' : 'text-accent-red'
        }`}>
          <span className={`w-2 h-2 rounded-full ${
            isAgentConnected ? 'bg-accent-green' : 'bg-accent-red'
          }`} aria-hidden="true" />
          {isAgentConnected ? t.header.agentConnected : t.header.agentDisconnected}
        </div>
        <div data-testid="header-live-status" className={`flex items-center gap-2 text-xs ${
          isLiveConnected ? 'text-accent-green' : 'text-accent-red'
        }`}>
          <span className={`w-2 h-2 rounded-full ${
            isLiveConnected ? 'bg-accent-green' : 'bg-accent-red'
          }`} aria-hidden="true" />
          {isLiveConnected ? t.header.liveConnected : t.header.liveDisconnected}
        </div>
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
