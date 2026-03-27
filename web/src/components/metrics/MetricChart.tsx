// Лёгкий SVG-график метрик без тяжёлой chart-библиотеки.
// Нам важны две вещи: маленький bundle и предсказуемый tooltip на hover.
import { useEffect, useMemo, useRef, useState } from 'react';
import type { Metrics } from '../../types';
import { formatChartAxisTime, formatChartTime, formatMetricTick, formatMetricValue } from '../../lib/format';
import { t } from '../../lib/i18n';

interface Props {
  data: Metrics[];
  dataKey: keyof Metrics;
  color: string;
  label: string;
}

interface ChartPoint {
  timestamp: number;
  value: number;
}

const CHART_HEIGHT = 192;
const PADDING = {
  top: 12,
  right: 16,
  bottom: 28,
  left: 72,
} as const;
const Y_TICK_COUNT = 4;
const X_TICK_COUNT = 6;

function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (!ref.current) return;

    const element = ref.current;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      setWidth(entry.contentRect.width);
    });

    observer.observe(element);
    setWidth(element.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);

  return { ref, width };
}

function buildPath(points: Array<{ x: number; y: number }>) {
  if (points.length === 0) return '';
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
}

export function MetricChart({ data, dataKey, color, label }: Props) {
  const { ref, width } = useElementWidth<HTMLDivElement>();
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const chartData = useMemo<ChartPoint[]>(
    () =>
      data.map((metric) => ({
        timestamp: metric.timestamp,
        value: typeof metric[dataKey] === 'number' ? metric[dataKey] : 0,
      })),
    [data, dataKey],
  );

  const innerWidth = Math.max(0, width - PADDING.left - PADDING.right);
  const innerHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;

  const bounds = useMemo(() => {
    if (chartData.length === 0) {
      return { min: 0, max: 1 };
    }
    const values = chartData.map((point) => point.value);
    const min = Math.min(...values);
    const max = Math.max(...values);

    if (min === max) {
      const delta = max === 0 ? 1 : Math.abs(max) * 0.1;
      return { min: Math.max(0, min - delta), max: max + delta };
    }

    const padding = (max - min) * 0.08;
    return {
      min: Math.max(0, min - padding),
      max: max + padding,
    };
  }, [chartData]);

  const svgPoints = useMemo(() => {
    if (chartData.length === 0 || innerWidth <= 0) return [];

    const range = Math.max(bounds.max - bounds.min, 1);
    return chartData.map((point, index) => {
      const x =
        chartData.length === 1
          ? PADDING.left + innerWidth / 2
          : PADDING.left + (index / (chartData.length - 1)) * innerWidth;
      const normalized = (point.value - bounds.min) / range;
      const y = PADDING.top + innerHeight - normalized * innerHeight;
      return { ...point, x, y };
    });
  }, [bounds.max, bounds.min, chartData, innerHeight, innerWidth]);

  const yTicks = useMemo(() => {
    const step = (bounds.max - bounds.min) / Y_TICK_COUNT;
    return Array.from({ length: Y_TICK_COUNT + 1 }, (_, index) => {
      const value = bounds.min + step * index;
      const normalized = (value - bounds.min) / Math.max(bounds.max - bounds.min, 1);
      const y = PADDING.top + innerHeight - normalized * innerHeight;
      return { value, y };
    });
  }, [bounds.max, bounds.min, innerHeight]);

  const xTicks = useMemo(() => {
    if (svgPoints.length === 0) return [];
    const lastIndex = svgPoints.length - 1;
    return Array.from({ length: Math.min(X_TICK_COUNT, svgPoints.length) }, (_, index) => {
      const pointIndex = Math.round((index / Math.max(Math.min(X_TICK_COUNT, svgPoints.length) - 1, 1)) * lastIndex);
      const point = svgPoints[pointIndex];
      return { x: point.x, timestamp: point.timestamp };
    });
  }, [svgPoints]);

  const linePath = buildPath(svgPoints.map(({ x, y }) => ({ x, y })));
  const areaPath = svgPoints.length
    ? `${linePath} L ${svgPoints[svgPoints.length - 1].x} ${CHART_HEIGHT - PADDING.bottom} L ${svgPoints[0].x} ${CHART_HEIGHT - PADDING.bottom} Z`
    : '';

  const hoveredPoint = hoverIndex !== null ? svgPoints[hoverIndex] : null;

  return (
    <div ref={ref} className="h-48">
      <div className="mb-2 text-xs uppercase tracking-wider text-text-secondary">{label}</div>
      {chartData.length === 0 || innerWidth <= 0 ? (
        <div className="flex h-[calc(100%-24px)] items-center justify-center text-xs text-text-secondary">
          {t.table.noDataHint}
        </div>
      ) : (
        <div className="relative h-[calc(100%-24px)]">
          <svg width="100%" height="100%" viewBox={`0 0 ${width} ${CHART_HEIGHT}`} preserveAspectRatio="none">
            <defs>
              <linearGradient id={`grad-${String(dataKey)}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>

            {yTicks.map((tick, index) => (
              <g key={`y-${index}`}>
                <line
                  x1={PADDING.left}
                  y1={tick.y}
                  x2={width - PADDING.right}
                  y2={tick.y}
                  stroke="rgba(100, 116, 139, 0.12)"
                  strokeWidth="1"
                />
                <text
                  x={PADDING.left - 12}
                  y={tick.y + 4}
                  textAnchor="end"
                  fill="#64748b"
                  fontSize="10"
                >
                  {formatMetricTick(dataKey, tick.value)}
                </text>
              </g>
            ))}

            {xTicks.map((tick, index) => (
              <text
                key={`x-${index}`}
                x={tick.x}
                y={CHART_HEIGHT - 6}
                textAnchor={index === 0 ? 'start' : index === xTicks.length - 1 ? 'end' : 'middle'}
                fill="#64748b"
                fontSize="10"
              >
                {formatChartAxisTime(tick.timestamp)}
              </text>
            ))}

            <path d={areaPath} fill={`url(#grad-${String(dataKey)})`} />
            <path d={linePath} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />

            {hoveredPoint && (
              <>
                <line
                  x1={hoveredPoint.x}
                  y1={PADDING.top}
                  x2={hoveredPoint.x}
                  y2={CHART_HEIGHT - PADDING.bottom}
                  stroke="rgba(255,255,255,0.45)"
                  strokeWidth="1"
                />
                <circle cx={hoveredPoint.x} cy={hoveredPoint.y} r="5" fill={color} stroke="#fff" strokeWidth="2" />
              </>
            )}

            {svgPoints.map((point, index) => {
              const nextX = svgPoints[index + 1]?.x ?? point.x + innerWidth / Math.max(svgPoints.length, 1);
              const prevX = svgPoints[index - 1]?.x ?? point.x - innerWidth / Math.max(svgPoints.length, 1);
              const hitboxX = (prevX + point.x) / 2;
              const hitboxWidth = Math.max(16, (nextX - prevX) / 2);
              return (
                <rect
                  key={`hitbox-${point.timestamp}-${index}`}
                  x={Math.max(PADDING.left, hitboxX)}
                  y={PADDING.top}
                  width={Math.min(hitboxWidth, width - PADDING.right - Math.max(PADDING.left, hitboxX))}
                  height={innerHeight}
                  fill="transparent"
                  onMouseEnter={() => setHoverIndex(index)}
                  onMouseLeave={() => setHoverIndex((current) => (current === index ? null : current))}
                />
              );
            })}
          </svg>

          {hoveredPoint && (
            <div
              className="pointer-events-none absolute z-10 min-w-44 rounded-xl border border-border bg-bg-card px-4 py-3 text-sm shadow-[0_10px_30px_rgba(15,23,42,0.35)]"
              style={{
                left: `${Math.min(Math.max(hoveredPoint.x + 12, PADDING.left), width - 220)}px`,
                top: `${Math.max(hoveredPoint.y - 18, 12)}px`,
              }}
            >
              <div className="mb-1 font-semibold text-text-primary">{formatChartTime(hoveredPoint.timestamp)}</div>
              <div style={{ color }}>{t.dashboard.chartValue}: {formatMetricValue(dataKey, hoveredPoint.value)}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
