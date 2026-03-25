# Nullius v2 — Phase 3: React Frontend

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React dashboard with dark CrowdStrike-style UI — Dashboard, Security, Processes, Logs, Settings pages with real-time updates via WebSocket.

**Architecture:** React 18 SPA with TypeScript, Tailwind CSS for styling, Zustand for state, TanStack Query for API caching, Recharts for graphs, WebSocket for live updates. Vite for build.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Recharts, Vite

**Spec:** `docs/superpowers/specs/2026-03-25-nullius-v2-design.md`
**Depends on:** Phase 1 (Backend API must be running for integration testing)

---

## File Structure

```
src/
├── app/
│   ├── App.tsx
│   ├── main.tsx
│   └── router.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── Security.tsx
│   ├── Processes.tsx
│   ├── Logs.tsx
│   └── Settings.tsx
├── components/
│   ├── metrics/
│   │   ├── CpuCard.tsx
│   │   ├── RamCard.tsx
│   │   ├── DiskCard.tsx
│   │   ├── NetworkCard.tsx
│   │   └── MetricChart.tsx
│   ├── security/
│   │   ├── EventsList.tsx
│   │   ├── EventDetail.tsx
│   │   ├── BlockedIPs.tsx
│   │   └── ThreatBadge.tsx
│   ├── services/
│   │   └── ServiceStatus.tsx
│   └── ui/
│       ├── Sidebar.tsx
│       ├── Header.tsx
│       ├── Card.tsx
│       ├── Table.tsx
│       ├── Badge.tsx
│       └── ThemeToggle.tsx
├── hooks/
│   ├── useMetrics.ts
│   ├── useSecurity.ts
│   ├── useWebSocket.ts
│   └── useLogs.ts
├── stores/
│   └── store.ts
├── lib/
│   ├── api.ts
│   └── ws.ts
├── types/
│   └── index.ts
└── styles/
    └── globals.css
```

---

### Task 1: Project Setup (Vite + React + TypeScript + Tailwind)

- [ ] **Step 1: Create Vite project**

```bash
cd "/Users/t00r1/Desktop/Projects /Nullius"
npm create vite@latest . -- --template react-ts
npm install
npm install tailwindcss @tailwindcss/vite
npm install react-router-dom zustand @tanstack/react-query recharts
npm install -D @types/react-router-dom
```

- [ ] **Step 2: Configure Tailwind in vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
})
```

- [ ] **Step 3: Setup globals.css with dark theme**

```css
/* src/styles/globals.css */
@import "tailwindcss";

@theme {
  --color-bg-primary: #0a0e1a;
  --color-bg-card: #111827;
  --color-bg-card-hover: #1a1f35;
  --color-border: #2a3050;
  --color-text-primary: #e0e6f0;
  --color-text-secondary: #64748b;
  --color-accent-blue: #38bdf8;
  --color-accent-purple: #a78bfa;
  --color-accent-green: #22c55e;
  --color-accent-yellow: #fbbf24;
  --color-accent-red: #f87171;
}

body {
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
```

- [ ] **Step 4: Verify dev server starts**

Run: `npm run dev`
Expected: Vite dev server running on http://localhost:3000

- [ ] **Step 5: Commit**

```bash
git add package.json vite.config.ts tsconfig.json src/styles/globals.css tailwind.config.js
git commit -m "feat(frontend): setup Vite + React + TypeScript + Tailwind with dark theme"
```

---

### Task 2: Types & API Client

- [ ] **Step 1: Define TypeScript types**

```typescript
// src/types/index.ts
export interface Metrics {
  id: number;
  timestamp: number;
  cpu_total: number;
  cpu_cores: string;
  ram_used: number;
  ram_total: number;
  disk: string;
  network_rx: number;
  network_tx: number;
  load_avg: string;
}

export interface SecurityEvent {
  id: number;
  timestamp: number;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  source_ip: string;
  description: string;
  raw_log: string;
  action_taken: string;
  resolved: number;
}

export interface BlockedIP {
  id: number;
  ip: string;
  reason: string;
  blocked_at: number;
  expires_at: number | null;
  auto: number;
}

export interface ServiceInfo {
  name: string;
  status: 'running' | 'stopped' | 'failed';
  pid: number;
  uptime: number;
  updated_at: number;
}

export interface ProcessInfo {
  pid: number;
  name: string;
  cpu: number;
  ram: number;
}

export interface LogEntry {
  timestamp: number;
  source: string;
  line: string;
  file: string;
}

export interface HealthStatus {
  status: string;
  agent: string;
  db: string;
}
```

- [ ] **Step 2: Create API client**

```typescript
// src/lib/api.ts
const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`API ${resp.status}`);
  return resp.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`API ${resp.status}`);
  return resp.json();
}

export const api = {
  health: () => get<import('../types').HealthStatus>('/health'),
  metrics: () => get<import('../types').Metrics | null>('/metrics'),
  metricsHistory: (period: string) => get<import('../types').Metrics[]>(`/metrics/history?period=${period}`),
  services: () => get<import('../types').ServiceInfo[]>('/services'),
  processes: () => get<import('../types').ProcessInfo[]>('/processes'),
  logs: (source?: string, limit?: number) =>
    get<import('../types').LogEntry[]>(`/logs?source=${source || ''}&limit=${limit || 100}`),
  securityEvents: (type?: string) =>
    get<import('../types').SecurityEvent[]>(`/security/events${type ? `?type=${type}` : ''}`),
  blockedIPs: () => get<import('../types').BlockedIP[]>('/security/blocked'),
  blockIP: (ip: string, reason: string, duration?: number) =>
    post('/security/block', { ip, reason, duration }),
  unblockIP: (ip: string) => post('/security/unblock', { ip }),
};
```

- [ ] **Step 3: Create WebSocket client**

```typescript
// src/lib/ws.ts
type Listener = (event: Record<string, unknown>) => void;

let socket: WebSocket | null = null;
const listeners: Set<Listener> = new Set();

export function connectWS(): void {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  socket = new WebSocket(`${protocol}//${location.host}/ws/live`);

  socket.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'pong') return;
    listeners.forEach((fn) => fn(data));
  };

  socket.onclose = () => {
    setTimeout(connectWS, 3000);
  };

  // Heartbeat
  setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'ping' }));
    }
  }, 15000);
}

export function onLiveEvent(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
```

- [ ] **Step 4: Commit**

```bash
git add src/types/ src/lib/
git commit -m "feat(frontend): add TypeScript types, API client, and WebSocket client"
```

---

### Task 3: Zustand Store & Layout Shell

- [ ] **Step 1: Create store**

```typescript
// src/stores/store.ts
import { create } from 'zustand';
import type { Metrics, SecurityEvent, ServiceInfo, ProcessInfo, LogEntry } from '../types';

interface NulliusStore {
  theme: 'dark' | 'light';
  agentStatus: 'connected' | 'disconnected';
  currentMetrics: Metrics | null;
  recentEvents: SecurityEvent[];
  toggleTheme: () => void;
  setAgentStatus: (status: 'connected' | 'disconnected') => void;
  setCurrentMetrics: (m: Metrics | null) => void;
  addSecurityEvent: (e: SecurityEvent) => void;
}

export const useStore = create<NulliusStore>((set) => ({
  theme: 'dark',
  agentStatus: 'disconnected',
  currentMetrics: null,
  recentEvents: [],
  toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
  setAgentStatus: (status) => set({ agentStatus: status }),
  setCurrentMetrics: (m) => set({ currentMetrics: m }),
  addSecurityEvent: (e) => set((s) => ({
    recentEvents: [e, ...s.recentEvents].slice(0, 50),
  })),
}));
```

- [ ] **Step 2: Create Sidebar**

```tsx
// src/components/ui/Sidebar.tsx
import { NavLink } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Dashboard', icon: '◉' },
  { path: '/security', label: 'Security', icon: '⛨' },
  { path: '/processes', label: 'Processes', icon: '⚙' },
  { path: '/logs', label: 'Logs', icon: '≡' },
  { path: '/settings', label: 'Settings', icon: '⚡' },
];

export function Sidebar() {
  return (
    <aside className="w-56 h-screen bg-[var(--color-bg-card)] border-r border-[var(--color-border)] flex flex-col py-6 px-3 fixed left-0 top-0">
      <div className="text-xl font-bold tracking-widest text-[var(--color-text-primary)] px-3 mb-8">
        NULLIUS
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-[var(--color-bg-card-hover)] text-[var(--color-accent-blue)]'
                  : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-card-hover)]'
              }`
            }
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 3: Create Header**

```tsx
// src/components/ui/Header.tsx
import { useStore } from '../../stores/store';

export function Header() {
  const { agentStatus, toggleTheme, theme } = useStore();

  return (
    <header className="h-14 border-b border-[var(--color-border)] flex items-center justify-between px-6 bg-[var(--color-bg-card)]">
      <div />
      <div className="flex items-center gap-4">
        <div className={`flex items-center gap-2 text-xs ${
          agentStatus === 'connected' ? 'text-[var(--color-accent-green)]' : 'text-[var(--color-accent-red)]'
        }`}>
          <span className={`w-2 h-2 rounded-full ${
            agentStatus === 'connected' ? 'bg-[var(--color-accent-green)]' : 'bg-[var(--color-accent-red)]'
          }`} />
          Agent {agentStatus}
        </div>
        <button
          onClick={toggleTheme}
          className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] text-sm"
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Create App.tsx with router**

```tsx
// src/app/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Sidebar } from '../components/ui/Sidebar';
import { Header } from '../components/ui/Header';
import { Dashboard } from '../pages/Dashboard';
import { Security } from '../pages/Security';
import { Processes } from '../pages/Processes';
import { Logs } from '../pages/Logs';
import { Settings } from '../pages/Settings';
import { useEffect } from 'react';
import { connectWS } from '../lib/ws';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchInterval: 5000 } },
});

export function App() {
  useEffect(() => { connectWS(); }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex-1 ml-56">
            <Header />
            <main className="p-6">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/security" element={<Security />} />
                <Route path="/processes" element={<Processes />} />
                <Route path="/logs" element={<Logs />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </main>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add src/stores/ src/components/ui/ src/app/
git commit -m "feat(frontend): add Zustand store, Sidebar, Header, and App layout"
```

---

### Task 4: UI Components (Card, Badge, Table)

- [ ] **Step 1: Create Card component**

```tsx
// src/components/ui/Card.tsx
import { ReactNode } from 'react';

interface CardProps {
  title?: string;
  children: ReactNode;
  className?: string;
  gradient?: boolean;
}

export function Card({ title, children, className = '', gradient = true }: CardProps) {
  return (
    <div className={`rounded-lg border border-[var(--color-border)] p-4 ${
      gradient
        ? 'bg-gradient-to-br from-[var(--color-bg-card)] to-[var(--color-bg-card-hover)]'
        : 'bg-[var(--color-bg-card)]'
    } ${className}`}>
      {title && (
        <div className="text-xs uppercase tracking-wider text-[var(--color-text-secondary)] mb-2">
          {title}
        </div>
      )}
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Create Badge component**

```tsx
// src/components/ui/Badge.tsx
const severityColors = {
  low: 'bg-blue-500/15 text-blue-400',
  medium: 'bg-yellow-500/15 text-yellow-400',
  high: 'bg-red-500/15 text-red-400',
  critical: 'bg-red-600/20 text-red-300 animate-pulse',
} as const;

const statusColors = {
  running: 'bg-green-500/15 text-green-400',
  stopped: 'bg-gray-500/15 text-gray-400',
  failed: 'bg-red-500/15 text-red-400',
} as const;

interface BadgeProps {
  variant: 'severity' | 'status';
  value: string;
}

export function Badge({ variant, value }: BadgeProps) {
  const colors = variant === 'severity'
    ? severityColors[value as keyof typeof severityColors] || 'bg-gray-500/15 text-gray-400'
    : statusColors[value as keyof typeof statusColors] || 'bg-gray-500/15 text-gray-400';

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {value}
    </span>
  );
}
```

- [ ] **Step 3: Create Table component**

```tsx
// src/components/ui/Table.tsx
import { ReactNode } from 'react';

interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyField: string;
}

export function Table<T extends Record<string, unknown>>({ columns, data, keyField }: TableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            {columns.map((col) => (
              <th key={col.key} className="text-left py-3 px-4 text-xs uppercase tracking-wider text-[var(--color-text-secondary)]">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={String(row[keyField])} className="border-b border-[var(--color-border)]/30 hover:bg-[var(--color-bg-card-hover)] transition-colors">
              {columns.map((col) => (
                <td key={col.key} className="py-3 px-4">
                  {col.render ? col.render(row) : String(row[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add src/components/ui/Card.tsx src/components/ui/Badge.tsx src/components/ui/Table.tsx
git commit -m "feat(frontend): add Card, Badge, and Table UI components"
```

---

### Task 5: Dashboard Page (Metrics Cards + Charts)

- [ ] **Step 1: Create hooks**

```typescript
// src/hooks/useMetrics.ts
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

export function useMetrics() {
  return useQuery({ queryKey: ['metrics'], queryFn: api.metrics, refetchInterval: 5000 });
}

export function useMetricsHistory(period: string = '1h') {
  return useQuery({
    queryKey: ['metricsHistory', period],
    queryFn: () => api.metricsHistory(period),
    refetchInterval: 30000,
  });
}
```

- [ ] **Step 2: Create metric cards (CpuCard, RamCard, DiskCard, NetworkCard)**

```tsx
// src/components/metrics/CpuCard.tsx
import { Card } from '../ui/Card';

interface Props { value: number; }

export function CpuCard({ value }: Props) {
  const color = value > 80 ? 'var(--color-accent-red)' : value > 60 ? 'var(--color-accent-yellow)' : 'var(--color-accent-blue)';
  return (
    <Card title="CPU">
      <div className="text-2xl font-bold" style={{ color }}>{value.toFixed(1)}%</div>
      <div className="mt-2 h-1.5 rounded-full bg-[#1e293b]">
        <div className="h-full rounded-full transition-all" style={{ width: `${value}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)` }} />
      </div>
    </Card>
  );
}
```

```tsx
// src/components/metrics/RamCard.tsx
import { Card } from '../ui/Card';

interface Props { used: number; total: number; }

export function RamCard({ used, total }: Props) {
  const percent = total > 0 ? (used / total) * 100 : 0;
  const color = percent > 80 ? 'var(--color-accent-red)' : percent > 60 ? 'var(--color-accent-yellow)' : 'var(--color-accent-purple)';
  const usedGB = (used / 1024 / 1024 / 1024).toFixed(1);
  const totalGB = (total / 1024 / 1024 / 1024).toFixed(1);
  return (
    <Card title="RAM">
      <div className="text-2xl font-bold" style={{ color }}>{percent.toFixed(1)}%</div>
      <div className="text-xs text-[var(--color-text-secondary)] mt-1">{usedGB} / {totalGB} GB</div>
      <div className="mt-2 h-1.5 rounded-full bg-[#1e293b]">
        <div className="h-full rounded-full transition-all" style={{ width: `${percent}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)` }} />
      </div>
    </Card>
  );
}
```

```tsx
// src/components/metrics/DiskCard.tsx
import { Card } from '../ui/Card';

interface Props { disk: string; }

export function DiskCard({ disk }: Props) {
  const disks = JSON.parse(disk || '[]');
  const main = disks[0] || { used: 0, total: 1 };
  const percent = (main.used / main.total) * 100;
  const color = percent > 80 ? 'var(--color-accent-red)' : 'var(--color-accent-yellow)';
  return (
    <Card title="Disk">
      <div className="text-2xl font-bold" style={{ color }}>{percent.toFixed(1)}%</div>
      <div className="mt-2 h-1.5 rounded-full bg-[#1e293b]">
        <div className="h-full rounded-full transition-all" style={{ width: `${percent}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)` }} />
      </div>
    </Card>
  );
}
```

```tsx
// src/components/metrics/NetworkCard.tsx
import { Card } from '../ui/Card';

interface Props { rx: number; tx: number; }

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B/s`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB/s`;
  return `${(b / 1024 / 1024).toFixed(1)} MB/s`;
}

export function NetworkCard({ rx, tx }: Props) {
  return (
    <Card title="Network">
      <div className="flex gap-4">
        <div>
          <div className="text-xs text-[var(--color-text-secondary)]">RX</div>
          <div className="text-lg font-bold text-[var(--color-accent-green)]">{formatBytes(rx)}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-secondary)]">TX</div>
          <div className="text-lg font-bold text-[var(--color-accent-blue)]">{formatBytes(tx)}</div>
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Create MetricChart**

```tsx
// src/components/metrics/MetricChart.tsx
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { Metrics } from '../../types';

interface Props {
  data: Metrics[];
  dataKey: string;
  color: string;
  label: string;
}

export function MetricChart({ data, dataKey, color, label }: Props) {
  const chartData = data.map((m) => ({
    time: new Date(m.timestamp * 1000).toLocaleTimeString(),
    value: m[dataKey as keyof Metrics] as number,
  }));

  return (
    <div className="h-48">
      <div className="text-xs uppercase tracking-wider text-[var(--color-text-secondary)] mb-2">{label}</div>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #2a3050', borderRadius: 8, color: '#e0e6f0' }}
          />
          <Area type="monotone" dataKey="value" stroke={color} fill={`url(#grad-${dataKey})`} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: Create Dashboard page**

```tsx
// src/pages/Dashboard.tsx
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useMetrics, useMetricsHistory } from '../hooks/useMetrics';
import { CpuCard } from '../components/metrics/CpuCard';
import { RamCard } from '../components/metrics/RamCard';
import { DiskCard } from '../components/metrics/DiskCard';
import { NetworkCard } from '../components/metrics/NetworkCard';
import { MetricChart } from '../components/metrics/MetricChart';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';

export function Dashboard() {
  const { data: metrics } = useMetrics();
  const { data: history } = useMetricsHistory('1h');
  const { data: services } = useQuery({ queryKey: ['services'], queryFn: api.services, refetchInterval: 10000 });
  const { data: events } = useQuery({ queryKey: ['events'], queryFn: () => api.securityEvents(), refetchInterval: 10000 });
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 });

  return (
    <div className="space-y-6">
      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-4">
        <CpuCard value={metrics?.cpu_total ?? 0} />
        <RamCard used={metrics?.ram_used ?? 0} total={metrics?.ram_total ?? 1} />
        <DiskCard disk={metrics?.disk ?? '[]'} />
        <NetworkCard rx={metrics?.network_rx ?? 0} tx={metrics?.network_tx ?? 0} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <MetricChart data={history ?? []} dataKey="cpu_total" color="#38bdf8" label="CPU History" />
        </Card>
        <Card>
          <MetricChart data={history ?? []} dataKey="ram_used" color="#a78bfa" label="RAM History" />
        </Card>
      </div>

      {/* Services + Recent events */}
      <div className="grid grid-cols-2 gap-4">
        <Card title="Services">
          <div className="space-y-2">
            {(services ?? []).slice(0, 8).map((s) => (
              <div key={s.name} className="flex justify-between items-center text-sm">
                <span>{s.name}</span>
                <Badge variant="status" value={s.status} />
              </div>
            ))}
          </div>
        </Card>
        <Card title="Recent Security Events">
          <div className="space-y-2">
            {(events ?? []).slice(0, 5).map((e) => (
              <div key={e.id} className="flex justify-between items-center text-sm">
                <div className="flex items-center gap-2">
                  <Badge variant="severity" value={e.severity} />
                  <span className="text-[var(--color-text-secondary)]">{e.type}</span>
                </div>
                <span className="text-xs text-[var(--color-text-secondary)]">{e.source_ip}</span>
              </div>
            ))}
            {(!events || events.length === 0) && (
              <div className="text-sm text-[var(--color-text-secondary)]">No events</div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add src/hooks/ src/components/metrics/ src/pages/Dashboard.tsx
git commit -m "feat(frontend): add Dashboard page with metric cards, charts, services, events"
```

---

### Task 6: Security Page

- [ ] **Step 1: Create security hooks and components**

`src/hooks/useSecurity.ts`, `src/components/security/EventsList.tsx`, `src/components/security/BlockedIPs.tsx`, `src/pages/Security.tsx`

Implementation follows the same pattern as Dashboard — TanStack Query for data, Table component for events list, block/unblock buttons with `api.blockIP` / `api.unblockIP` calls, filter dropdowns for type and severity.

- [ ] **Step 2: Commit**

```bash
git add src/hooks/useSecurity.ts src/components/security/ src/pages/Security.tsx
git commit -m "feat(frontend): add Security page with events list and IP blocking"
```

---

### Task 7: Processes Page

- [ ] **Step 1: Create Processes page**

Sortable table of processes by CPU/RAM. Kill button sends `POST /api/security/block` (or a dedicated process endpoint). Highlight rows where ML flags suspicious.

- [ ] **Step 2: Commit**

```bash
git add src/pages/Processes.tsx
git commit -m "feat(frontend): add Processes page with sortable table"
```

---

### Task 8: Logs Page

- [ ] **Step 1: Create Logs page with WebSocket streaming**

`src/hooks/useLogs.ts` — combines REST initial load + WS live events. Auto-scroll, source filter, text search, suspicious line highlighting (red background for lines containing attack patterns).

- [ ] **Step 2: Commit**

```bash
git add src/hooks/useLogs.ts src/pages/Logs.tsx
git commit -m "feat(frontend): add Logs page with live streaming and search"
```

---

### Task 9: Settings Page

- [ ] **Step 1: Create Settings page (read-only config + ML status)**

Read-only YAML display, ML model status from `/api/ml/status`, retrain button (placeholder for Phase 4).

- [ ] **Step 2: Commit**

```bash
git add src/pages/Settings.tsx
git commit -m "feat(frontend): add Settings page with config view and ML status"
```

---

### Task 10: ThemeToggle + Light Theme

- [ ] **Step 1: Add light theme CSS variables and toggle logic**

Update `globals.css` with `[data-theme="light"]` overrides. Wire ThemeToggle in Header to set `document.documentElement.dataset.theme`.

- [ ] **Step 2: Commit**

```bash
git add src/styles/globals.css src/components/ui/ThemeToggle.tsx
git commit -m "feat(frontend): add dark/light theme toggle"
```
