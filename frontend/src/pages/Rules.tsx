import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import {
  Plus,
  Edit2,
  Trash2,
  ToggleLeft,
  ToggleRight,
  BookOpen,
  AlertTriangle,
  RefreshCw,
  X,
  Shield,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { getRules, createRule, updateRule, deleteRule, toggleRule } from '../api/rules';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import { TableSkeleton } from '../components/shared/LoadingSpinner';
import EmptyState from '../components/shared/EmptyState';
import ConfirmDialog from '../components/shared/ConfirmDialog';
import Pagination from '../components/shared/Pagination';
import type { CorrelationRule, RuleFormData, Severity } from '../types';

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info'];

const DEFAULT_FORM: RuleFormData = {
  name: '',
  description: '',
  severity: 'medium',
  category: '',
  condition: { field: '', operator: 'equals', value: '' },
  threshold: 1,
  time_window: 300,
  enabled: true,
  mitre_tactic: '',
  mitre_technique: '',
  alert_title_template: '',
  alert_description_template: '',
};

interface RuleFormProps {
  initial?: CorrelationRule | null;
  onClose: () => void;
  onSaved: () => void;
}

const RuleForm: React.FC<RuleFormProps> = ({ initial, onClose, onSaved }) => {
  const [form, setForm] = useState<RuleFormData>(
    initial
      ? {
          name: initial.name,
          description: initial.description || '',
          severity: initial.severity,
          category: initial.category,
          condition: initial.condition,
          threshold: initial.threshold,
          time_window: initial.time_window,
          enabled: initial.enabled,
          mitre_tactic: initial.mitre_tactic || '',
          mitre_technique: initial.mitre_technique || '',
          alert_title_template: initial.alert_title_template || '',
          alert_description_template: initial.alert_description_template || '',
        }
      : DEFAULT_FORM
  );

  const [conditionJson, setConditionJson] = useState(
    JSON.stringify(initial?.condition || DEFAULT_FORM.condition, null, 2)
  );
  const [conditionError, setConditionError] = useState('');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: RuleFormData) =>
      initial ? updateRule(initial.id, data) : createRule(data),
    onSuccess: () => {
      toast.success(initial ? 'Rule updated' : 'Rule created');
      queryClient.invalidateQueries({ queryKey: ['rules'] });
      onSaved();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const setField = <K extends keyof RuleFormData>(key: K, value: RuleFormData[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const condition = JSON.parse(conditionJson);
      mutation.mutate({ ...form, condition });
    } catch {
      setConditionError('Invalid JSON');
      return;
    }
  };

  const handleConditionChange = (val: string) => {
    setConditionJson(val);
    try {
      JSON.parse(val);
      setConditionError('');
    } catch {
      setConditionError('Invalid JSON');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-cyber-card border border-cyber-border rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col mx-4 animate-fade-in">
        <div className="flex items-center justify-between px-6 py-4 border-b border-cyber-border flex-shrink-0">
          <h2 className="text-base font-semibold text-cyber-text">
            {initial ? 'Edit Rule' : 'Create Rule'}
          </h2>
          <button onClick={onClose} className="p-1.5 rounded text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="text-xs text-cyber-muted block mb-1">Name *</label>
              <input
                required
                type="text"
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                placeholder="Rule name"
                className="cyber-input w-full"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-cyber-muted block mb-1">Description</label>
              <textarea
                value={form.description}
                onChange={(e) => setField('description', e.target.value)}
                rows={2}
                placeholder="What does this rule detect?"
                className="cyber-input w-full resize-none"
              />
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Severity *</label>
              <select
                value={form.severity}
                onChange={(e) => setField('severity', e.target.value as Severity)}
                className="cyber-select w-full"
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Category *</label>
              <input
                required
                type="text"
                value={form.category}
                onChange={(e) => setField('category', e.target.value)}
                placeholder="e.g. authentication, network"
                className="cyber-input w-full"
              />
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Threshold</label>
              <input
                type="number"
                min={1}
                value={form.threshold}
                onChange={(e) => setField('threshold', parseInt(e.target.value) || 1)}
                className="cyber-input w-full"
              />
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Time Window (seconds)</label>
              <input
                type="number"
                min={1}
                value={form.time_window}
                onChange={(e) => setField('time_window', parseInt(e.target.value) || 300)}
                className="cyber-input w-full"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-cyber-muted block mb-1">
              Condition (JSON) {conditionError && <span className="text-red-400 ml-2">{conditionError}</span>}
            </label>
            <textarea
              value={conditionJson}
              onChange={(e) => handleConditionChange(e.target.value)}
              rows={6}
              className={`cyber-input w-full font-mono text-xs resize-none ${
                conditionError ? 'border-red-700/50' : ''
              }`}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-cyber-muted block mb-1">MITRE Tactic</label>
              <input
                type="text"
                value={form.mitre_tactic}
                onChange={(e) => setField('mitre_tactic', e.target.value)}
                placeholder="e.g. TA0001"
                className="cyber-input w-full"
              />
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">MITRE Technique</label>
              <input
                type="text"
                value={form.mitre_technique}
                onChange={(e) => setField('mitre_technique', e.target.value)}
                placeholder="e.g. T1110"
                className="cyber-input w-full"
              />
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Alert Title Template</label>
              <input
                type="text"
                value={form.alert_title_template}
                onChange={(e) => setField('alert_title_template', e.target.value)}
                placeholder="{count} failed logins from {source_ip}"
                className="cyber-input w-full font-mono text-xs"
              />
            </div>
            <div>
              <label className="text-xs text-cyber-muted block mb-1">Alert Description Template</label>
              <input
                type="text"
                value={form.alert_description_template}
                onChange={(e) => setField('alert_description_template', e.target.value)}
                placeholder="Detected {count} events..."
                className="cyber-input w-full font-mono text-xs"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-sm text-cyber-text font-medium">Enabled</label>
            <button
              type="button"
              onClick={() => setField('enabled', !form.enabled)}
              className={`transition-colors ${form.enabled ? 'text-cyber-accent' : 'text-cyber-muted'}`}
            >
              {form.enabled ? (
                <ToggleRight className="w-7 h-7" />
              ) : (
                <ToggleLeft className="w-7 h-7" />
              )}
            </button>
          </div>

          <div className="flex justify-end gap-3 pt-2 border-t border-cyber-border">
            <button type="button" onClick={onClose} className="cyber-btn-secondary">
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending || !!conditionError}
              className="cyber-btn-primary"
            >
              {mutation.isPending ? 'Saving...' : initial ? 'Save Changes' : 'Create Rule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const Rules: React.FC = () => {
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CorrelationRule | null>(null);
  const [deletingRuleId, setDeletingRuleId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['rules', page],
    queryFn: () => getRules(page, 50),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => toggleRule(id, enabled),
    onSuccess: () => {
      toast.success('Rule updated');
      queryClient.invalidateQueries({ queryKey: ['rules'] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteRule(id),
    onSuccess: () => {
      toast.success('Rule deleted');
      queryClient.invalidateQueries({ queryKey: ['rules'] });
      setDeletingRuleId(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const formatTs = (ts: string | null) => {
    if (!ts) return '—';
    try {
      return format(parseISO(ts), 'MMM dd, HH:mm');
    } catch {
      return ts;
    }
  };

  const ruleToDelete = data?.items.find((r) => r.id === deletingRuleId);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-cyber-text">Correlation Rules</h1>
          <p className="text-sm text-cyber-muted mt-1">
            {data ? `${data.total} rules` : 'Manage detection rules'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => refetch()} disabled={isFetching} className="cyber-btn-secondary flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => { setEditingRule(null); setFormOpen(true); }}
            className="cyber-btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Rule
          </button>
        </div>
      </div>

      <div className="cyber-card overflow-hidden">
        {isLoading ? (
          <TableSkeleton rows={8} cols={7} />
        ) : isError ? (
          <div className="p-8 text-center">
            <AlertTriangle className="w-8 h-8 text-cyber-danger mx-auto mb-2" />
            <p className="text-cyber-danger">{(error as Error).message}</p>
          </div>
        ) : data?.items.length === 0 ? (
          <EmptyState
            title="No rules configured"
            description="Create your first correlation rule to start detecting security threats."
            icon={<BookOpen className="w-8 h-8 text-cyber-muted" />}
            action={
              <button
                onClick={() => { setEditingRule(null); setFormOpen(true); }}
                className="cyber-btn-primary"
              >
                <Plus className="w-4 h-4 inline mr-1.5" />
                Create Rule
              </button>
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px]">
                <thead>
                  <tr className="border-b border-cyber-border bg-cyber-bg/30">
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Name</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Severity</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Category</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Enabled</th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Triggers</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Last Triggered</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">MITRE</th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cyber-border/30">
                  {data?.items.map((rule) => (
                    <tr key={rule.id} className="table-row-hover">
                      <td className="px-4 py-3">
                        <div className="text-sm font-medium text-cyber-text">{rule.name}</div>
                        {rule.description && (
                          <div className="text-xs text-cyber-muted truncate max-w-xs">{rule.description}</div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <SeverityBadge severity={rule.severity} size="sm" />
                      </td>
                      <td className="px-4 py-3 text-sm text-cyber-muted">{rule.category}</td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => toggleMutation.mutate({ id: rule.id, enabled: !rule.enabled })}
                          disabled={toggleMutation.isPending}
                          className={`transition-colors ${rule.enabled ? 'text-cyber-accent' : 'text-cyber-muted hover:text-cyber-text'}`}
                        >
                          {rule.enabled ? (
                            <ToggleRight className="w-6 h-6" />
                          ) : (
                            <ToggleLeft className="w-6 h-6" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-sm text-cyber-text">
                        {rule.trigger_count.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-xs text-cyber-muted font-mono">
                        {formatTs(rule.last_triggered)}
                      </td>
                      <td className="px-4 py-3">
                        {(rule.mitre_tactic || rule.mitre_technique) && (
                          <div className="flex items-center gap-1">
                            <Shield className="w-3 h-3 text-purple-400" />
                            <span className="text-xs text-purple-400 font-mono">
                              {rule.mitre_technique || rule.mitre_tactic}
                            </span>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => { setEditingRule(rule); setFormOpen(true); }}
                            className="p-1.5 rounded text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 transition-colors"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setDeletingRuleId(rule.id)}
                            className="p-1.5 rounded text-cyber-muted hover:text-red-400 hover:bg-red-900/20 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
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

      {/* Rule Form Modal */}
      {formOpen && (
        <RuleForm
          initial={editingRule}
          onClose={() => { setFormOpen(false); setEditingRule(null); }}
          onSaved={() => { setFormOpen(false); setEditingRule(null); }}
        />
      )}

      {/* Delete Confirm */}
      <ConfirmDialog
        isOpen={!!deletingRuleId}
        title="Delete Rule"
        message={`Are you sure you want to delete "${ruleToDelete?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => deletingRuleId && deleteMutation.mutate(deletingRuleId)}
        onCancel={() => setDeletingRuleId(null)}
      />
    </div>
  );
};

export default Rules;
