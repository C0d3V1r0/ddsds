// - Корневой компонент: провайдеры, layout, роутинг
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Sidebar } from '../components/ui/Sidebar';
import { Header } from '../components/ui/Header';
import { Dashboard } from '../pages/Dashboard';
import { Security } from '../pages/Security';
import { Processes } from '../pages/Processes';
import { Logs } from '../pages/Logs';
import { Settings } from '../pages/Settings';
import { connectWS, disconnectWS } from '../lib/ws';

// - Глобальный QueryClient с рефетчем каждые 5 секунд по умолчанию
const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchInterval: 5000 } },
});

export function App() {
  // - Подключаем WebSocket при монтировании, отключаем при размонтировании
  useEffect(() => {
    connectWS();
    return () => { disconnectWS(); };
  }, []);

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
