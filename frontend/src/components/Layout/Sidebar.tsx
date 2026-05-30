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
  Sun,
  Moon,
  Briefcase,
  ShieldCheck,
  Brain,
  Cloud,
  Zap,
  Monitor,
} from 'lucide-react';
import { checkBackendHealth } from '../../api/stats';
import { getAlerts } from '../../api/alerts';
import { logout } from '../../api/auth';
import { useTheme } from '../../context/ThemeContext';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  hint?: string;
  badge?: number;
}

interface NavGroup {
  title: string;
  items: Omit<NavItem, 'badge'>[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: 'Monitor',
    items: [
      { to: '/', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Security Overview', hint: 'g d' },
      { to: '/alerts', icon: <Bell className="w-5 h-5" />, label: 'Alert Queue', hint: 'g a' },
      { to: '/events', icon: <Activity className="w-5 h-5" />, label: 'Event Explorer', hint: 'g e' },
      { to: '/search', icon: <Search className="w-5 h-5" />, label: 'Hunt Search', hint: 'g s' },
      { to: '/saved-searches', icon: <Bookmark className="w-5 h-5" />, label: 'Saved Hunts' },
    ],
  },
  {
    title: 'Investigate',
    items: [
      { to: '/cases', icon: <Briefcase className="w-5 h-5" />, label: 'Case Management' },
      { to: '/threat-intel', icon: <Crosshair className="w-5 h-5" />, label: 'Threat Intelligence', hint: 'g t' },
      { to: '/watchlist', icon: <List className="w-5 h-5" />, label: 'Watchlists', hint: 'g w' },
      { to: '/mitre', icon: <Target className="w-5 h-5" />, label: 'ATT&CK Coverage', hint: 'g m' },
      { to: '/assets', icon: <Monitor className="w-5 h-5" />, label: 'Asset Inventory' },
    ],
  },
  {
    title: 'Detect',
    items: [
      { to: '/rules', icon: <BookOpen className="w-5 h-5" />, label: 'Detection Rules', hint: 'g r' },
      { to: '/ueba', icon: <Brain className="w-5 h-5" />, label: 'Behavior Analytics' },
      { to: '/playbooks', icon: <Zap className="w-5 h-5" />, label: 'Response Playbooks' },
    ],
  },
  {
    title: 'Collect & Manage',
    items: [
      { to: '/connectors', icon: <Cloud className="w-5 h-5" />, label: 'Data Sources' },
      { to: '/compliance', icon: <ShieldCheck className="w-5 h-5" />, label: 'Compliance Reports' },
      { to: '/settings', icon: <Settings className="w-5 h-5" />, label: 'System Settings' },
    ],
  },
];

interface SidebarProps {
  onClose?: () => void;
  onHelpOpen?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ onClose, onHelpOpen }) => {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [openAlertCount, setOpenAlertCount] = useState(0);
  const sseRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const check = async () => {
      const online = await checkBackendHealth();
      setBackendOnline(online);
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

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

  useEffect(() => {
    if (location.pathname === '/alerts') {
      setOpenAlertCount(0);
    }
  }, [location.pathname]);

  const renderItem = (item: Omit<NavItem, 'badge'>) => {
    const badge = item.to === '/alerts' ? openAlertCount || undefined : undefined;
    const isActive = item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);

    return (
      <NavLink
        key={item.to}
        to={item.to}
        onClick={onClose}
        title={item.hint ? `${item.label} (${item.hint})` : item.label}
        className={`group flex items-center gap-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150 border-l-2 pl-3 ${
          isActive
            ? 'bg-cyber-accent/10 text-cyber-accent border-l-cyber-accent'
            : 'text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 border-l-transparent'
        }`}
      >
        <span className={`transition-colors ${isActive ? 'text-cyber-accent' : 'text-cyber-muted group-hover:text-cyber-text'}`}>
          {item.icon}
        </span>
        <span className="flex-1">{item.label}</span>
        {item.hint && !badge && (
          <span className="hidden group-hover:flex items-center gap-0.5 opacity-60">
            {item.hint.split(' ').map((k, i) => (
              <kbd key={i} className="text-[9px] font-mono px-1 py-0.5 rounded bg-cyber-border text-cyber-muted">{k}</kbd>
            ))}
          </span>
        )}
        {badge != null && badge > 0 && (
          <span className="min-w-[20px] h-5 px-1 rounded-full bg-cyber-danger text-white text-[10px] font-bold flex items-center justify-center">
            {badge > 99 ? '99+' : badge}
          </span>
        )}
      </NavLink>
    );
  };

  return (
    <aside className="w-72 h-full min-h-screen bg-cyber-card border-r border-cyber-border flex flex-col">
      <div className="flex items-center gap-3 px-6 py-5 border-b border-cyber-border">
        <div className="w-9 h-9 rounded-lg bg-cyber-accent/10 border border-cyber-accent/30 flex items-center justify-center flex-shrink-0">
          <Shield className="w-5 h-5 text-cyber-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-lg font-bold text-cyber-text tracking-tight">SiemLess</span>
          <div className="text-[10px] font-mono text-cyber-muted tracking-widest uppercase">SOC Command Center</div>
        </div>
        <button
          onClick={toggleTheme}
          className="p-1.5 rounded-md text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 transition-colors flex-shrink-0"
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
        <button
          onClick={onClose}
          className="lg:hidden p-1 text-cyber-muted hover:text-cyber-text transition-colors flex-shrink-0"
          aria-label="Close menu"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto" aria-label="Main navigation">
        {NAV_GROUPS.map((group) => (
          <div key={group.title}>
            <div className="px-3 mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-cyber-muted/60">
              {group.title}
            </div>
            <div className="space-y-0.5">
              {group.items.map(renderItem)}
            </div>
          </div>
        ))}
      </nav>

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
