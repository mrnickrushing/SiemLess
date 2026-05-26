import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Shield,
  LayoutDashboard,
  Activity,
  Bell,
  BookOpen,
  Search,
  Crosshair,
  Wifi,
  WifiOff,
  LogOut,
  X,
  Target,
  Bookmark,
  List,
  Settings,
  Keyboard,
} from 'lucide-react';
import { checkBackendHealth } from '../../api/stats';
import { getAlerts } from '../../api/alerts';
import { logout } from '../../api/auth';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  hint?: string;   // keyboard shortcut hint shown on hover
  badge?: number;
}

const BASE_NAV: Omit<NavItem, 'badge'>[] = [
  { to: '/',             icon: <LayoutDashboard className="w-5 h-5" />, label: 'Dashboard',    hint: 'g d' },
  { to: '/events',       icon: <Activity        className="w-5 h-5" />, label: 'Events',        hint: 'g e' },
  { to: '/alerts',       icon: <Bell            className="w-5 h-5" />, label: 'Alerts',        hint: 'g a' },
  { to: '/rules',        icon: <BookOpen        className="w-5 h-5" />, label: 'Rules',         hint: 'g r' },
  { to: '/search',       icon: <Search          className="w-5 h-5" />, label: 'Search',        hint: 'g s' },
  { to: '/saved-searches', icon: <Bookmark      className="w-5 h-5" />, label: 'Saved Searches' },
  { to: '/threat-intel', icon: <Crosshair       className="w-5 h-5" />, label: 'Threat Intel',  hint: 'g t' },
  { to: '/mitre',        icon: <Target          className="w-5 h-5" />, label: 'MITRE ATT&CK',  hint: 'g m' },
  { to: '/watchlist',    icon: <List            className="w-5 h-5" />, label: 'Watchlist',     hint: 'g w' },
  { to: '/settings',     icon: <Settings        className="w-5 h-5" />, label: 'Settings' },
];

interface SidebarProps {
  onClose?: () => void;
  onHelpOpen?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ onClose, onHelpOpen }) => {
  const location = useLocation();
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [openAlertCount, setOpenAlertCount] = useState(0);
  const sseRef = useRef<EventSource | null>(null);

  // Health check
  useEffect(() => {
    const check = async () => {
      const online = await checkBackendHealth();
      setBackendOnline(online);
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  // Poll open alert count; bump on SSE events
  useEffect(() => {
    const fetchCount = async () => {
      try {
        const data = await getAlerts({ status: 'open', page: 1, page_size: 1 });
        setOpenAlertCount(data.total);
      } catch {
        // non-fatal
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 30_000);

    // Listen on SSE stream to detect new events and refetch
    try {
      const es = new EventSource('/api/v1/events/stream');
      es.onmessage = () => fetchCount();
      sseRef.current = es;
    } catch {
      // SSE not available
    }

    return () => {
      clearInterval(interval);
      sseRef.current?.close();
    };
  }, []);

  const navItems: NavItem[] = BASE_NAV.map((item) =>
    item.to === '/alerts' ? { ...item, badge: openAlertCount || undefined } : item
  );

  return (
    <aside className="w-64 h-full min-h-screen bg-cyber-card border-r border-cyber-border flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-cyber-border">
        <div className="w-9 h-9 rounded-lg bg-cyber-accent/10 border border-cyber-accent/30 flex items-center justify-center flex-shrink-0">
          <Shield className="w-5 h-5 text-cyber-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-lg font-bold text-cyber-text tracking-tight">SiemLess</span>
          <div className="text-[10px] font-mono text-cyber-muted tracking-widest uppercase">Security Platform</div>
        </div>
        <button
          onClick={onClose}
          className="lg:hidden p-1 text-cyber-muted hover:text-cyber-text transition-colors flex-shrink-0"
          aria-label="Close menu"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5" aria-label="Main navigation">
        {navItems.map((item) => {
          const isActive =
            item.to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.to);

          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onClose}
              title={item.hint ? `${item.label} (${item.hint})` : item.label}
              className={`group flex items-center gap-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150
                border-l-2 pl-3
                ${
                  isActive
                    ? 'bg-cyber-accent/10 text-cyber-accent border-l-cyber-accent'
                    : 'text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 border-l-transparent'
                }`}
            >
              <span className={`transition-colors ${isActive ? 'text-cyber-accent' : 'text-cyber-muted group-hover:text-cyber-text'}`}>
                {item.icon}
              </span>
              <span className="flex-1">{item.label}</span>
              {/* Keyboard hint — visible on hover */}
              {item.hint && !item.badge && (
                <span className="hidden group-hover:flex items-center gap-0.5 opacity-60">
                  {item.hint.split(' ').map((k, i) => (
                    <kbd key={i} className="text-[9px] font-mono px-1 py-0.5 rounded bg-cyber-border text-cyber-muted">{k}</kbd>
                  ))}
                </span>
              )}
              {item.badge != null && item.badge > 0 && (
                <span className="min-w-[20px] h-5 px-1 rounded-full bg-cyber-danger text-white text-[10px] font-bold flex items-center justify-center">
                  {item.badge > 99 ? '99+' : item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Backend Status */}
      <div className="px-5 py-4 border-t border-cyber-border">
        <div className="flex items-center gap-2.5">
          {backendOnline === null ? (
            <><div className="w-2 h-2 rounded-full bg-cyber-muted animate-pulse" /><span className="text-xs text-cyber-muted">Checking connection...</span></>
          ) : backendOnline ? (
            <><Wifi className="w-3.5 h-3.5 text-cyber-accent" /><span className="text-xs text-cyber-accent">Backend connected</span><div className="ml-auto w-2 h-2 rounded-full bg-cyber-accent animate-pulse-slow" /></>
          ) : (
            <><WifiOff className="w-3.5 h-3.5 text-cyber-danger" /><span className="text-xs text-cyber-danger">Backend offline</span><div className="ml-auto w-2 h-2 rounded-full bg-cyber-danger" /></>
          )}
        </div>
        <div className="mt-2 text-[10px] font-mono text-cyber-muted/60">API: /api/v1</div>
      </div>

      {/* Keyboard shortcut hint + Logout */}
      <div className="px-3 pb-4 space-y-1">
        <button
          onClick={onHelpOpen}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium text-cyber-muted/60 hover:text-cyber-muted hover:bg-cyber-border/20 transition-all duration-150"
          aria-label="Keyboard shortcuts"
        >
          <Keyboard className="w-3.5 h-3.5" />
          <span>Keyboard shortcuts</span>
          <kbd className="ml-auto text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyber-border text-cyber-muted">?</kbd>
        </button>
        <button
          onClick={() => logout()}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-cyber-muted hover:text-cyber-danger hover:bg-cyber-danger/10 transition-all duration-150"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
