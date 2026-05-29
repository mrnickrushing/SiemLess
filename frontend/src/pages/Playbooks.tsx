import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Zap,
  Plus,
  RefreshCw,
  Trash2,
  PlayCircle,
  ChevronDown,
  ChevronUp,
  X,
  GripVertical,
  CheckCircle,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import {
  getPlaybooks,
  createPlaybook,
  updatePlaybook,
  deletePlaybook,
  triggerPlaybook,
  getPlaybookRuns,
} from '../api/playbooks';
import type { Playbook, PlaybookStep } from '../types';

const ACTION_OPTIONS = [
  { value: 'webhook', label: 'Send Webhook' },
  { value: 'update_alert', label: 'Update Alert' },
  { value: 'create_case', label: 'Create Case' },
  { value: 'create_ticket', label: 'Create Ticket' },
  { value: 'add_to_watchlist', label: 'Add to Watchlist' },
  { value: 'send_email', label: 'Send Email' },
];

const TRIGGER_OPTIONS = [
  { value: 'alert.created', label: 'Alert Created' },
  { value: 'alert.critical', label: 'Critical Alert' },
  { value: 'alert.high', label: 'High Alert' },
  { value: 'manual', label: 'Manual Trigger' },
];

/**
 * Format an ISO timestamp into a localized short date and time string.
 *
 * @param iso - An ISO 8601 timestamp string
 * @returns A localized string containing abbreviated month, numeric day, and two-digit hour and minute derived from `iso`
 */
function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

const RunsPanel: React.FC<{ playbookId: string }> = ({ playbookId }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['playbook-runs', playbookId],
    queryFn: () => getPlaybookRuns(playbookId, { page_size: 10 }),
  });

  return (
    <div className="px-5 pb-4 bg-cyber-bg/40 border-t border-cyber-border/30">
      <p className="text-xs font-medium text-cyber-muted uppercase tracking-wider py-3">
        Recent Runs
      </p>
      {isLoading && <RefreshCw className="w-4 h-4 animate-spin text-cyber-muted" />}
      {!isLoading && !data?.items?.length && (
        <p className="text-xs text-cyber-muted italic">No runs yet.</p>
      )}
      <div className="space-y-2">
        {data?.items.map((run) => (
          <div key={run.id} className="flex items-center gap-3 text-xs">
            {run.status === 'success' ? (
              <CheckCircle className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
            ) : run.status === 'running' ? (
              <RefreshCw className="w-3.5 h-3.5 text-yellow-400 animate-spin flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
            )}
            <span className="text-cyber-muted">{formatDate(run.started_at)}</span>
            <span
              className={`px-1.5 py-0.5 rounded font-medium ${
                run.status === 'success'
                  ? 'bg-green-400/10 text-green-400'
                  : run.status === 'running'
                  ? 'bg-yellow-400/10 text-yellow-400'
                  : 'bg-red-400/10 text-red-400'
              }`}
            >
              {run.status}
            </span>
            {run.error && (
              <span className="text-red-400 truncate max-w-[200px]">{run.error}</span>
            )}
            {run.finished_at && (
              <span className="text-cyber-muted/60 ml-auto">
                <Clock className="w-3 h-3 inline mr-0.5" />
                {Math.round(
                  (new Date(run.finished_at).getTime() -
                    new Date(run.started_at).getTime()) / 1000
                )}s
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const StepBuilder: React.FC<{
  steps: PlaybookStep[];
  onChange: (steps: PlaybookStep[]) => void;
}> = ({ steps, onChange }) => {
  const addStep = () => {
    onChange([...steps, { action: 'webhook', params: {} }]);
  };

  const removeStep = (i: number) => {
    onChange(steps.filter((_, idx) => idx !== i));
  };

  const updateStep = (i: number, patch: Partial<PlaybookStep>) => {
    onChange(steps.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  };

  return (
    <div className="space-y-2">
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-2 p-3 rounded-lg bg-cyber-border/10 border border-cyber-border/30">
          <GripVertical className="w-4 h-4 text-cyber-muted/40 mt-0.5 flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <select
              className="cyber-input w-full text-sm"
              value={step.action}
              onChange={(e) => updateStep(i, { action: e.target.value })}
            >
              {ACTION_OPTIONS.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
            <textarea
              className="cyber-input w-full h-14 resize-none text-xs font-mono"
              value={JSON.stringify(step.params, null, 2)}
              onChange={(e) => {
                try {
                  updateStep(i, { params: JSON.parse(e.target.value) });
                } catch {
                  // invalid JSON — ignore until valid
                }
              }}
              placeholder='{"key": "value"}'
            />
          </div>
          <button
            onClick={() => removeStep(i)}
            className="text-cyber-muted hover:text-cyber-danger p-1 flex-shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addStep}
        className="w-full py-2 rounded-lg border border-dashed border-cyber-border/60 text-xs text-cyber-muted hover:text-cyber-text hover:border-cyber-border transition-colors"
      >
        <Plus className="w-3.5 h-3.5 inline mr-1" />
        Add Step
      </button>
    </div>
  );
};

const CreatePlaybookModal: React.FC<{
  onClose: () => void;
  onCreate: (data: {
    name: string;
    description: string;
    trigger_on: string;
    steps: PlaybookStep[];
    enabled: boolean;
  }) => void;
  loading: boolean;
  initial?: Playbook;
}> = ({ onClose, onCreate, loading, initial }) => {
  const [form, setForm] = useState({
    name: initial?.name ?? '',
    description: initial?.description ?? '',
    trigger_on: initial?.trigger_on ?? 'alert.created',
    steps: initial?.steps ?? ([] as PlaybookStep[]),
    enabled: initial?.enabled ?? true,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm overflow-y-auto p-4">
      <div className="cyber-card w-full max-w-lg my-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-cyber-text">
            {initial ? 'Edit Playbook' : 'New Playbook'}
          </h2>
          <button onClick={onClose} className="text-cyber-muted hover:text-cyber-text">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1">Name *</label>
            <input
              className="cyber-input w-full"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Playbook name"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1">Description</label>
            <input
              className="cyber-input w-full"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Optional description"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1">Trigger On</label>
            <select
              className="cyber-input w-full"
              value={form.trigger_on}
              onChange={(e) => setForm((f) => ({ ...f, trigger_on: e.target.value }))}
            >
              {TRIGGER_OPTIONS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-2">Steps</label>
            <StepBuilder
              steps={form.steps}
              onChange={(steps) => setForm((f) => ({ ...f, steps }))}
            />
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="cyber-btn-secondary flex-1">Cancel</button>
          <button
            onClick={() => onCreate(form)}
            disabled={!form.name.trim() || loading}
            className="cyber-btn flex-1"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin mx-auto" /> : 'Save Playbook'}
          </button>
        </div>
      </div>
    </div>
  );
};

const Playbooks: React.FC = () => {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Playbook | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['playbooks'],
    queryFn: () => getPlaybooks({ page_size: 50 }),
  });

  const createMutation = useMutation({
    mutationFn: createPlaybook,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbooks'] });
      setShowCreate(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updatePlaybook>[1] }) =>
      updatePlaybook(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playbooks'] });
      setEditing(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlaybook,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['playbooks'] }),
  });

  const triggerMutation = useMutation({
    mutationFn: (id: string) => triggerPlaybook(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['playbook-runs', id] });
      qc.invalidateQueries({ queryKey: ['playbooks'] });
    },
  });

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Zap className="w-6 h-6 text-cyber-accent" />
          <div>
            <h1 className="text-2xl font-bold text-cyber-text">Playbooks</h1>
            <p className="text-sm text-cyber-muted mt-0.5">
              SOAR automation — define triggers, conditions, and actions
            </p>
          </div>
        </div>
        <button onClick={() => setShowCreate(true)} className="cyber-btn flex items-center gap-2">
          <Plus className="w-4 h-4" />
          New Playbook
        </button>
      </div>

      {/* List */}
      <div className="cyber-card overflow-hidden">
        {isLoading && (
          <div className="flex items-center justify-center py-12 text-cyber-muted">
            <RefreshCw className="w-5 h-5 animate-spin" />
          </div>
        )}
        {!isLoading && !data?.items?.length && (
          <div className="text-center py-12">
            <Zap className="w-10 h-10 text-cyber-muted/30 mx-auto mb-3" />
            <p className="text-sm text-cyber-muted">No playbooks configured</p>
          </div>
        )}
        <div className="divide-y divide-cyber-border/30">
          {data?.items.map((pb) => {
            const isExpanded = expandedId === pb.id;
            return (
              <div key={pb.id}>
                <div className="px-5 py-4">
                  <div className="flex items-center gap-4">
                    {/* Enable toggle */}
                    <button
                      onClick={() =>
                        updateMutation.mutate({ id: pb.id, data: { enabled: !pb.enabled } })
                      }
                      className={`relative w-8 h-4 rounded-full transition-colors flex-shrink-0 ${
                        pb.enabled ? 'bg-cyber-accent' : 'bg-cyber-border'
                      }`}
                    >
                      <div
                        className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow transition-transform ${
                          pb.enabled ? 'translate-x-4' : 'translate-x-0.5'
                        }`}
                      />
                    </button>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-cyber-text">{pb.name}</p>
                        <span className="text-xs bg-cyber-border/30 text-cyber-muted px-1.5 py-0.5 rounded">
                          {TRIGGER_OPTIONS.find((t) => t.value === pb.trigger_on)?.label ?? pb.trigger_on}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-xs text-cyber-muted">
                        {pb.description && <span>{pb.description}</span>}
                        <span>{pb.steps.length} step{pb.steps.length !== 1 ? 's' : ''}</span>
                        <span>{pb.run_count} run{pb.run_count !== 1 ? 's' : ''}</span>
                        {pb.last_run_at && <span>Last: {formatDate(pb.last_run_at)}</span>}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => triggerMutation.mutate(pb.id)}
                        disabled={triggerMutation.isPending}
                        className="cyber-btn-secondary text-xs px-2.5 py-1.5 flex items-center gap-1"
                        title="Trigger manually"
                      >
                        <PlayCircle className="w-3.5 h-3.5" />
                        Run
                      </button>
                      <button
                        onClick={() => setEditing(pb as Playbook)}
                        className="cyber-btn-secondary text-xs px-2.5 py-1.5"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() =>
                          confirm(`Delete playbook "${pb.name}"?`) && deleteMutation.mutate(pb.id)
                        }
                        className="text-cyber-muted hover:text-cyber-danger p-1.5 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : pb.id)}
                        className="text-cyber-muted hover:text-cyber-text p-1.5 rounded"
                      >
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>

                {isExpanded && <RunsPanel playbookId={pb.id} />}
              </div>
            );
          })}
        </div>
      </div>

      {showCreate && (
        <CreatePlaybookModal
          onClose={() => setShowCreate(false)}
          onCreate={(data) => createMutation.mutate(data)}
          loading={createMutation.isPending}
        />
      )}

      {editing && (
        <CreatePlaybookModal
          onClose={() => setEditing(null)}
          onCreate={(data) => updateMutation.mutate({ id: editing.id, data })}
          loading={updateMutation.isPending}
          initial={editing}
        />
      )}
    </div>
  );
};

export default Playbooks;
