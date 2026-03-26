// Страница настроек: статус системы, внешний вид, ML-модуль
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { ErrorBlock, LoadingBlock, StateBlock } from '../components/ui/StateBlock';
import { useStore } from '../stores/store';
import { t } from '../lib/i18n';

export function Settings() {
  const { data: health, isError: healthError, isLoading: healthLoading } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 });
  const { data: mlStatus, isError: mlError, isLoading: mlLoading } = useQuery({ queryKey: ['mlStatus'], queryFn: api.mlStatus, refetchInterval: 10000 });
  const { theme, toggleTheme } = useStore();

  // Определяем статус ML-компонентов по ответу API
  const anomalyStatus = mlStatus?.anomaly_detector?.ready ? 'running' : 'stopped';
  const classifierStatus = mlStatus?.attack_classifier?.ready ? 'running' : 'stopped';

  return (
    <div data-testid="page-settings" className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold">{t.settings.title}</h1>
        <p className="text-sm text-text-secondary">{t.settings.summary}</p>
      </div>

      {/* Статус системы */}
      <Card title={t.settings.systemStatus} testId="settings-system-card">
        <p className="mb-4 text-sm text-text-secondary">{t.settings.systemStatusHint}</p>
        {healthLoading ? (
          <LoadingBlock testId="settings-health-loading" />
        ) : healthError ? (
          <ErrorBlock testId="settings-health-error" />
        ) : (
          <div data-testid="settings-system-status" className="space-y-3">
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
        )}
      </Card>

      {/* Внешний вид */}
      <Card title={t.settings.appearance} testId="settings-appearance-card">
        <p className="mb-4 text-sm text-text-secondary">{t.settings.appearanceHint}</p>
        <div className="flex items-center justify-between text-sm">
          <span>{t.settings.theme}</span>
          <button
            data-testid="settings-theme-toggle"
            onClick={toggleTheme}
            className="bg-bg-primary border border-border rounded px-4 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
          >
            {theme === 'dark' ? t.settings.switchToLight : t.settings.switchToDark}
          </button>
        </div>
      </Card>

      {/* ML-модуль: реальный статус с бэкенда */}
      <Card title={t.settings.mlModule} testId="settings-ml-card">
        {mlLoading ? (
          <LoadingBlock testId="settings-ml-loading" />
        ) : mlError ? (
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
            <StateBlock
              title="ML-функции пока в режиме ожидания"
              description="Модели начнут приносить пользу после накопления достаточного объёма данных и фонового обучения."
              testId="settings-ml-state"
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span>{t.settings.anomalyDetector}</span>
              <Badge variant="status" value={anomalyStatus} />
            </div>
            <div className="flex justify-between items-center text-sm">
              <span>{t.settings.attackClassifier}</span>
              <Badge variant="status" value={classifierStatus} />
            </div>
            <p className="text-xs text-text-secondary mt-2">
              {t.settings.mlNote}
            </p>
            {anomalyStatus === 'stopped' && classifierStatus === 'stopped' && (
              <StateBlock
                title="ML-функции пока в режиме ожидания"
                description="Модели начнут приносить пользу после накопления достаточного объёма данных и фонового обучения."
                testId="settings-ml-state"
              />
            )}
          </div>
        )}
      </Card>

      {/* Информация */}
      <Card title={t.settings.about} testId="settings-about-card">
        <div className="space-y-1 text-sm text-text-secondary">
          <div>{t.settings.version}</div>
          <div>{t.settings.subtitle}</div>
        </div>
      </Card>
    </div>
  );
}
