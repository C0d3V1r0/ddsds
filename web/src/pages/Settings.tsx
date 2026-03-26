// - Страница настроек: статус системы, конфигурация, ML
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { useStore } from '../stores/store';
import { t } from '../lib/i18n';

export function Settings() {
  const { data: health, isError: healthError } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 });
  const { theme, toggleTheme } = useStore();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">{t.settings.title}</h1>

      {/* - Статус системы */}
      <Card title={t.settings.systemStatus}>
        {healthError && <div className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
        <div className="space-y-3">
          <div className="flex justify-between items-center text-sm">
            <span>{t.settings.apiServer}</span>
            <Badge variant="status" value={health?.status === 'ok' ? 'running' : 'failed'} />
          </div>
          <div className="flex justify-between items-center text-sm">
            <span>{t.settings.agent}</span>
            <Badge variant="status" value={health?.agent === 'connected' ? 'running' : 'stopped'} />
          </div>
          <div className="flex justify-between items-center text-sm">
            <span>{t.settings.database}</span>
            <Badge variant="status" value={health?.db === 'ok' ? 'running' : 'failed'} />
          </div>
        </div>
      </Card>

      {/* - Внешний вид */}
      <Card title={t.settings.appearance}>
        <div className="flex items-center justify-between text-sm">
          <span>{t.settings.theme}</span>
          <button
            onClick={toggleTheme}
            className="bg-bg-primary border border-border rounded px-4 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
          >
            {theme === 'dark' ? t.settings.switchToLight : t.settings.switchToDark}
          </button>
        </div>
      </Card>

      {/* - ML-модуль */}
      <Card title={t.settings.mlModule}>
        <div className="space-y-3">
          <div className="flex justify-between items-center text-sm">
            <span>{t.settings.anomalyDetector}</span>
            <Badge variant="status" value="stopped" />
          </div>
          <div className="flex justify-between items-center text-sm">
            <span>{t.settings.attackClassifier}</span>
            <Badge variant="status" value="stopped" />
          </div>
          <p className="text-xs text-text-secondary mt-2">
            {t.settings.mlNote}
          </p>
        </div>
      </Card>

      {/* - Информация */}
      <Card title={t.settings.about}>
        <div className="space-y-1 text-sm text-text-secondary">
          <div>{t.settings.version}</div>
          <div>{t.settings.subtitle}</div>
        </div>
      </Card>
    </div>
  );
}
