// - График метрик с градиентной заливкой (Recharts)
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { Metrics } from '../../types';

interface Props {
  data: Metrics[];
  dataKey: keyof Metrics;
  color: string;
  label: string;
}

export function MetricChart({ data, dataKey, color, label }: Props) {
  const chartData = data.map((m) => ({
    time: new Date(m.timestamp * 1000).toLocaleTimeString(),
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
          <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-bg-card)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              color: 'var(--color-text-primary)',
            }}
          />
          <Area type="monotone" dataKey="value" stroke={color} fill={`url(#grad-${String(dataKey)})`} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
