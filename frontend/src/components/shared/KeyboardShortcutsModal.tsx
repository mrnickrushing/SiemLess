import React, { useEffect } from 'react';
import { X, Keyboard } from 'lucide-react';

interface ShortcutRowProps {
  keys: string[];
  description: string;
}

const Kbd: React.FC<{ k: string }> = ({ k }) => (
  <kbd className="inline-flex items-center justify-center min-w-[26px] h-[22px] px-1.5 rounded
    bg-cyber-border border border-cyber-border/80 text-cyber-text text-[11px] font-mono
    shadow-[0_1px_0_0_rgba(0,0,0,0.4)] font-semibold">
    {k}
  </kbd>
);

const ShortcutRow: React.FC<ShortcutRowProps> = ({ keys, description }) => (
  <div className="flex items-center justify-between gap-4 py-2 border-b border-cyber-border/30 last:border-0">
    <span className="text-xs text-cyber-muted">{description}</span>
    <div className="flex items-center gap-1 flex-shrink-0">
      {keys.map((k, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="text-cyber-muted/40 text-[10px] mx-0.5">then</span>}
          <Kbd k={k} />
        </React.Fragment>
      ))}
    </div>
  </div>
);

const SECTIONS = [
  {
    title: 'Navigation',
    shortcuts: [
      { keys: ['g', 'd'], description: 'Go to Dashboard' },
      { keys: ['g', 'e'], description: 'Go to Events' },
      { keys: ['g', 'a'], description: 'Go to Alerts' },
      { keys: ['g', 'r'], description: 'Go to Rules' },
      { keys: ['g', 's'], description: 'Go to Search' },
      { keys: ['g', 't'], description: 'Go to Threat Intel' },
      { keys: ['g', 'm'], description: 'Go to MITRE ATT&CK' },
      { keys: ['g', 'w'], description: 'Go to Watchlist' },
    ],
  },
  {
    title: 'Tables',
    shortcuts: [
      { keys: ['j'], description: 'Move selection down' },
      { keys: ['k'], description: 'Move selection up' },
      { keys: ['↵'], description: 'Open selected row' },
      { keys: ['Esc'], description: 'Clear selection' },
    ],
  },
  {
    title: 'Global',
    shortcuts: [
      { keys: ['/'], description: 'Focus search input' },
      { keys: ['?'], description: 'Show this help' },
      { keys: ['Esc'], description: 'Dismiss / close' },
    ],
  },
];

interface KeyboardShortcutsModalProps {
  open: boolean;
  onClose: () => void;
}

const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({ open, onClose }) => {
  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative w-full max-w-md bg-cyber-card border border-cyber-border rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-cyber-border">
          <div className="flex items-center gap-2.5">
            <Keyboard className="w-4 h-4 text-cyber-accent" />
            <h2 className="text-sm font-semibold text-cyber-text">Keyboard Shortcuts</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-cyber-muted hover:text-cyber-text transition-colors rounded"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
          {SECTIONS.map((section) => (
            <div key={section.title}>
              <p className="text-[10px] font-semibold text-cyber-accent uppercase tracking-widest mb-2">
                {section.title}
              </p>
              <div>
                {section.shortcuts.map((s) => (
                  <ShortcutRow key={s.description} keys={s.keys} description={s.description} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="px-5 py-3 border-t border-cyber-border bg-cyber-bg/40">
          <p className="text-[11px] text-cyber-muted/60 text-center">
            Press <Kbd k="?" /> at any time to show this panel
          </p>
        </div>
      </div>
    </div>
  );
};

export default KeyboardShortcutsModal;
