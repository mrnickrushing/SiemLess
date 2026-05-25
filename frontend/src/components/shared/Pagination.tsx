import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

const Pagination: React.FC<PaginationProps> = ({ page, pages, total, pageSize, onPageChange }) => {
  if (pages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  const getPageNumbers = () => {
    const delta = 2;
    const range: (number | string)[] = [];
    for (let i = Math.max(2, page - delta); i <= Math.min(pages - 1, page + delta); i++) {
      range.push(i);
    }
    if (page - delta > 2) range.unshift('...');
    if (page + delta < pages - 1) range.push('...');
    range.unshift(1);
    if (pages > 1) range.push(pages);
    return range;
  };

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-cyber-border">
      <div className="text-xs text-cyber-muted font-mono">
        Showing <span className="text-cyber-text">{start}</span>–
        <span className="text-cyber-text">{end}</span> of{' '}
        <span className="text-cyber-text">{total.toLocaleString()}</span> results
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="p-1.5 rounded text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        {getPageNumbers().map((p, idx) =>
          typeof p === 'string' ? (
            <span key={`ellipsis-${idx}`} className="px-2 text-cyber-muted text-sm">
              {p}
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`min-w-[32px] h-8 px-2 rounded text-sm font-medium transition-colors ${
                p === page
                  ? 'bg-cyber-accent text-cyber-bg'
                  : 'text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40'
              }`}
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          className="p-1.5 rounded text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default Pagination;
