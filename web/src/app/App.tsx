// Корневой компонент: провайдеры, layout, роутинг
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense, useEffect } from 'react';
import { Sidebar } from '../components/ui/Sidebar';
import { Header } from '../components/ui/Header';
import { connectWS, disconnectWS } from '../lib/ws';
import { useSystemStatus } from '../hooks/useSystemStatus';

const Dashboard = lazy(async () => import('../pages/Dashboard').then((module) => ({ default: module.Dashboard })));
const Security = lazy(async () => import('../pages/Security').then((module) => ({ default: module.Security })));
const Processes = lazy(async () => import('../pages/Processes').then((module) => ({ default: module.Processes })));
const Logs = lazy(async () => import('../pages/Logs').then((module) => ({ default: module.Logs })));
const Settings = lazy(async () => import('../pages/Settings').then((module) => ({ default: module.Settings })));

// Без агрессивного polling — данные и так приходят по WS
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function RouteFallback() {
  return (
    <div className="flex min-h-[240px] items-center justify-center text-sm text-text-secondary">
      Загрузка страницы...
    </div>
  );
}

function AppShell() {
  useSystemStatus();

  // WS подключаем при монтировании, отключаем при размонтировании
  useEffect(() => {
    connectWS();
    return () => { disconnectWS(); };
  }, []);

  return (
    <BrowserRouter>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 ml-56">
          <Header />
          <main className="p-6">
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/security" element={<Security />} />
                <Route path="/processes" element={<Processes />} />
                <Route path="/logs" element={<Logs />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}
