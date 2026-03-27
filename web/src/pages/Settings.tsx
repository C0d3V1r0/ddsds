// Страница настроек: только реальные пользовательские настройки интерфейса
import { Card } from '../components/ui/Card';
import { useStore } from '../stores/store';
import { t } from '../lib/i18n';

export function Settings() {
  const { theme, toggleTheme, locale, setLocale } = useStore();

  return (
    <div data-testid="page-settings" className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold">{t.settings.title}</h1>
        <p className="text-sm text-text-secondary">{t.settings.summary}</p>
      </div>

      <Card title={t.settings.appearance} testId="settings-appearance-card">
        <p className="mb-4 text-sm text-text-secondary">{t.settings.appearanceHint}</p>
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm gap-4">
            <span>{t.settings.language}</span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="settings-language-ru"
                onClick={() => setLocale('ru')}
                className={`rounded border px-3 py-1.5 text-sm transition-colors ${
                  locale === 'ru'
                    ? 'border-accent-blue bg-bg-card-hover text-accent-blue'
                    : 'border-border text-text-secondary hover:text-text-primary hover:bg-bg-card-hover'
                }`}
              >
                Русский
              </button>
              <button
                type="button"
                data-testid="settings-language-en"
                onClick={() => setLocale('en')}
                className={`rounded border px-3 py-1.5 text-sm transition-colors ${
                  locale === 'en'
                    ? 'border-accent-blue bg-bg-card-hover text-accent-blue'
                    : 'border-border text-text-secondary hover:text-text-primary hover:bg-bg-card-hover'
                }`}
              >
                English
              </button>
            </div>
          </div>
          <div className="flex items-center justify-between text-sm gap-4">
            <span>{t.settings.theme}</span>
            <button
              data-testid="settings-theme-toggle"
              onClick={toggleTheme}
              className="bg-bg-primary border border-border rounded px-4 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
            >
              {theme === 'dark' ? t.settings.switchToLight : t.settings.switchToDark}
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}
