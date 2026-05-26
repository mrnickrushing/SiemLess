import React, { useState, useCallback } from 'react';
import { Menu, Shield } from 'lucide-react';
import Sidebar from './Sidebar';
import KeyboardShortcutsModal from '../shared/KeyboardShortcutsModal';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const openHelp = useCallback(() => setShortcutsOpen(true), []);
  const closeHelp = useCallback(() => setShortcutsOpen(false), []);

  useKeyboardShortcuts({
    onHelp: openHelp,
    onEscape: closeHelp,
  });

  return (
    <div className="flex min-h-screen bg-cyber-bg">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — drawer on mobile, static on desktop */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 transition-transform duration-300 ease-in-out
          lg:relative lg:translate-x-0 lg:z-auto
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} onHelpOpen={openHelp} />
      </div>

      {/* Main content area */}
      <main className="flex-1 min-w-0 overflow-auto flex flex-col">
        {/* Mobile top bar */}
        <div className="lg:hidden sticky top-0 z-30 flex items-center gap-3 px-4 py-3 bg-cyber-card border-b border-cyber-border">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1 text-cyber-muted hover:text-cyber-text transition-colors"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="w-7 h-7 rounded-lg bg-cyber-accent/10 border border-cyber-accent/30 flex items-center justify-center">
            <Shield className="w-4 h-4 text-cyber-accent" />
          </div>
          <span className="text-sm font-bold text-cyber-text tracking-tight">SiemLess</span>
        </div>

        <div className="flex-1 p-4 lg:p-6">
          {children}
        </div>
      </main>

      {/* Keyboard shortcuts modal */}
      <KeyboardShortcutsModal open={shortcutsOpen} onClose={closeHelp} />
    </div>
  );
};

export default Layout;
