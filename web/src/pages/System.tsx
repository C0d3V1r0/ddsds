import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { ErrorBlock, LoadingBlock, StateBlock } from '../components/ui/StateBlock';
import { useStore } from '../stores/store';
import { t } from '../lib/i18n';
import { formatDateTime } from '../lib/format';

function getAnomalyReasonText(
  anomalyDetector: {
    reason_code: string;
    samples_count: number;
    required_samples: number;
    event_count: number;
    max_event_count: number;
  } | undefined,
) {
  if (!anomalyDetector) return '';
  switch (anomalyDetector.reason_code) {
    case 'training_in_progress':
      return t.system.mlReasonTraining;
    case 'insufficient_data':
      return t.system.mlReasonInsufficientData(anomalyDetector.samples_count, anomalyDetector.required_samples);
    case 'poisoned_baseline':
      return t.system.mlReasonPostponed(anomalyDetector.event_count, anomalyDetector.max_event_count);
    case 'ready':
      return t.system.mlReasonReady(anomalyDetector.samples_count);
    case 'training_failed':
      return t.system.mlReasonFailed;
    case 'model_load_failed':
      return t.system.mlReasonLoadFailed;
    case 'waiting_for_first_run':
    default:
      return t.system.mlReasonWaiting;
  }
}

export function System() {
  const { data: health, isError: healthError, isLoading: healthLoading } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 });
  const { data: mlStatus, isError: mlError, isLoading: mlLoading } = useQuery({ queryKey: ['mlStatus'], queryFn: api.mlStatus, refetchInterval: 10000 });
  const locale = useStore((state) => state.locale);

  const anomalyStatus = mlStatus?.anomaly_detector?.status ?? (mlStatus?.anomaly_detector?.ready ? 'running' : 'pending');
  const classifierStatus = mlStatus?.attack_classifier?.ready ? 'running' : 'pending';
  const anomalyReason = getAnomalyReasonText(mlStatus?.anomaly_detector);

  return (
    <div data-testid="page-system" className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold">{t.system.title}</h1>
        <p className="text-sm text-text-secondary">{t.system.summary}</p>
      </div>

      <Card title={t.system.systemStatus} testId="system-status-card">
        <p className="mb-4 text-sm text-text-secondary">{t.system.systemStatusHint}</p>
        {healthLoading ? (
          <LoadingBlock testId="system-health-loading" />
        ) : healthError ? (
          <ErrorBlock testId="system-health-error" />
        ) : (
          <div data-testid="system-status-list" className="space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span>{t.system.apiServer}</span>
              <Badge variant="status" value={health?.status === 'ok' ? 'running' : 'failed'} />
            </div>
            <div className="flex justify-between items-center text-sm">
              <span>{t.system.agent}</span>
              <Badge variant="status" value={health?.agent === 'connected' ? 'running' : 'stopped'} />
            </div>
            <div className="flex justify-between items-center text-sm">
              <span>{t.system.database}</span>
              <Badge variant="status" value={health?.db === 'ok' ? 'running' : 'failed'} />
            </div>
          </div>
        )}
      </Card>

      <Card title={t.system.mlModule} testId="system-ml-card">
        {mlLoading ? (
          <LoadingBlock testId="system-ml-loading" />
        ) : mlError ? (
          <div className="space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span>{t.system.anomalyDetector}</span>
              <Badge variant="status" value="stopped" />
            </div>
            <div className="flex justify-between items-center text-sm">
              <span>{t.system.attackClassifier}</span>
              <Badge variant="status" value="stopped" />
            </div>
            <p className="text-xs text-text-secondary mt-2">{t.system.mlNote}</p>
            <StateBlock
              title={t.system.mlPendingTitle}
              description={t.system.mlPendingDescription}
              testId="system-ml-state"
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span>{t.system.anomalyDetector}</span>
              <Badge variant="status" value={anomalyStatus} />
            </div>
            {anomalyReason && (
              <div className="text-xs text-text-secondary">{anomalyReason}</div>
            )}
            {mlStatus?.anomaly_detector?.next_run_at && anomalyStatus !== 'running' && (
              <div className="text-xs text-text-secondary/80">
                {t.system.mlNextAttempt}: {formatDateTime(mlStatus.anomaly_detector.next_run_at)}
              </div>
            )}
            <div className="flex justify-between items-center text-sm">
              <span>{t.system.attackClassifier}</span>
              <Badge variant="status" value={classifierStatus} />
            </div>
            <p className="text-xs text-text-secondary mt-2">{t.system.mlNote}</p>
            {(anomalyStatus !== 'running' || classifierStatus === 'pending') && (
              <StateBlock
                title={t.system.mlPendingTitle}
                description={t.system.mlPendingDescription}
                testId="system-ml-state"
              />
            )}
          </div>
        )}
      </Card>

      <Card title={t.system.about} testId="system-about-card">
        <div className="space-y-4">
          <div className="space-y-1">
            <div className="text-base font-semibold text-text-primary">{t.system.version}</div>
            <div className="text-sm text-text-secondary">{t.system.subtitle}</div>
          </div>
          <div className="grid gap-3 md:grid-cols-3 text-sm">
            <div className="rounded-lg border border-border bg-bg-primary/40 px-4 py-3">
              <div className="text-xs uppercase tracking-wider text-text-secondary">{t.system.releaseChannel}</div>
              <div className="mt-1 text-text-primary">{t.system.betaChannel}</div>
            </div>
            <div className="rounded-lg border border-border bg-bg-primary/40 px-4 py-3">
              <div className="text-xs uppercase tracking-wider text-text-secondary">{t.system.deploymentMode}</div>
              <div className="mt-1 text-text-primary">{t.system.selfHosted}</div>
            </div>
            <div className="rounded-lg border border-border bg-bg-primary/40 px-4 py-3">
              <div className="text-xs uppercase tracking-wider text-text-secondary">{t.system.uiLanguage}</div>
              <div className="mt-1 text-text-primary">{locale === 'ru' ? 'Русский' : 'English'}</div>
            </div>
          </div>
          <div className="text-xs text-text-secondary">{t.system.aboutDescription}</div>
        </div>
      </Card>
    </div>
  );
}
