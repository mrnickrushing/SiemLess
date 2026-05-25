import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import {
  Bell,
  ChevronDown,
  X,
  User,
  Server,
  Shield,
  Clock,
  Hash,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { getAlerts, getAlert, updateAlert } from '../api/alerts';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import { StatusBadge } from '../components/shared/StatusBadge';
import { TableSkeleton, LoadingSpinner } from '../components/shared/LoadingSpinner';
import EmptyState from '../components/shared/EmptyState';
import Pagination from '../components/shared/Pagination';
import type { Alert, AlertFilters, AlertStatus, Severity, AlertUpdateData } from '../types';

const STATUSES: AlertStatus[] = ['open', 'investigating', 'resolved', 'false_positive'];
const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

const AlertDetailPanel: React.FC<{ alertId: string; onClose: () => void }> = ({
  alertId,
  onClose,
}) => {
  const queryClient = useQueryClient();
  const [editStatus, setEditStatus] = useState<AlertStatus | ''>('');
  const [assignTo, setAssignTo] = useState('');
  const [notes, setNotes] = useState('');
  const [fpReason, setFpReason] = useState('');

  const { data: alert, isLoading, isError } = useQuery({
    queryKey: ['alert', alertId],
    queryFn: () => getAlert(alertId),
    enabled: !!alertId,
    onSuccess: (data: Alert) => {
      setEditStatus(data.status);
      setAssignTo(data.assigned_to || '');
      setNotes(data.notes || '');
      setFpReason(data.false_positive_reason || '');
    },
  } as Parameters<typeof useQuery>[0]);

  const mutation = useMutation({
    mutationFn: (data: AlertUpdateData) => updateAlert(alertId, data),
    onSuccess: () => {
      toast.success('Alert updated');
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['alert', alertId] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleSave = () => {
    const updateData: AlertUpdateData = {};
    if (editStatus) updateData.status = editStatus as AlertStatus;
    if (assignTo) updateData.assigned_to = assignTo;
    if (notes) updateData.notes = notes;
    if (fpReason) updateData.false_positive_reason = fpReason;
    mutation.mutate(updateData);
  };

  const formatTs = (ts: string | null) => {
    if (!ts) return '—';
    try {
      return format(parseISO(ts), 'yyyy-MM-dd HH:mm:ss');
    } catch {
      return ts;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="w-full max-w-2xl bg-cyber-card border-l border-cyber-border flex flex-col shadow-2xl animate-fade-in">
        <div className="flex items-center justify-between px-6 py-4 border-b border-cyber-border flex-shrink-0">
          <h2 className="text-base font-semibold text-cyber-text">Alert Detail</h2>
          <button onClick={onClose} className="p-2 rounded text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-20">
              <LoadingSpinner size="lg" />
            </div>
          )}
          {isError && <div className="p-6 text-cyber-danger">Failed to load alert</div>}
          {alert && (
            <div className="p-6 space-y-6">
              {/* Title and badges */}
              <div>
                <h3 className="text-lg font-semibold text-cyber-text mb-2">{alert.title}</h3>
                <div className="flex items-center gap-2 flex-wrap">
                  <SeverityBadge severity={alert.severity} />
                  <StatusBadge status={alert.status} />
                  {alert.rule_name && (
                    <span className="text-xs text-cyber-muted bg-cyber-border/40 px-2 py-0.5 rounded font-mono">
                      {alert.rule_name}
                    </span>
                  )}
                </div>
              </div>

              {alert.description && (
                <p className="text-sm text-cyber-muted bg-cyber-bg/50 border border-cyber-border/50 rounded-lg p-3">
                  {alert.description}
                </p>
              )}

              {/* Meta Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-xs text-cyber-muted mb-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    Created
                  </div>
                  <p className="text-sm text-cyber-text font-mono">{formatTs(alert.created_at)}</p>
                </div>
                <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-xs text-cyber-muted mb-1.5">
                    <Hash className="w-3.5 h-3.5" />
                    Events
                  </div>
                  <p className="text-sm text-cyber-text font-semibold">{alert.event_count}</p>
                </div>
                {alert.source_ips.length > 0 && (
                  <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 text-xs text-cyber-muted mb-1.5">
                      <Server className="w-3.5 h-3.5" />
                      Source IPs
                    </div>
                    <div className="space-y-0.5">
                      {alert.source_ips.map((ip) => (
                        <p key={ip} className="text-xs text-cyber-accent font-mono">{ip}</p>
                      ))}
                    </div>
                  </div>
                )}
                {alert.affected_users.length > 0 && (
                  <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 text-xs text-cyber-muted mb-1.5">
                      <User className="w-3.5 h-3.5" />
                      Affected Users
                    </div>
                    <div className="space-y-0.5">
                      {alert.affected_users.map((u) => (
                        <p key={u} className="text-xs text-cyber-text font-mono">{u}</p>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* MITRE */}
              {(alert.mitre_tactic || alert.mitre_technique) && (
                <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-xs text-cyber-muted mb-2">
                    <Shield className="w-3.5 h-3.5" />
                    MITRE ATT&CK
                  </div>
                  {alert.mitre_tactic && (
                    <div className="flex gap-2 text-xs">
                      <span className="text-cyber-muted">Tactic:</span>
                      <span className="text-cyber-text font-mono">{alert.mitre_tactic}</span>
                    </div>
                  )}
                  {alert.mitre_technique && (
                    <div className="flex gap-2 text-xs mt-1">
                      <span className="text-cyber-muted">Technique:</span>
                      <span className="text-cyber-text font-mono">{alert.mitre_technique}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Quick Actions */}
              <div className="border-t border-cyber-border pt-4">
                <h4 className="text-sm font-semibold text-cyber-text mb-3">Quick Actions</h4>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-cyber-muted block mb-1">Status</label>
                    <select
                      value={editStatus}
                      onChange={(e) => setEditStatus(e.target.value as AlertStatus)}
                      className="cyber-select w-full"
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-cyber-muted block mb-1">Assign To</label>
                    <input
                      type="text"
                      value={assignTo}
                      onChange={(e) => setAssignTo(e.target.value)}
                      placeholder="analyst@example.com"
                      className="cyber-input w-full"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-cyber-muted block mb-1">Notes</label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={3}
                      placeholder="Add investigation notes..."
                      className="cyber-input w-full resize-none"
                    />
                  </div>
                  {(editStatus === 'false_positive') && (
                    <div>
                      <label className="text-xs text-cyber-muted block mb-1">False Positive Reason</label>
                      <input
                        type="text"
                        value={fpReason}
                        onChange={(e) => setFpReason(e.target.value)}
                        placeholder="Why is this a false positive?"
                        className="cyber-input w-full"
                      />
                    </div>
                  )}
                  <div className="flex justify-end gap-2 pt-1">
                    <button onClick={onClose} className="cyber-btn-secondary">
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={mutation.isPending}
                      className="cyber-btn-primary"
                    >
                      {mutation.isPending ? 'Saving...' : 'Save Changes'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Alerts: React.FC = () => {
  const [filters, setFilters] = useState<AlertFilters>({ page: 1, page_size: 20 });
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['alerts', filters],
    queryFn: () => getAlerts(filters),
    refetchInterval: 30000,
  });

  const formatTs = (ts: string) => {
    try {
      return format(parseISO(ts), 'MMM dd, HH:mm');
    } catch {
      return ts;
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-cyber-text">Alerts</h1>
          <p className="text-sm text-cyber-muted mt-1">
            {data ? `${data.total.toLocaleString()} alerts` : 'Security alerts management'}
          </p>
        </div>
        <button onClick={() => refetch()} disabled={isFetching} className="flex items-center gap-2 cyber-btn-secondary">
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="cyber-card p-4 mb-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div>
            <label className="text-[10px] text-cyber-muted uppercase tracking-wider block mb-1">Status</label>
            <select
              value={filters.status || ''}
              onChange={(e) =>
                setFilters((f) => ({ ...f, status: (e.target.value as AlertStatus) || undefined, page: 1 }))
              }
              className="cyber-select text-sm"
            >
              <option value="">All Statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-cyber-muted uppercase tracking-wider block mb-1">Severity</label>
            <select
              value={filters.severity || ''}
              onChange={(e) =>
                setFilters((f) => ({ ...f, severity: (e.target.value as Severity) || undefined, page: 1 }))
              }
              className="cyber-select text-sm"
            >
              <option value="">All Severities</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>
          {(filters.status || filters.severity) && (
            <button
              onClick={() => setFilters({ page: 1, page_size: 20 })}
              className="mt-4 text-xs text-cyber-muted hover:text-cyber-text flex items-center gap-1"
            >
              <X className="w-3.5 h-3.5" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Alert Cards */}
      {isLoading ? (
        <div className="cyber-card">
          <TableSkeleton rows={8} cols={5} />
        </div>
      ) : isError ? (
        <div className="cyber-card p-8 text-center">
          <AlertTriangle className="w-8 h-8 text-cyber-danger mx-auto mb-2" />
          <p className="text-cyber-danger">{(error as Error).message}</p>
        </div>
      ) : data?.items.length === 0 ? (
        <EmptyState
          title="No alerts found"
          description="No alerts match your current filters."
          icon={<Bell className="w-8 h-8 text-cyber-muted" />}
        />
      ) : (
        <div className="space-y-3">
          {data?.items.map((alert) => (
            <div
              key={alert.id}
              onClick={() => setSelectedAlertId(alert.id)}
              className={`cyber-card p-4 cursor-pointer hover:border-cyber-border/80 transition-all ${
                alert.status === 'resolved' || alert.status === 'false_positive'
                  ? 'opacity-60'
                  : alert.severity === 'critical'
                  ? 'border-red-800/40 hover:border-red-700/60'
                  : ''
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <SeverityBadge severity={alert.severity} size="sm" />
                    <StatusBadge status={alert.status} size="sm" />
                    {alert.mitre_tactic && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-purple-900/30 text-purple-400 border border-purple-700/30 rounded font-mono">
                        {alert.mitre_tactic}
                      </span>
                    )}
                    {alert.mitre_technique && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-purple-900/20 text-purple-400/80 border border-purple-700/20 rounded font-mono">
                        {alert.mitre_technique}
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-cyber-text mb-1">{alert.title}</h3>
                  {alert.description && (
                    <p className="text-xs text-cyber-muted line-clamp-1">{alert.description}</p>
                  )}
                </div>
                <ChevronDown className="w-4 h-4 text-cyber-muted rotate-[-90deg] flex-shrink-0 mt-0.5" />
              </div>
              <div className="flex items-center gap-4 mt-3 flex-wrap">
                <div className="flex items-center gap-1.5 text-xs text-cyber-muted">
                  <Clock className="w-3 h-3" />
                  {formatTs(alert.created_at)}
                </div>
                {alert.source_ips.length > 0 && (
                  <div className="flex items-center gap-1.5 text-xs text-cyber-muted">
                    <Server className="w-3 h-3" />
                    <span className="font-mono text-cyber-accent">{alert.source_ips[0]}</span>
                    {alert.source_ips.length > 1 && (
                      <span className="text-cyber-muted/60">+{alert.source_ips.length - 1}</span>
                    )}
                  </div>
                )}
                {alert.affected_users.length > 0 && (
                  <div className="flex items-center gap-1.5 text-xs text-cyber-muted">
                    <User className="w-3 h-3" />
                    {alert.affected_users[0]}
                    {alert.affected_users.length > 1 && (
                      <span className="text-cyber-muted/60">+{alert.affected_users.length - 1}</span>
                    )}
                  </div>
                )}
                {alert.assigned_to && (
                  <div className="flex items-center gap-1.5 text-xs text-cyber-muted">
                    <span>Assigned:</span>
                    <span className="text-cyber-text">{alert.assigned_to}</span>
                  </div>
                )}
                <div className="flex items-center gap-1 text-xs text-cyber-muted ml-auto">
                  <Hash className="w-3 h-3" />
                  {alert.event_count} events
                </div>
              </div>
            </div>
          ))}

          {data && (
            <div className="cyber-card overflow-hidden">
              <Pagination
                page={data.page}
                pages={data.pages}
                total={data.total}
                pageSize={data.page_size}
                onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
              />
            </div>
          )}
        </div>
      )}

      {selectedAlertId && (
        <AlertDetailPanel
          alertId={selectedAlertId}
          onClose={() => setSelectedAlertId(null)}
        />
      )}
    </div>
  );
};

export default Alerts;
