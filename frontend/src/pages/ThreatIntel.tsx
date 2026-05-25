import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import {
  Plus,
  Search,
  Crosshair,
  CheckCircle,
  XCircle,
  Trash2,
  RefreshCw,
  X,
  Upload,
  AlertTriangle,
} from 'lucide-react';
import toast from 'react-hot-toast';
import {
  getThreatIndicators,
  getThreatIntelStats,
  checkThreatIndicator,
  createThreatIndicator,
  deleteThreatIndicator,
} from '../api/threatIntel';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import { TableSkeleton } from '../components/shared/LoadingSpinner';
import EmptyState from '../components/shared/EmptyState';
import ConfirmDialog from '../components/shared/ConfirmDialog';
import Pagination from '../components/shared/Pagination';
import type { IndicatorType, Severity, ThreatIndicator, ThreatIndicatorFormData } from '../types';

const INDICATOR_TYPES: IndicatorType[] = ['ip', 'domain', 'hash', 'url', 'email', 'user_agent'];
const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

const DEFAULT_FORM: ThreatIndicatorFormData = {
  type: 'ip',
  value: '',
  confidence: 80,
  severity: 'high',
  source: '',
  description: '',
  tags: [],
};

const TypeBadge: React.FC<{ type: IndicatorType }> = ({ type }) => {
  const colors: Record<IndicatorType, string> = {
    ip: 'bg-red-900/30 text-red-400 border-red-700/40',
    domain: 'bg-orange-900/30 text-orange-400 border-orange-700/40',
    hash: 'bg-purple-900/30 text-purple-400 border-purple-700/40',
    url: 'bg-blue-900/30 text-blue-400 border-blue-700/40',
    email: 'bg-yellow-900/30 text-yellow-400 border-yellow-700/40',
    user_agent: 'bg-cyan-900/30 text-cyan-400 border-cyan-700/40',
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase font-semibold ${colors[type]}`}>
      {type}
    </span>
  );
};

const ConfidenceBar: React.FC<{ value: number }> = ({ value }) => (
  <div className="flex items-center gap-2">
    <div className="flex-1 h-1.5 bg-cyber-border rounded-full overflow-hidden">
      <div
        className="h-full rounded-full"
        style={{
          width: `${value}%`,
          background: value >= 80 ? '#ff3b3b' : value >= 60 ? '#ff8c00' : '#4a9eff',
        }}
      />
    </div>
    <span className="text-xs font-mono text-cyber-muted w-8 text-right">{value}%</span>
  </div>
);

interface AddIndicatorFormProps {
  onClose: () => void;
  onSaved: () => void;
}

const AddIndicatorForm: React.FC<AddIndicatorFormProps> = ({ onClose, onSaved }) => {
  const [form, setForm] = useState<ThreatIndicatorFormData>(DEFAULT_FORM);
  const [tagsInput, setTagsInput] = useState('');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: ThreatIndicatorFormData) => createThreatIndicator(data),
    onSuccess: () => {
      toast.success('Threat indicator added');
      queryClient.invalidateQueries({ queryKey: ['threat-indicators'] });
      queryClient.invalidateQueries({ queryKey: ['threat-intel-stats'] });
      onSaved();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const setField = <K extends keyof ThreatIndicatorFormData>(
    key: K,
    value: ThreatIndicatorFormData[K]
  ) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
    mutation.mutate({ ...form, tags });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-cyber-card border border-cyber-border rounded-xl shadow-2xl w-full max-w-lg mx-4 animate-fade-in">
        <div className="flex items-center justify-between px-6 py-4 border-b border-cyber-border">
          <h2 className="text-base font-semibold text-cyber-text">Add Threat Indicator</h2>
          <button onClick={onClose} className="p-1.5 rounded text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Type *</label>
              <select
                value={form.type}
                onChange={(e) => setField('type', e.target.value as IndicatorType)}
                className="cyber-select w-full"
              >
                {INDICATOR_TYPES.map((t) => (
                  <option key={t} value={t}>{t.toUpperCase()}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Severity *</label>
              <select
                value={form.severity}
                onChange={(e) => setField('severity', e.target.value as Severity)}
                className="cyber-select w-full"
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-cyber-muted block mb-1">Value *</label>
            <input
              required
              type="text"
              value={form.value}
              onChange={(e) => setField('value', e.target.value)}
              placeholder={form.type === 'ip' ? '192.168.1.1' : form.type === 'domain' ? 'malicious.com' : 'Indicator value...'}
              className="cyber-input w-full font-mono"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Source *</label>
              <input
                required
                type="text"
                value={form.source}
                onChange={(e) => setField('source', e.target.value)}
                placeholder="e.g. VirusTotal, Manual"
                className="cyber-input w-full"
              />
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Confidence: {form.confidence}%</label>
              <input
                type="range"
                min={0}
                max={100}
                value={form.confidence}
                onChange={(e) => setField('confidence', parseInt(e.target.value))}
                className="w-full mt-2 accent-cyber-accent"
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-cyber-muted block mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setField('description', e.target.value)}
              rows={2}
              placeholder="Additional context..."
              className="cyber-input w-full resize-none"
            />
          </div>
          <div>
            <label className="text-xs text-cyber-muted block mb-1">Tags (comma-separated)</label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="apt28, ransomware, c2"
              className="cyber-input w-full font-mono"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="cyber-btn-secondary">Cancel</button>
            <button type="submit" disabled={mutation.isPending} className="cyber-btn-primary">
              {mutation.isPending ? 'Adding...' : 'Add Indicator'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const ThreatIntel: React.FC = () => {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [addFormOpen, setAddFormOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [checkValue, setCheckValue] = useState('');
  const [checkResult, setCheckResult] = useState<{ matched: boolean; indicator: ThreatIndicator | null } | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['threat-indicators', page, typeFilter],
    queryFn: () => getThreatIndicators(page, 50, typeFilter || undefined),
  });

  const { data: stats } = useQuery({
    queryKey: ['threat-intel-stats'],
    queryFn: getThreatIntelStats,
    refetchInterval: 60000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteThreatIndicator(id),
    onSuccess: () => {
      toast.success('Indicator deleted');
      queryClient.invalidateQueries({ queryKey: ['threat-indicators'] });
      queryClient.invalidateQueries({ queryKey: ['threat-intel-stats'] });
      setDeletingId(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleCheck = async () => {
    if (!checkValue.trim()) return;
    setIsChecking(true);
    setCheckResult(null);
    try {
      const result = await checkThreatIndicator(checkValue.trim());
      setCheckResult(result);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setIsChecking(false);
    }
  };

  const formatTs = (ts: string) => {
    try {
      return format(parseISO(ts), 'MMM dd, yyyy');
    } catch {
      return ts;
    }
  };

  const deletingIndicator = data?.items.find((i) => i.id === deletingId);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-cyber-text">Threat Intelligence</h1>
          <p className="text-sm text-cyber-muted mt-1">
            {stats ? `${stats.total.toLocaleString()} indicators (${stats.active} active)` : 'Threat indicators database'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => refetch()} disabled={isFetching} className="cyber-btn-secondary flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => toast('Bulk import coming soon', { icon: '📤' })}
            className="cyber-btn-secondary flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            Import
          </button>
          <button
            onClick={() => setAddFormOpen(true)}
            className="cyber-btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Indicator
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3 mb-6">
          <div className="cyber-card p-3 col-span-2 md:col-span-1">
            <div className="text-xs text-cyber-muted mb-1">Total</div>
            <div className="text-2xl font-bold text-cyber-text">{stats.total.toLocaleString()}</div>
          </div>
          {Object.entries(stats.by_type).map(([type, count]) => (
            <div key={type} className="cyber-card p-3">
              <div className="text-xs text-cyber-muted mb-1 uppercase">{type}</div>
              <div className="text-xl font-bold text-cyber-text">{(count as number).toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}

      {/* Quick Check */}
      <div className="cyber-card p-4 mb-6">
        <h3 className="text-sm font-semibold text-cyber-text mb-3 flex items-center gap-2">
          <Search className="w-4 h-4 text-cyber-accent" />
          Quick Threat Check
        </h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={checkValue}
            onChange={(e) => setCheckValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCheck()}
            placeholder="Enter IP, domain, hash, or URL..."
            className="cyber-input flex-1 font-mono"
          />
          <button
            onClick={handleCheck}
            disabled={isChecking || !checkValue.trim()}
            className="cyber-btn-primary px-6"
          >
            {isChecking ? 'Checking...' : 'Check'}
          </button>
          {checkResult && (
            <button onClick={() => { setCheckResult(null); setCheckValue(''); }} className="p-2 text-cyber-muted hover:text-cyber-text">
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {checkResult && (
          <div className={`mt-4 rounded-lg p-4 border ${checkResult.matched ? 'bg-red-900/20 border-red-700/40' : 'bg-green-900/10 border-green-700/30'}`}>
            {checkResult.matched && checkResult.indicator ? (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <XCircle className="w-5 h-5 text-red-400" />
                  <span className="text-red-400 font-semibold">Threat Match Found!</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-cyber-muted">Type: </span>
                    <TypeBadge type={checkResult.indicator.type} />
                  </div>
                  <div>
                    <span className="text-cyber-muted">Severity: </span>
                    <SeverityBadge severity={checkResult.indicator.severity} size="sm" />
                  </div>
                  <div>
                    <span className="text-cyber-muted">Source: </span>
                    <span className="text-cyber-text">{checkResult.indicator.source}</span>
                  </div>
                  <div>
                    <span className="text-cyber-muted">Confidence: </span>
                    <span className="text-cyber-text font-mono">{checkResult.indicator.confidence}%</span>
                  </div>
                  {checkResult.indicator.description && (
                    <div className="col-span-2">
                      <span className="text-cyber-muted">Description: </span>
                      <span className="text-cyber-text">{checkResult.indicator.description}</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-400" />
                <span className="text-green-400 font-medium">No threat intel match found</span>
                <span className="text-cyber-muted text-sm">— "{checkValue}" is not in the threat database</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="cyber-select text-sm"
        >
          <option value="">All Types</option>
          {INDICATOR_TYPES.map((t) => (
            <option key={t} value={t}>{t.toUpperCase()}</option>
          ))}
        </select>
        {typeFilter && (
          <button
            onClick={() => { setTypeFilter(''); setPage(1); }}
            className="text-xs text-cyber-muted hover:text-cyber-text flex items-center gap-1"
          >
            <X className="w-3.5 h-3.5" />
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="cyber-card overflow-hidden">
        {isLoading ? (
          <TableSkeleton rows={10} cols={7} />
        ) : isError ? (
          <div className="p-8 text-center">
            <AlertTriangle className="w-8 h-8 text-cyber-danger mx-auto mb-2" />
            <p className="text-cyber-danger">{(error as Error).message}</p>
          </div>
        ) : data?.items.length === 0 ? (
          <EmptyState
            title="No threat indicators"
            description="Add your first threat indicator to start tracking IOCs."
            icon={<Crosshair className="w-8 h-8 text-cyber-muted" />}
            action={
              <button onClick={() => setAddFormOpen(true)} className="cyber-btn-primary">
                <Plus className="w-4 h-4 inline mr-1.5" />
                Add Indicator
              </button>
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px]">
                <thead>
                  <tr className="border-b border-cyber-border bg-cyber-bg/30">
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Type</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Value</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Severity</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider w-40">Confidence</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Source</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Last Seen</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Active</th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cyber-border/30">
                  {data?.items.map((indicator) => (
                    <tr key={indicator.id} className="table-row-hover">
                      <td className="px-4 py-3">
                        <TypeBadge type={indicator.type} />
                      </td>
                      <td className="px-4 py-3 font-mono text-sm text-cyber-text max-w-[200px]">
                        <span className="truncate block" title={indicator.value}>
                          {indicator.value}
                        </span>
                        {indicator.description && (
                          <span className="text-xs text-cyber-muted block mt-0.5 truncate">
                            {indicator.description}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <SeverityBadge severity={indicator.severity} size="sm" />
                      </td>
                      <td className="px-4 py-3">
                        <ConfidenceBar value={indicator.confidence} />
                      </td>
                      <td className="px-4 py-3 text-sm text-cyber-muted">
                        {indicator.source}
                      </td>
                      <td className="px-4 py-3 text-xs text-cyber-muted font-mono">
                        {formatTs(indicator.last_seen)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`w-2 h-2 rounded-full inline-block ${indicator.active ? 'bg-cyber-accent' : 'bg-cyber-muted'}`} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setDeletingId(indicator.id)}
                          className="p-1.5 rounded text-cyber-muted hover:text-red-400 hover:bg-red-900/20 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
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

      {addFormOpen && (
        <AddIndicatorForm
          onClose={() => setAddFormOpen(false)}
          onSaved={() => setAddFormOpen(false)}
        />
      )}

      <ConfirmDialog
        isOpen={!!deletingId}
        title="Delete Indicator"
        message={`Delete indicator "${deletingIndicator?.value}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => deletingId && deleteMutation.mutate(deletingId)}
        onCancel={() => setDeletingId(null)}
      />
    </div>
  );
};

export default ThreatIntel;
