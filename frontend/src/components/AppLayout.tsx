import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import {
  LayoutDashboard,
  Radio,
  Key,
  RefreshCw,
  Settings,
  LogOut,
  Menu,
  X,
  Zap
} from 'lucide-react';
import { cn } from '../lib/utils';

interface AppLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  onRefresh?: () => void;
  autoRefresh?: boolean;
  onAutoRefreshToggle?: (enabled: boolean) => void;
}

export function AppLayout({
  children,
  title = 'Dashboard',
  subtitle,
  onRefresh,
  autoRefresh = false,
  onAutoRefreshToggle,
}: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Providers', href: '/providers', icon: Radio },
    { name: 'Keys', href: '/keys', icon: Key },
    { name: 'Runs', href: '/runs', icon: RefreshCw },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  const handleLogoutClick = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex">
      {/* Sidebar */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-50 w-72 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 border-r border-slate-700/50 transform transition-transform duration-300 ease-in-out shadow-2xl",
        sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        "lg:translate-x-0 lg:static lg:inset-0"
      )}>
        <div className="flex flex-col h-full">
          {/* Logo Header */}
          <div className="flex items-center justify-between h-20 px-6 border-b border-slate-700/50 bg-slate-800/50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/50">
                <Zap className="w-6 h-6 text-white" strokeWidth={2.5} />
              </div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">routeLLM</h1>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-slate-700/50"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto scrollbar-thin">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-xl transition-all duration-200",
                    isActive
                      ? 'bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white shadow-lg shadow-indigo-500/50 scale-105'
                      : 'text-slate-300 hover:text-white hover:bg-slate-700/70 hover:scale-105'
                  )}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon className="w-5 h-5" strokeWidth={isActive ? 2.5 : 2} />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>

          {/* User Section */}
          <div className="px-4 py-4 border-t border-slate-700/50 bg-slate-800/30">
            <div className="flex items-center gap-3 px-4 py-3 mb-3 rounded-xl bg-gradient-to-r from-slate-700/50 to-slate-600/30 border border-slate-600/30">
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-xl flex items-center justify-center text-white text-sm font-bold shadow-lg shadow-indigo-500/50">
                {user?.email?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-white truncate">{user?.email || 'User'}</p>
                <p className="text-xs text-slate-300 truncate">{user?.is_admin ? 'Administrator' : 'User'}</p>
              </div>
            </div>
            <button
              onClick={handleLogoutClick}
              className="w-full flex items-center gap-3 px-4 py-3 text-sm font-medium text-slate-300 hover:text-white hover:bg-red-600/20 hover:border-red-500/50 rounded-xl transition-all duration-200 border border-slate-700/50 hover:border-red-500/50"
            >
              <LogOut className="w-5 h-5" strokeWidth={2} />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className={cn(
        "flex-1 flex flex-col min-w-0",
        sidebarOpen && "pl-72",
        "lg:pl-0"
      )}>
        {/* Top Bar */}
        <header className="sticky top-0 z-40 w-full h-20 shrink-0 border-b border-slate-200 dark:border-slate-700/50 bg-white dark:bg-slate-800 shadow-sm">
          <div className="h-full flex items-center gap-4 px-4 sm:px-6 lg:pl-0 lg:pr-6">
            <button
              type="button"
              className="lg:hidden -m-2.5 p-2.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded-lg transition-colors"
              onClick={() => setSidebarOpen(true)}
            >
              <span className="sr-only">Open sidebar</span>
              <Menu className="w-6 h-6" />
            </button>

            <div className="flex-1 flex items-center justify-between min-w-0 gap-4">
              <div className="flex-1 min-w-0 lg:pl-4">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white leading-tight">{title}</h1>
                {subtitle && (
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 leading-tight">{subtitle}</p>
                )}
              </div>

              <div className="flex items-center gap-3 shrink-0">
                {onAutoRefreshToggle && (
                  <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 cursor-pointer whitespace-nowrap">
                    <input
                      type="checkbox"
                      checked={autoRefresh}
                      onChange={(e) => onAutoRefreshToggle(e.target.checked)}
                      className="rounded border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                    />
                    <span>Auto-refresh</span>
                  </label>
                )}
                {onRefresh && (
                  <button
                    onClick={onRefresh}
                    className="flex items-center gap-2 rounded-lg bg-white dark:bg-slate-700 px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors border border-slate-200 dark:border-slate-600 shadow-sm whitespace-nowrap"
                  >
                    <RefreshCw className="w-4 h-4" />
                    <span>Refresh</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-900">
          <div className="w-full mx-auto px-4 sm:px-6 lg:px-6 py-8">
            <div className="w-full">
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
