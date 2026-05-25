import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import { Search as SearchIcon, Clock, Tag, Lightbulb, X } from 'lucide-react';
import { searchEvents } from '../api/search';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import { TableSkeleton } from '../components/shared/LoadingSpinner';
import EmptyState from '../components/shared/EmptyState';
import Pagination from '../components/shared/Pagination';
import EventDetailPanel from './EventDetail';

const SEARCH_EXAMPLES = [
  { label: 'Failed login attempts', query: 'category:authentication AND severity:high' },
  { label: 'Critical events', query: 'severity:critical' },
  { label: 'Specific IP', query: 'source_ip:192.168.1.1' },
  { label: 'Network events', query: 'category:network AND severity:high' },
  { label: 'Privileged user', query: 'username:root OR username:admin' },
  { label: 'Port scan detection', query: 'event_type:port_scan' },
  { label: 'Malware category', query: 'category:malware' },
  { label: 'Windows events', query: 'log_type:windows' },
];

const Search: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [submittedQuery, setSubmittedQuery] = useState(searchParams.get('q') || '');
  const [page, setPage] = useState(1);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  useEffect(() => {
    const q = searchParams.get('q');
    if (q) {
      setQuery(q);
      setSubmittedQuery(q);
    }
  }, [searchParams]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['search', submittedQuery, page],
    queryFn: () => searchEvents(submittedQuery, page, 50),
    enabled: !!submittedQuery.trim(),
  });

  const handleSearch = (q?: string) => {
    const searchQ = q ?? query;
    if (!searchQ.trim()) return;
    setSubmittedQuery(searchQ.trim());
    setQuery(searchQ.trim());
    setPage(1);
    setSearchParams({ q: searchQ.trim() });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch();
  };

  const clearSearch = () => {
    setQuery('');
    setSubmittedQuery('');
    setPage(1);
    setSearchParams({});
  };

  const formatTs = (ts: string) => {
    try {
      return format(parseISO(ts), 'MM-dd HH:mm:ss');
    } catch {
      return ts;
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-cyber-text mb-1">Search</h1>
        <p className="text-sm text-cyber-muted">Full-text search across all security events</p>
      </div>

      {/* Search Input */}
      <div className="cyber-card p-4 mb-6">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-cyber-muted" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder='Search logs... (e.g. source_ip:192.168.1.1 AND severity:high)'
              className="cyber-input w-full pl-10 pr-10 py-3 text-sm"
              autoFocus
            />
            {query && (
              <button
                onClick={clearSearch}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-cyber-muted hover:text-cyber-text"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <button
            onClick={() => handleSearch()}
            disabled={!query.trim()}
            className="cyber-btn-primary px-6"
          >
            Search
          </button>
        </div>

        {/* Result count */}
        {data && submittedQuery && (
          <div className="mt-3 flex items-center gap-3 text-xs text-cyber-muted">
            <Clock className="w-3.5 h-3.5" />
            <span>
              Found <span className="text-cyber-text font-semibold">{data.total.toLocaleString()}</span> results
              for <span className="text-cyber-accent">"{submittedQuery}"</span>
              {data.took_ms !== undefined && (
                <span> in <span className="text-cyber-text">{data.took_ms}ms</span></span>
              )}
            </span>
          </div>
        )}
      </div>

      {/* Examples / Empty State */}
      {!submittedQuery && (
        <div className="cyber-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Lightbulb className="w-4 h-4 text-cyber-accent" />
            <h3 className="text-sm font-semibold text-cyber-text">Search Examples</h3>
          </div>
          <p className="text-xs text-cyber-muted mb-4">
            Use field:value syntax or natural language. Combine with AND, OR, NOT operators.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {SEARCH_EXAMPLES.map((example) => (
              <button
                key={example.query}
                onClick={() => {
                  setQuery(example.query);
                  handleSearch(example.query);
                }}
                className="flex items-start gap-3 p-3 rounded-lg bg-cyber-bg/50 border border-cyber-border/50 hover:border-cyber-accent/30 hover:bg-cyber-accent/5 transition-all text-left group"
              >
                <SearchIcon className="w-4 h-4 text-cyber-muted group-hover:text-cyber-accent flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-cyber-text group-hover:text-cyber-accent">
                    {example.label}
                  </p>
                  <p className="text-xs text-cyber-muted font-mono mt-0.5">{example.query}</p>
                </div>
              </button>
            ))}
          </div>

          <div className="mt-6 pt-4 border-t border-cyber-border/50">
            <h4 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-3">Searchable Fields</h4>
            <div className="flex flex-wrap gap-2">
              {['source_ip', 'destination_ip', 'hostname', 'username', 'severity', 'category', 'log_type', 'event_type', 'message', 'tags'].map((f) => (
                <span key={f} className="text-xs px-2 py-1 bg-cyber-border/40 text-cyber-muted rounded font-mono">
                  {f}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {submittedQuery && (
        <div className="cyber-card overflow-hidden">
          {isLoading ? (
            <TableSkeleton rows={10} cols={7} />
          ) : isError ? (
            <div className="p-8 text-center">
              <p className="text-cyber-danger">{(error as Error).message}</p>
            </div>
          ) : data?.items.length === 0 ? (
            <EmptyState
              title="No results found"
              description={`No events matched "${submittedQuery}". Try a different search term.`}
              icon={<SearchIcon className="w-8 h-8 text-cyber-muted" />}
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px]">
                  <thead>
                    <tr className="border-b border-cyber-border bg-cyber-bg/30">
                      <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider whitespace-nowrap">Timestamp</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Severity</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Source IP</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Hostname</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Category</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Log Type</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Message</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Tags</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cyber-border/30">
                    {data?.items.map((event) => (
                      <tr
                        key={event.id}
                        onClick={() => setSelectedEventId(event.id)}
                        className="table-row-hover"
                      >
                        <td className="px-4 py-2.5 font-mono text-xs text-cyber-muted whitespace-nowrap">
                          {formatTs(event.timestamp)}
                        </td>
                        <td className="px-4 py-2.5">
                          <SeverityBadge severity={event.severity} size="sm" />
                        </td>
                        <td className="px-4 py-2.5 font-mono text-xs text-cyber-accent whitespace-nowrap">
                          {event.source_ip || '—'}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-xs text-cyber-text">
                          {event.hostname || '—'}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-cyber-text">{event.category}</td>
                        <td className="px-4 py-2.5 text-xs text-cyber-muted">{event.log_type}</td>
                        <td className="px-4 py-2.5 text-xs text-cyber-text max-w-xs">
                          <span className="truncate block" title={event.message}>
                            {event.message}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          {event.tags.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {event.tags.slice(0, 2).map((tag) => (
                                <span key={tag} className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 bg-cyber-border/40 text-cyber-muted rounded font-mono">
                                  <Tag className="w-2.5 h-2.5" />
                                  {tag}
                                </span>
                              ))}
                              {event.tags.length > 2 && (
                                <span className="text-[10px] text-cyber-muted">+{event.tags.length - 2}</span>
                              )}
                            </div>
                          ) : (
                            <span className="text-cyber-muted/40">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data && (
                <Pagination
                  page={data.page}
                  pages={data.pages}
                  total={data.total}
                  pageSize={data.page_size}
                  onPageChange={setPage}
                />
              )}
            </>
          )}
        </div>
      )}

      {selectedEventId && (
        <EventDetailPanel
          eventId={selectedEventId}
          onClose={() => setSelectedEventId(null)}
        />
      )}
    </div>
  );
};

export default Search;
