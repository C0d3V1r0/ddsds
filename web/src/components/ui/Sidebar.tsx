// - Боковая навигация приложения
import { NavLink } from 'react-router-dom';
import { t } from '../../lib/i18n';

export function Sidebar() {
  const navItems = [
    { path: '/', label: t.nav.dashboard, icon: '\u25C9' },
    { path: '/security', label: t.nav.security, icon: '\u26E8' },
    { path: '/processes', label: t.nav.processes, icon: '\u2699' },
    { path: '/logs', label: t.nav.logs, icon: '\u2261' },
    { path: '/settings', label: t.nav.settings, icon: '\u2736' },
  ];

  return (
    <aside data-testid="app-sidebar" className="w-56 h-screen bg-bg-card border-r border-border flex flex-col py-6 px-3 fixed left-0 top-0">
      <div data-testid="app-brand" className="text-xl font-bold tracking-widest text-text-primary px-3 mb-8">
        NULLIUS
      </div>
      <nav className="flex flex-col gap-1" aria-label="Основная навигация">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            data-testid={`nav-${item.path === '/' ? 'dashboard' : item.path.slice(1)}`}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-bg-card-hover text-accent-blue'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-card-hover'
              }`
            }
          >
            <span className="text-base" aria-hidden="true">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
