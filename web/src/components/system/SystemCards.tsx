import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { ErrorBlock, LoadingBlock, StateBlock } from '../ui/StateBlock';
import { t } from '../../lib/i18n';
import {
  formatDateTime,
  formatRiskChangeSummary,
  formatRiskExplanation,
  formatRiskFactor,
  formatRiskLevel,
  formatRiskTopContributors,
  formatRiskTrend,
} from '../../lib/format';
import type {
  DeploymentStatus,
  HealthStatus,
  MlAnomalyDetectorStatus,
  MlStatus,
  RiskHistoryPoint,
  RiskScore,
  SelfProtectionStatus,
} from '../../types';

function buildRiskSparklinePath(values: number[]): string {
  if (values.length < 2) return '';
  const width = 220;
  const height = 56;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(1, max - min);

  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
}

function getHostProfileLabel(profile: string): string {
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

function getAnomalyReasonText(anomalyDetector: MlAnomalyDetectorStatus | undefined): string {
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
    case 'ready_best_effort_baseline':
      return t.system.mlReasonBestEffortBaseline(
        anomalyDetector.filtered_samples_count,
        anomalyDetector.samples_count,
        anomalyDetector.weighted_event_pressure,
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

interface SystemStatusCardProps {
  health?: HealthStatus;
  isLoading: boolean;
  isError: boolean;
}

export function SystemStatusCard({ health, isLoading, isError }: SystemStatusCardProps) {
  return (
    <Card title={t.system.systemStatus} testId="system-status-card">
      <p className="mb-4 text-sm text-text-secondary">{t.system.systemStatusHint}</p>
      {isLoading ? (
        <LoadingBlock testId="system-health-loading" />
      ) : isError ? (
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
  );
}

interface DeploymentCardProps {
  deploymentStatus?: DeploymentStatus;
  isLoading: boolean;
  isError: boolean;
}

export function DeploymentCard({ deploymentStatus, isLoading, isError }: DeploymentCardProps) {
  return (
    <Card title={t.system.deploymentRoleTitle} testId="system-deployment-card">
      {isLoading ? (
        <LoadingBlock testId="system-deployment-loading" />
      ) : isError ? (
        <ErrorBlock testId="system-deployment-error" />
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">{t.system.deploymentRoleSummary}</p>
          <div className="flex items-end gap-3">
            <div className="text-2xl font-bold text-text-primary">
              {deploymentStatus?.role === 'standby' ? t.system.deploymentRoleStandby : t.system.deploymentRolePrimary}
            </div>
            <div className="pb-1 text-sm text-text-secondary">
              {deploymentStatus?.role === 'standby' ? t.system.deploymentRoleStandbyHint : t.system.deploymentRolePrimaryHint}
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-text-secondary">{t.system.deploymentBackgroundLoops}</span>
              <Badge variant="status" value={deploymentStatus?.background_tasks_enabled ? 'running' : 'stopped'} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-text-secondary">{t.system.deploymentActiveResponse}</span>
              <Badge variant="status" value={deploymentStatus?.active_response_enabled ? 'running' : 'stopped'} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-text-secondary">{t.system.deploymentPrimaryLock}</span>
              <Badge variant="status" value={deploymentStatus?.primary_lock_held ? 'running' : 'stopped'} />
            </div>
          </div>
          <div className="text-xs text-text-secondary">
            {t.system.deploymentNodeName(deploymentStatus?.node_name ?? 'unknown')}
          </div>
          {deploymentStatus?.primary_lock_info?.owner_node_name ? (
            <div className="text-xs text-text-secondary">
              {t.system.deploymentLockOwner(
                deploymentStatus.primary_lock_info.owner_node_name,
                deploymentStatus.primary_lock_info.owner_pid,
              )}
            </div>
          ) : null}
          <div className="text-xs text-text-secondary">
            {deploymentStatus?.failover?.enabled
              ? t.system.deploymentFailoverEnabled(
                  deploymentStatus.failover.primary_api_url || 'not-set',
                  deploymentStatus.failover.failure_threshold,
                )
              : t.system.deploymentFailoverDisabled}
          </div>
          <div className="rounded-lg border border-border bg-bg-primary/40 px-3 py-3 text-sm text-text-secondary">
            {deploymentStatus?.role === 'standby' ? t.system.deploymentStandbyNote : t.system.deploymentPrimaryNote}
          </div>
        </div>
      )}
    </Card>
  );
}

interface RiskCardProps {
  riskScore?: RiskScore;
  riskHistory?: RiskHistoryPoint[];
  isLoading: boolean;
  isError: boolean;
}

export function RiskCard({ riskScore, riskHistory, isLoading, isError }: RiskCardProps) {
  const values = (riskHistory ?? []).map((point) => point.score);
  const sparkline = buildRiskSparklinePath(values);
  const previousRiskScore = riskHistory && riskHistory.length >= 2 ? riskHistory[riskHistory.length - 2].score : null;
  const riskDelta = previousRiskScore == null || !riskScore ? 0 : riskScore.score - previousRiskScore;
  const topRiskContributors = formatRiskTopContributors(riskScore?.factors ?? []);
  const riskChangeSummary = formatRiskChangeSummary(riskScore?.factors ?? [], riskHistory ?? [], riskScore?.score ?? 0);

  return (
    <Card title={t.system.riskScore} testId="system-risk-card">
      {isLoading ? (
        <LoadingBlock testId="system-risk-loading" />
      ) : isError ? (
        <ErrorBlock testId="system-risk-error" />
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">{t.system.riskSummary}</p>
          <div className="flex items-end gap-3">
            <div className="text-4xl font-bold text-text-primary">{riskScore?.score ?? 0}</div>
            <div className="pb-1 text-sm text-text-secondary">{formatRiskLevel(riskScore?.level ?? 'low')}</div>
          </div>
          <div className="text-sm text-text-secondary">{formatRiskTrend(riskHistory ?? [])}</div>
          {riskHistory && riskHistory.length > 1 ? (
            <div className="space-y-2">
              <div className="text-xs uppercase tracking-wider text-text-secondary">{t.system.riskTrend}</div>
              <div className="rounded-lg border border-border bg-bg-primary/40 px-3 py-3">
                <div className="flex items-center justify-between gap-4">
                  <svg viewBox="0 0 220 56" className="h-14 w-full max-w-[220px]" aria-hidden="true">
                    <path
                      d={sparkline}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      className="text-accent-blue"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <div className="text-right">
                    <div className={`text-sm font-medium ${riskDelta > 0 ? 'text-orange-300' : riskDelta < 0 ? 'text-accent-green' : 'text-text-secondary'}`}>
                      {riskDelta > 0 ? `+${riskDelta}` : riskDelta}
                    </div>
                    <div className="text-xs text-text-secondary">{formatDateTime(riskHistory[riskHistory.length - 1].timestamp)}</div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-text-secondary">{t.system.riskHistoryEmpty}</div>
          )}
          <div className="max-w-2xl text-sm text-text-secondary">
            {formatRiskExplanation(riskScore?.level ?? 'low', riskScore?.factors ?? [])}
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-bg-primary/40 px-3 py-3">
              <div className="mb-3 text-xs uppercase tracking-wider text-text-secondary">{t.system.riskTopContributors}</div>
              <div className="space-y-2">
                {topRiskContributors.length === 0 ? (
                  <div className="text-sm text-accent-green">{formatRiskLevel('low')}</div>
                ) : (
                  topRiskContributors.map((factor) => (
                    <div key={`${factor.code}-${factor.weight}`} className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-text-secondary">{factor.label}</span>
                      <span className="font-mono text-text-primary">+{factor.weight}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-bg-primary/40 px-3 py-3">
              <div className="mb-3 text-xs uppercase tracking-wider text-text-secondary">{t.system.riskChangeSummary}</div>
              <div className="text-sm text-text-secondary">{riskChangeSummary}</div>
            </div>
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
  );
}

interface MlCardProps {
  mlStatus?: MlStatus;
  isLoading: boolean;
  isError: boolean;
}

export function MlCard({ mlStatus, isLoading, isError }: MlCardProps) {
  const anomalyDetector = mlStatus?.anomaly_detector;
  const anomalyStatus = anomalyDetector?.status ?? (anomalyDetector?.ready ? 'running' : 'pending');
  const classifierStatus = mlStatus?.attack_classifier?.ready ? 'running' : 'pending';
  const anomalyReason = getAnomalyReasonText(anomalyDetector);

  return (
    <Card title={t.system.mlModule} testId="system-ml-card">
      {isLoading ? (
        <LoadingBlock testId="system-ml-loading" />
      ) : isError ? (
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
          <StateBlock title={t.system.mlPendingTitle} description={t.system.mlPendingDescription} testId="system-ml-state" />
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex justify-between items-center text-sm">
            <span>{t.system.anomalyDetector}</span>
            <Badge variant="status" value={anomalyStatus} />
          </div>
          {anomalyReason && <div className="text-xs text-text-secondary">{anomalyReason}</div>}
          {anomalyDetector && anomalyDetector.dataset_quality_score > 0 ? (
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
          ) : null}
          {mlStatus?.anomaly_detector?.next_run_at && anomalyStatus !== 'running' ? (
            <div className="text-xs text-text-secondary/80">
              {t.system.mlNextAttempt}: {formatDateTime(mlStatus.anomaly_detector.next_run_at)}
            </div>
          ) : null}
          <div className="flex justify-between items-center text-sm">
            <span>{t.system.attackClassifier}</span>
            <Badge variant="status" value={classifierStatus} />
          </div>
          <p className="text-xs text-text-secondary mt-2">{t.system.mlNote}</p>
          {anomalyStatus !== 'running' || classifierStatus === 'pending' ? (
            <StateBlock title={t.system.mlPendingTitle} description={t.system.mlPendingDescription} testId="system-ml-state" />
          ) : null}
        </div>
      )}
    </Card>
  );
}

interface SelfProtectionCardProps {
  selfProtection?: SelfProtectionStatus;
  isLoading: boolean;
  isError: boolean;
}

export function SelfProtectionCard({ selfProtection, isLoading, isError }: SelfProtectionCardProps) {
  return (
    <Card title={t.system.selfProtection} testId="system-self-protection-card">
      {isLoading ? (
        <LoadingBlock testId="system-self-protection-loading" />
      ) : isError ? (
        <ErrorBlock testId="system-self-protection-error" />
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">{t.system.selfProtectionSummary}</p>
          <div className="flex items-end gap-3">
            <Badge variant="severity" value={selfProtection?.level ?? 'low'} />
            <div className="text-sm text-text-secondary">
              {t.system.selfProtectionCounters(
                selfProtection?.healthy_count ?? 0,
                selfProtection?.warning_count ?? 0,
                selfProtection?.failing_count ?? 0,
              )}
            </div>
          </div>
          <div className="space-y-3">
            {(selfProtection?.checks ?? []).map((check) => (
              <div key={check.code} className="rounded-lg border border-border bg-bg-primary/40 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium text-text-primary">{check.title}</div>
                    <div className="mt-1 text-sm text-text-secondary">{check.description}</div>
                    <div className="mt-2 text-xs text-text-secondary/80">{check.recommendation}</div>
                  </div>
                  <div className="shrink-0">
                    <Badge variant="severity" value={check.severity} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

interface AboutCardProps {
  locale: 'ru' | 'en';
}

export function AboutCard({ locale }: AboutCardProps) {
  return (
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
  );
}
