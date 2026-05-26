import React, { useState, useCallback, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { format, parseISO, subDays } from 'date-fns';
import { Filter, RefreshCw, Play, Pause, Tag } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getEvents, getEventCategories, getEventLogTypes } from '../api/events';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import { TableSkeleton } from '../components/shared/LoadingSpinner';
import EmptyState from '../components/shared/EmptyState';
import Pagination from '../components/shared/Pagination';
import type { EventFilters, Severity } from '../types';

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

const Events: React.FC = () => {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<EventFilters>({
    page: 1,
    page_size: 50,
  });
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [sourceIpInput, setSourceIpInput] = useState('');
  const [hostnameInput, setHostnameInput] = useState('');

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['events', filters],
    queryFn: () => getEvents(filters),
    refetchInterval: autoRefresh ? 10000 : false,
  });

  const { data: categories } = useQuery({
    queryKey: ['event-categories'],
    queryFn: getEventCategories,
    staleTime: 300000,
  });

  const { data: logTypes } = useQuery({
    queryKey: ['event-log-types'],
    queryFn: getEventLogTypes,
    staleTime: 300000,
  });

  // Build and apply a complete filter object — avoids stale closure dropping
  // source_ip / hostname when dropdowns change independently.
  const buildFilters = useCallback(
    (overrides: Partial<EventFilters> = {}): EventFilters => ({
      page: 1,
      page_size: 50,
      ...(filters.severity ? { severity: filters.severity } : {}),
      ...(filters.category ? { category: filters.category } : {}),
      ...(filters.log_type ? { log_type: filters.log_type } : {}),
      ...(sourceIpInput.trim() ? { source_ip: sourceIpInput.trim() } : {}),
      ...(hostnameInput.trim() ? { hostname: hostnameInput.trim() } : {}),
      ...(startDate ? { start_time: new Date(startDate).toISOString() } : {}),
      ...(endDate ? { end_time: new Date(endDate).toISOString() } : {}),
      ...overrides,
    }),
    [filters.severity, filters.category, filters.log_type, sourceIpInput, hostnameInput, startDate, endDate]
  );

  const applyFilters = useCallback(() => {
    setFilters(buildFilters());
  }, [buildFilters]);

  const resetFilters = () => {
    setFilters({ page: 1, page_size: 50 });
    setSourceIpInput('');
    setHostnameInput('');
    setStartDate('');
    setEndDate('');
  };

  const formatTs = (ts: string) => {
    try {
      return format(parseISO(ts), 'MM-dd HH:mm:ss');
    } catch {
      return ts;
    }
  };

  const setQuickRange = (hours: number) => {
    const end = new Date();
    const start = subDays(end, hours / 24);
    setStartDate(format(start, "yyyy-MM-dd'T'HH:mm"));
    setEndDate(format(end, "yyyy-MM-dd'T'HH:mm"));
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-cyber-text">Events</h1>
          <p className="text-sm text-cyber-muted mt-1">
            {data ? `${data.total.toLocaleString()} total events` : 'Security events log'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`flex items-center gap-2 text-sm px-3 py-2 rounded-md border transition-colors ${
              autoRefresh
                ? 'bg-cyber-accent/10 border-cyber-accent/30 text-cyber-accent'
                : 'bg-cyber-card border-cyber-border text-cyber-muted hover:text-cyber-text'
            }`}
          >
            {autoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh'}
          </button>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 cyber-btn-secondary"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="cyber-card p-4 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-cyber-muted" />
          <span className="text-xs font-medium text-cyber-muted uppercase tracking-wider">Filters</span>
          <div className="flex gap-2 ml-3">
            {[1, 6, 24, 72].map((h) => (
              <button
                key={h}
                onClick={() => setQuickRange(h)}
                className="text-[11px] px-2 py-0.5 rounded bg-cyber-border/40 text-cyber-muted hover:text-cyber-accent hover:bg-cyber-border transition-colors font-mono"
              >
                {h < 24 ? `${h}h` : `${h / 24}d`}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
          <div>
            <label className="text-[10px] text-cyber-muted uppercase tracking-wider block mb-1">Start Time</label>
            <input
              type="datetime-local"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="cyber-input w-full text-xs"
            />
          </div>
          <div>
            <label className="text-[10px] text-cyber-muted uppercase tracking-wider block mb-1">End Time</label>
            <input
              type="datetime-local"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="cyber-input w-full text-xs"
            />
          </div>
          <div>
            <label className="text-[10px] text-cyber-muted uppercase tracking-wider block mb-1">Severity</label>
            <select
              value={filters.severity || ''}
              onChange={(e) => {
                const next = buildFilters({ severity: (e.target.value as Severity) || undefined });
                setFilters(next);
              }}
              className="cyber-select w-full text-xs"
            >
              <option value="">All Severities</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-cyber-muted uppercase tracking-wider block mb-1">Category</label>
            <select
              value={filters.category || ''}
              onChange={(e) => {
                const next = buildFilters({ category: e.target.value || undefined });
                setFilters(next);
              }}
              className="cyber-select w-full text-xs"
            >
              <option value="">All Categories</option>
              {categories?.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-cyber-muted uppercase tracking-wider block mb-1">Log Type</label>
            <select
              value={filters.log_type || ''}
              onChange={(e) => {
                const next = buildFilters({ log_type: e.target.value || undefined });
                setFilters(next);
              }}
              className="cyber-select w-full text-xs"
            >
              <option value="">All Log Types</option>
              {logTypes?.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-cyber-muted uppercase tracking-wider block mb-1">Source IP</label>
            <input
              type="text"
              value={sourceIpInput}
              onChange={(e) => setSourceIpInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applyFilters()}
              placeholder="192.168.1.1"
              className="cyber-input w-full text-xs font-mono"
            />
          </div>
        </div>
        <div className="flex items-center justify-between mt-3">
          <div className="flex-1 max-w-xs">
            <input
              type="text"
              value={hostnameInput}
              onChange={(e) => setHostnameInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applyFilters()}
              placeholder="Hostname filter..."
              className="cyber-input w-full text-xs"
            />
          </div>
          <div className="flex gap-2">
            <button onClick={resetFilters} className="cyber-btn-secondary text-xs px-3 py-1.5">Reset</button>
            <button onClick={applyFilters} className="cyber-btn-primary text-xs px-3 py-1.5">Apply Filters</button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="cyber-card overflow-hidden">
        {isLoading ? (
          <TableSkeleton rows={10} cols={7} />
        ) : isError ? (
          <div className="p-8 text-center">
            <p className="text-cyber-danger">{(error as Error).message}</p>
          </div>
        ) : data?.items.length === 0 ? (
          <EmptyState title="No events found" description="Try adjusting your filters or time range." />
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
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider w-full">Message</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Tags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cyber-border/30">
                  {data?.items.map((event) => (
                    <tr key={event.id} onClick={() => navigate(`/events/${event.id}`)} className="table-row-hover">
                      <td className="px-4 py-2.5 font-mono text-xs text-cyber-muted whitespace-nowrap">{formatTs(event.timestamp)}</td>
                      <td className="px-4 py-2.5"><SeverityBadge severity={event.severity} size="sm" /></td>
                      <td className="px-4 py-2.5 font-mono text-xs text-cyber-accent whitespace-nowrap">{event.source_ip || '—'}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-cyber-text">{event.hostname || '—'}</td>
                      <td className="px-4 py-2.5 text-xs text-cyber-text">{event.category}</td>
                      <td className="px-4 py-2.5 text-xs text-cyber-muted">{event.log_type}</td>
                      <td className="px-4 py-2.5 text-xs text-cyber-text max-w-sm lg:max-w-xl">
                        <span className="truncate block" title={event.message}>{event.message}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        {event.tags.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {event.tags.slice(0, 2).map((tag) => (
                              <span key={tag} className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 bg-cyber-border/40 text-cyber-muted rounded font-mono">
                                <Tag className="w-2.5 h-2.5" />{tag}
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
                onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
              />
            )}
          </>
        )}
      </div>

    </div>
  );
};

export default Events;
