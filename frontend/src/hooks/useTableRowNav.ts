import { useEffect, useCallback } from 'react';

/**
 * Adds j / k (or ArrowDown / ArrowUp) keyboard navigation to a table.
 *
 * @param rowCount   Total number of rows currently visible
 * @param selectedIndex  Current selected row index (controlled)
 * @param onSelect   Callback when the selection changes
 * @param onOpen     Optional callback when Enter is pressed on a row
 * @param enabled    Set to false to disable (e.g. when a modal is open)
 */
export function useTableRowNav({
  rowCount,
  selectedIndex,
  onSelect,
  onOpen,
  enabled = true,
}: {
  rowCount: number;
  selectedIndex: number | null;
  onSelect: (index: number | null) => void;
  onOpen?: (index: number) => void;
  enabled?: boolean;
}) {
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
    if (!enabled || rowCount === 0) return;

    const handler = (e: KeyboardEvent) => {
      if (isTyping()) return;
      if (e.ctrlKey || e.altKey || e.metaKey) return;

      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        const next =
          selectedIndex === null ? 0 : Math.min(selectedIndex + 1, rowCount - 1);
        onSelect(next);
        return;
      }
      if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        const prev =
          selectedIndex === null ? rowCount - 1 : Math.max(selectedIndex - 1, 0);
        onSelect(prev);
        return;
      }
      if (e.key === 'Enter' && selectedIndex !== null) {
        e.preventDefault();
        onOpen?.(selectedIndex);
        return;
      }
      if (e.key === 'Escape') {
        onSelect(null);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [enabled, rowCount, selectedIndex, onSelect, onOpen, isTyping]);
}
