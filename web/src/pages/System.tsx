import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useStore } from '../stores/store';
import { t } from '../lib/i18n';
import {
  AboutCard,
  DeploymentCard,
  MlCard,
  RiskCard,
  SelfProtectionCard,
  SystemStatusCard,
} from '../components/system/SystemCards';

export function System() {
  const { data: health, isError: healthError, isLoading: healthLoading } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 });
  const { data: mlStatus, isError: mlError, isLoading: mlLoading } = useQuery({ queryKey: ['mlStatus'], queryFn: api.mlStatus, refetchInterval: 10000 });
  const { data: riskScore, isError: riskError, isLoading: riskLoading } = useQuery({ queryKey: ['riskScore'], queryFn: api.riskScore, refetchInterval: 10000 });
  const { data: riskHistory } = useQuery({ queryKey: ['riskHistory'], queryFn: () => api.riskHistory(), refetchInterval: 30000 });
  const { data: selfProtection, isError: selfProtectionError, isLoading: selfProtectionLoading } = useQuery({ queryKey: ['selfProtection'], queryFn: api.selfProtection, refetchInterval: 30000 });
  const { data: deploymentStatus, isError: deploymentError, isLoading: deploymentLoading } = useQuery({ queryKey: ['deploymentStatus'], queryFn: api.deploymentStatus, refetchInterval: 30000 });
  const locale = useStore((state) => state.locale);

  return (
    <div data-testid="page-system" className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold">{t.system.title}</h1>
        <p className="text-sm text-text-secondary">{t.system.summary}</p>
      </div>
      <SystemStatusCard health={health} isLoading={healthLoading} isError={healthError} />
      <DeploymentCard deploymentStatus={deploymentStatus} isLoading={deploymentLoading} isError={deploymentError} />
      <RiskCard riskScore={riskScore} riskHistory={riskHistory} isLoading={riskLoading} isError={riskError} />
      <MlCard mlStatus={mlStatus} isLoading={mlLoading} isError={mlError} />
      <SelfProtectionCard selfProtection={selfProtection} isLoading={selfProtectionLoading} isError={selfProtectionError} />
      <AboutCard locale={locale} />
    </div>
  );
}
