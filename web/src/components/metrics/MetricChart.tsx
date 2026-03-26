// - График метрик с градиентной заливкой (Recharts)
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { Metrics } from '../../types';
import { formatChartTime, formatMetricTick, formatMetricValue } from '../../lib/format';
import { t } from '../../lib/i18n';

interface Props {
  data: Metrics[];
  dataKey: keyof Metrics;
  color: string;
  label: string;
}

export function MetricChart({ data, dataKey, color, label }: Props) {
  const chartData = data.map((m) => ({
    timestamp: m.timestamp,
    time: formatChartTime(m.timestamp),
    value: (() => { const raw = m[dataKey]; return typeof raw === 'number' ? raw : 0; })(),
  }));

  return (
    <div className="h-48">
      <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">{label}</div>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id={`grad-${String(dataKey)}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis
            tick={{ fill: '#64748b', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value: number) => formatMetricTick(dataKey, value)}
            width={72}
          />
          <Tooltip
            formatter={(value) => [formatMetricValue(dataKey, Number(value ?? 0)), t.dashboard.chartValue]}
            labelFormatter={(_, payload) => {
              const point = payload?.[0]?.payload as { timestamp?: number } | undefined;
              return point?.timestamp ? formatChartTime(point.timestamp) : '';
            }}
            separator=": "
            contentStyle={{
              backgroundColor: 'var(--color-bg-card)',
              border: '1px solid var(--color-border)',
              borderRadius: '12px',
              color: 'var(--color-text-primary)',
              boxShadow: '0 10px 30px rgba(15, 23, 42, 0.35)',
              padding: '12px 14px',
            }}
            labelStyle={{ color: 'var(--color-text-primary)', fontWeight: 600, marginBottom: 6 }}
            itemStyle={{ color, paddingTop: 2, paddingBottom: 2 }}
          />
          <Area type="monotone" dataKey="value" name={label} stroke={color} fill={`url(#grad-${String(dataKey)})`} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
