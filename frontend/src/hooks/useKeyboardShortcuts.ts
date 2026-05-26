import { useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

export interface ShortcutHandler {
  /** called when the shortcut fires */
  onHelp: () => void;
  /** called when Escape is pressed (close modal, deselect row, etc.) */
  onEscape?: () => void;
}

/**
 * Global keyboard shortcut handler.
 *
 * Navigation (g-prefixed, Vim-style):
 *   g d  → Dashboard
 *   g e  → Events
 *   g a  → Alerts
 *   g r  → Rules
 *   g s  → Search
 *   g t  → Threat Intel
 *   g m  → MITRE ATT&CK
 *   g w  → Watchlist
 *
 * Global:
 *   ?    → show keyboard shortcuts help modal
 *   Esc  → dismiss / clear (delegates to onEscape)
 *
 * Disabled when focus is inside an input, textarea, or select.
 */
export function useKeyboardShortcuts({ onHelp, onEscape }: ShortcutHandler) {
  const navigate = useNavigate();
  const gPressedRef = useRef(false);
  const gTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isTyping = useCallback(() => {
    const el = document.activeElement;
    if (!el) return false;
    const tag = el.tagName.toLowerCase();
    return (
      tag === 'input' ||
      tag === 'textarea' ||
      tag === 'select' ||
      (el as HTMLElement).isContentEditable
    );
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Never intercept when user is typing
      if (isTyping()) return;
      // Never intercept modified keys (Ctrl, Alt, Meta)
      if (e.ctrlKey || e.altKey || e.metaKey) return;

      const key = e.key;

      // --- Escape ---
      if (key === 'Escape') {
        gPressedRef.current = false;
        if (gTimerRef.current) clearTimeout(gTimerRef.current);
        onEscape?.();
        return;
      }

      // --- Help modal ---
      if (key === '?') {
        e.preventDefault();
        onHelp();
        return;
      }

      // --- g-prefix navigation ---
      if (gPressedRef.current) {
        gPressedRef.current = false;
        if (gTimerRef.current) clearTimeout(gTimerRef.current);
        e.preventDefault();
        switch (key.toLowerCase()) {
          case 'd': navigate('/');           break;
          case 'e': navigate('/events');     break;
          case 'a': navigate('/alerts');     break;
          case 'r': navigate('/rules');      break;
          case 's': navigate('/search');     break;
          case 't': navigate('/threat-intel'); break;
          case 'm': navigate('/mitre');      break;
          case 'w': navigate('/watchlist');  break;
        }
        return;
      }

      if (key.toLowerCase() === 'g') {
        gPressedRef.current = true;
        // Reset if second key not pressed within 800 ms
        gTimerRef.current = setTimeout(() => {
          gPressedRef.current = false;
        }, 800);
      }
    };

    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
      if (gTimerRef.current) clearTimeout(gTimerRef.current);
    };
  }, [navigate, onHelp, onEscape, isTyping]);
}
