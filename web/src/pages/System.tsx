import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { ErrorBlock, LoadingBlock, StateBlock } from '../components/ui/StateBlock';
import { useStore } from '../stores/store';
import { t } from '../lib/i18n';
import { formatDateTime, formatRiskFactor, formatRiskLevel } from '../lib/format';

function getAnomalyReasonText(
  anomalyDetector: {
    reason_code: string;
    samples_count: number;
    filtered_samples_count: number;
    discarded_samples_count: number;
    required_samples: number;
    event_count: number;
    max_event_count: number;
    filter_window_seconds: number;
    dataset_quality_score: number;
    dataset_quality_label: 'low' | 'medium' | 'high';
    dataset_noise_label: 'clean' | 'stressed' | 'noisy';
    weighted_event_pressure: number;
    excluded_windows_count: number;
  } | undefined,
) {
  if (!anomalyDetector) return '';
  switch (anomalyDetector.reason_code) {
    case 'training_in_progress':
      return t.system.mlReasonTraining;
    case 'insufficient_data':
      return t.system.mlReasonInsufficientData(anomalyDetector.samples_count, anomalyDetector.required_samples);
    case 'insufficient_clean_data':
      return t.system.mlReasonInsufficientCleanData(
        anomalyDetector.filtered_samples_count,
        anomalyDetector.required_samples,
        anomalyDetector.samples_count,
        anomalyDetector.filter_window_seconds,
      );
    case 'poisoned_baseline':
      return t.system.mlReasonPostponed(anomalyDetector.event_count, anomalyDetector.max_event_count);
    case 'ready_filtered_baseline':
      return t.system.mlReasonFilteredBaseline(
        anomalyDetector.filtered_samples_count,
        anomalyDetector.samples_count,
        anomalyDetector.filter_window_seconds,
      );
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

function getHostProfileLabel(profile: string) {
  switch (profile) {
    case 'web':
      return t.system.mlProfileWeb;
    case 'docker':
      return t.system.mlProfileDocker;
    case 'database':
      return t.system.mlProfileDatabase;
    case 'dev':
      return t.system.mlProfileDev;
    case 'generic':
    default:
      return t.system.mlProfileGeneric;
  }
}

export function System() {
  const { data: health, isError: healthError, isLoading: healthLoading } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 });
  const { data: mlStatus, isError: mlError, isLoading: mlLoading } = useQuery({ queryKey: ['mlStatus'], queryFn: api.mlStatus, refetchInterval: 10000 });
  const { data: riskScore, isError: riskError, isLoading: riskLoading } = useQuery({ queryKey: ['riskScore'], queryFn: api.riskScore, refetchInterval: 10000 });
  const locale = useStore((state) => state.locale);

  const anomalyDetector = mlStatus?.anomaly_detector;
  const anomalyStatus = anomalyDetector?.status ?? (anomalyDetector?.ready ? 'running' : 'pending');
  const classifierStatus = mlStatus?.attack_classifier?.ready ? 'running' : 'pending';
  const anomalyReason = getAnomalyReasonText(anomalyDetector);

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

      <Card title={t.system.riskScore} testId="system-risk-card">
        {riskLoading ? (
          <LoadingBlock testId="system-risk-loading" />
        ) : riskError ? (
          <ErrorBlock testId="system-risk-error" />
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-text-secondary">{t.system.riskSummary}</p>
            <div className="flex items-end gap-3">
              <div className="text-4xl font-bold text-text-primary">{riskScore?.score ?? 0}</div>
              <div className="pb-1 text-sm text-text-secondary">{formatRiskLevel(riskScore?.level ?? 'low')}</div>
            </div>
            <div className="space-y-2">
              {(riskScore?.factors ?? []).length === 0 ? (
                <div className="text-sm text-accent-green">{formatRiskLevel('low')}</div>
              ) : (
                riskScore?.factors.map((factor) => (
                  <div key={`${factor.code}-${factor.weight}`} className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">{formatRiskFactor(factor)}</span>
                    <span className="font-mono text-text-primary">+{factor.weight}</span>
                  </div>
                ))
              )}
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
            {anomalyDetector && anomalyDetector.dataset_quality_score > 0 && (
              <div className="space-y-2 rounded-lg border border-border bg-bg-primary/40 px-3 py-2 text-xs text-text-secondary">
                <div>
                  {t.system.mlDatasetQuality(
                    anomalyDetector.dataset_quality_score,
                    anomalyDetector.dataset_quality_label === 'high'
                      ? t.system.mlQualityHigh
                      : anomalyDetector.dataset_quality_label === 'medium'
                        ? t.system.mlQualityMedium
                        : t.system.mlQualityLow,
                    anomalyDetector.filtered_samples_count,
                    anomalyDetector.discarded_samples_count,
                  )}
                </div>
                <div>
                  {t.system.mlDatasetPressure(
                    anomalyDetector.dataset_noise_label === 'clean'
                      ? t.system.mlNoiseClean
                      : anomalyDetector.dataset_noise_label === 'stressed'
                        ? t.system.mlNoiseStressed
                        : t.system.mlNoiseNoisy,
                    anomalyDetector.weighted_event_pressure,
                    anomalyDetector.excluded_windows_count,
                  )}
                </div>
                <div>
                  {t.system.mlDatasetContext(
                    getHostProfileLabel(anomalyDetector.host_profile),
                    anomalyDetector.maintenance_event_count,
                    anomalyDetector.maintenance_window_seconds,
                  )}
                </div>
              </div>
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
