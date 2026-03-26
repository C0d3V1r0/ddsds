// - Верхняя панель со статусом агента и переключателем темы
import { useStore } from '../../stores/store';
import { t } from '../../lib/i18n';

export function Header() {
  const agentStatus = useStore((state) => state.agentStatus);
  const toggleTheme = useStore((state) => state.toggleTheme);
  const theme = useStore((state) => state.theme);

  const isConnected = agentStatus === 'connected';

  return (
    <header className="h-14 border-b border-border flex items-center justify-between px-6 bg-bg-card">
      <div />
      <div className="flex items-center gap-4">
        <div className={`flex items-center gap-2 text-xs ${
          isConnected ? 'text-accent-green' : 'text-accent-red'
        }`}>
          <span className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-accent-green' : 'bg-accent-red'
          }`} />
          {isConnected ? t.header.agentConnected : t.header.agentDisconnected}
        </div>
        <button
          onClick={toggleTheme}
          className="text-text-secondary hover:text-text-primary text-lg transition-colors"
          title={theme === 'dark' ? t.settings.switchToLight : t.settings.switchToDark}
          aria-label={theme === 'dark' ? t.settings.switchToLight : t.settings.switchToDark}
        >
          {theme === 'dark' ? '\u2600\uFE0E' : '\u263E\uFE0E'}
        </button>
      </div>
    </header>
  );
}
