import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Briefcase,
  Plus,
  ChevronRight,
  Clock,
  MessageSquare,
  Paperclip,
  Link2,
  AlertTriangle,
  X,
  Send,
  Tag,
  RefreshCw,
} from 'lucide-react';
import {
  getCases,
  getCase,
  createCase,
  updateCase,
  getCaseTimeline,
  getCaseComments,
  addCaseComment,
  getCaseArtifacts,
  addCaseArtifact,
  getCaseLinkedAlerts,
} from '../api/cases';
import type { Case, CaseCreate, Severity, CaseStatus } from '../types';

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'text-red-400 bg-red-400/10 border-red-400/30',
  high: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  medium: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  low: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  info: 'text-gray-400 bg-gray-400/10 border-gray-400/30',
};

const STATUS_COLORS: Record<CaseStatus, string> = {
  open: 'text-cyber-accent bg-cyber-accent/10 border-cyber-accent/30',
  investigating: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  resolved: 'text-green-400 bg-green-400/10 border-green-400/30',
  closed: 'text-gray-400 bg-gray-400/10 border-gray-400/30',
};

/**
 * Format an ISO 8601 timestamp into a localized short date and time string.
 *
 * @param iso - An ISO 8601 timestamp string
 * @returns A localized string with short month, numeric day, and two-digit hour and minute
 */
function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const CreateCaseModal: React.FC<{
  onClose: () => void;
  onCreate: (data: CaseCreate) => void;
  loading: boolean;
}> = ({ onClose, onCreate, loading }) => {
  const [form, setForm] = useState<CaseCreate>({
    title: '',
    description: '',
    severity: 'medium',
    assigned_to: '',
    tags: [],
  });
  const [tagInput, setTagInput] = useState('');

  const handleAddTag = () => {
    if (tagInput.trim() && !form.tags?.includes(tagInput.trim())) {
      setForm((f) => ({ ...f, tags: [...(f.tags ?? []), tagInput.trim()] }));
      setTagInput('');
    }
  };

  const handleRemoveTag = (tag: string) => {
    setForm((f) => ({ ...f, tags: f.tags?.filter((t) => t !== tag) }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="cyber-card w-full max-w-lg mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-cyber-text">New Case</h2>
          <button onClick={onClose} className="text-cyber-muted hover:text-cyber-text">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1">Title *</label>
            <input
              className="cyber-input w-full"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Brief case summary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1">Description</label>
            <textarea
              className="cyber-input w-full h-20 resize-none"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Detailed description..."
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-cyber-muted mb-1">Severity</label>
              <select
                className="cyber-input w-full"
                value={form.severity}
                onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value as Severity }))}
              >
                {(['critical', 'high', 'medium', 'low', 'info'] as Severity[]).map((s) => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-cyber-muted mb-1">Assign To</label>
              <input
                className="cyber-input w-full"
                value={form.assigned_to}
                onChange={(e) => setForm((f) => ({ ...f, assigned_to: e.target.value }))}
                placeholder="username"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1">Tags</label>
            <div className="flex gap-2">
              <input
                className="cyber-input flex-1"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                placeholder="Add tag..."
              />
              <button type="button" onClick={handleAddTag} className="cyber-btn-secondary px-3">
                <Tag className="w-4 h-4" />
              </button>
            </div>
            {(form.tags ?? []).length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {(form.tags ?? []).map((tag) => (
                  <span key={tag} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-cyber-border/40 text-cyber-muted">
                    {tag}
                    <button onClick={() => handleRemoveTag(tag)} className="hover:text-cyber-danger">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="cyber-btn-secondary flex-1">Cancel</button>
          <button
            onClick={() => onCreate(form)}
            disabled={!form.title.trim() || loading}
            className="cyber-btn flex-1"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin mx-auto" /> : 'Create Case'}
          </button>
        </div>
      </div>
    </div>
  );
};

type DetailTab = 'timeline' | 'comments' | 'artifacts' | 'alerts';

const CaseDetail: React.FC<{ caseId: string }> = ({ caseId }) => {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<DetailTab>('timeline');
  const [commentText, setCommentText] = useState('');
  const [artifactForm, setArtifactForm] = useState({ type: 'ip', value: '', description: '' });
  const [showArtifactForm, setShowArtifactForm] = useState(false);

  const { data: c, isLoading } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => getCase(caseId),
  });

  const { data: timeline } = useQuery({
    queryKey: ['case-timeline', caseId],
    queryFn: () => getCaseTimeline(caseId),
    enabled: activeTab === 'timeline',
  });

  const { data: comments } = useQuery({
    queryKey: ['case-comments', caseId],
    queryFn: () => getCaseComments(caseId),
    enabled: activeTab === 'comments',
  });

  const { data: artifacts } = useQuery({
    queryKey: ['case-artifacts', caseId],
    queryFn: () => getCaseArtifacts(caseId),
    enabled: activeTab === 'artifacts',
  });

  const { data: linkedAlerts } = useQuery({
    queryKey: ['case-linked-alerts', caseId],
    queryFn: () => getCaseLinkedAlerts(caseId),
    enabled: activeTab === 'alerts',
  });

  const statusMutation = useMutation({
    mutationFn: (status: string) => updateCase(caseId, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['case', caseId] }),
  });

  const commentMutation = useMutation({
    mutationFn: (body: string) => addCaseComment(caseId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['case-comments', caseId] });
      qc.invalidateQueries({ queryKey: ['case-timeline', caseId] });
      setCommentText('');
    },
  });

  const artifactMutation = useMutation({
    mutationFn: (data: { artifact_type: string; value: string; description?: string }) =>
      addCaseArtifact(caseId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['case-artifacts', caseId] });
      qc.invalidateQueries({ queryKey: ['case-timeline', caseId] });
      setShowArtifactForm(false);
      setArtifactForm({ type: 'ip', value: '', description: '' });
    },
  });

  if (isLoading || !c) {
    return (
      <div className="flex-1 flex items-center justify-center text-cyber-muted">
        <RefreshCw className="w-5 h-5 animate-spin" />
      </div>
    );
  }

  const tabs: { id: DetailTab; label: string; icon: React.ReactNode }[] = [
    { id: 'timeline', label: 'Timeline', icon: <Clock className="w-4 h-4" /> },
    { id: 'comments', label: 'Comments', icon: <MessageSquare className="w-4 h-4" /> },
    { id: 'artifacts', label: 'Artifacts', icon: <Paperclip className="w-4 h-4" /> },
    { id: 'alerts', label: 'Linked Alerts', icon: <Link2 className="w-4 h-4" /> },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-cyber-border flex-shrink-0">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold text-cyber-text truncate">{c.title}</h2>
            <div className="flex flex-wrap items-center gap-2 mt-1.5">
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${SEVERITY_COLORS[c.severity]}`}>
                {c.severity}
              </span>
              <select
                className="text-xs rounded-full border px-2 py-0.5 font-medium bg-transparent cursor-pointer focus:outline-none"
                value={c.status}
                onChange={(e) => statusMutation.mutate(e.target.value)}
                style={{ borderColor: 'transparent' }}
              >
                {(['open', 'investigating', 'resolved', 'closed'] as CaseStatus[]).map((s) => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
              {c.assigned_to && (
                <span className="text-xs text-cyber-muted">@{c.assigned_to}</span>
              )}
            </div>
          </div>
        </div>
        {c.description && (
          <p className="text-sm text-cyber-muted mt-2 leading-relaxed">{c.description}</p>
        )}
        {(c.tags ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {(c.tags ?? []).map((tag) => (
              <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-cyber-border/40 text-cyber-muted">{tag}</span>
            ))}
          </div>
        )}
        <p className="text-xs text-cyber-muted/60 mt-2">
          Created {formatDate(c.created_at)} · Updated {formatDate(c.updated_at)}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-cyber-border flex-shrink-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-cyber-accent text-cyber-accent'
                : 'border-transparent text-cyber-muted hover:text-cyber-text'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'timeline' && (
          <div className="space-y-3">
            {!timeline?.length && (
              <p className="text-xs text-cyber-muted text-center py-8">No timeline events yet.</p>
            )}
            {timeline?.map((item) => (
              <div key={item.id} className="flex gap-3 items-start">
                <div className="w-2 h-2 rounded-full bg-cyber-accent mt-1.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-cyber-muted">{formatDate(item.ts)}</p>
                  <p className="text-sm text-cyber-text mt-0.5">{item.summary}</p>
                </div>
                <span className="text-xs text-cyber-muted/60 bg-cyber-border/20 px-1.5 py-0.5 rounded flex-shrink-0">
                  {item.kind}
                </span>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'comments' && (
          <div className="flex flex-col h-full gap-3">
            <div className="flex-1 space-y-3">
              {!comments?.length && (
                <p className="text-xs text-cyber-muted text-center py-8">No comments yet.</p>
              )}
              {comments?.map((comment) => (
                <div key={comment.id} className="cyber-card p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-medium text-cyber-accent">@{comment.author}</span>
                    <span className="text-xs text-cyber-muted">{formatDate(comment.created_at)}</span>
                  </div>
                  <p className="text-sm text-cyber-text leading-relaxed">{comment.body}</p>
                </div>
              ))}
            </div>
            <div className="flex gap-2 pt-2 border-t border-cyber-border">
              <textarea
                className="cyber-input flex-1 h-16 resize-none text-sm"
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Add a comment..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.ctrlKey && commentText.trim()) {
                    commentMutation.mutate(commentText.trim());
                  }
                }}
              />
              <button
                onClick={() => commentText.trim() && commentMutation.mutate(commentText.trim())}
                disabled={!commentText.trim() || commentMutation.isPending}
                className="cyber-btn px-3 self-end"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {activeTab === 'artifacts' && (
          <div className="space-y-3">
            <button
              onClick={() => setShowArtifactForm(!showArtifactForm)}
              className="cyber-btn-secondary text-xs w-full"
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              Add Artifact
            </button>

            {showArtifactForm && (
              <div className="cyber-card p-3 space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-cyber-muted mb-1">Type</label>
                    <select
                      className="cyber-input w-full text-sm"
                      value={artifactForm.type}
                      onChange={(e) => setArtifactForm((f) => ({ ...f, type: e.target.value }))}
                    >
                      {['ip', 'domain', 'hash', 'url', 'email', 'file', 'user', 'host'].map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-cyber-muted mb-1">Value</label>
                    <input
                      className="cyber-input w-full text-sm"
                      value={artifactForm.value}
                      onChange={(e) => setArtifactForm((f) => ({ ...f, value: e.target.value }))}
                      placeholder="Artifact value"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-cyber-muted mb-1">Notes</label>
                  <input
                    className="cyber-input w-full text-sm"
                    value={artifactForm.description}
                    onChange={(e) => setArtifactForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="Optional description"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowArtifactForm(false)}
                    className="cyber-btn-secondary flex-1 text-xs"
                  >Cancel</button>
                  <button
                    onClick={() =>
                      artifactForm.value &&
                      artifactMutation.mutate({
                        artifact_type: artifactForm.type,
                        value: artifactForm.value,
                        description: artifactForm.description || undefined,
                      })
                    }
                    disabled={!artifactForm.value || artifactMutation.isPending}
                    className="cyber-btn flex-1 text-xs"
                  >Save</button>
                </div>
              </div>
            )}

            {!artifacts?.length && !showArtifactForm && (
              <p className="text-xs text-cyber-muted text-center py-8">No artifacts yet.</p>
            )}
            {artifacts?.map((a) => (
              <div key={a.id} className="cyber-card p-3 flex items-start gap-3">
                <span className="text-xs px-1.5 py-0.5 rounded bg-cyber-border/40 text-cyber-muted font-mono flex-shrink-0">
                  {a.artifact_type}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-mono text-cyber-text truncate">{a.value}</p>
                  {a.description && (
                    <p className="text-xs text-cyber-muted mt-0.5">{a.description}</p>
                  )}
                </div>
                <span className="text-xs text-cyber-muted/60 flex-shrink-0">{formatDate(a.created_at)}</span>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'alerts' && (
          <div className="space-y-2">
            {!linkedAlerts?.length && (
              <p className="text-xs text-cyber-muted text-center py-8">No linked alerts.</p>
            )}
            {linkedAlerts?.map((alert) => (
              <div key={alert.id} className="cyber-card p-3 flex items-center gap-3">
                <AlertTriangle className={`w-4 h-4 flex-shrink-0 ${
                  alert.severity === 'critical' ? 'text-red-400' :
                  alert.severity === 'high' ? 'text-orange-400' : 'text-yellow-400'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-cyber-text truncate">{alert.title}</p>
                  <p className="text-xs text-cyber-muted">{formatDate(alert.created_at)}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLORS[alert.status as CaseStatus] || ''}`}>
                  {alert.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const Cases: React.FC = () => {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['cases', page, statusFilter, severityFilter],
    queryFn: () =>
      getCases({
        page,
        page_size: 25,
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
      }),
  });

  const createMutation = useMutation({
    mutationFn: createCase,
    onSuccess: (newCase) => {
      qc.invalidateQueries({ queryKey: ['cases'] });
      setShowCreate(false);
      setSelectedId(newCase.id);
    },
  });

  const handleCreate = useCallback(
    (formData: CaseCreate) => {
      createMutation.mutate(formData);
    },
    [createMutation]
  );

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left Panel */}
      <div className="w-80 flex-shrink-0 border-r border-cyber-border flex flex-col">
        {/* Header */}
        <div className="px-4 py-3 border-b border-cyber-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="w-4 h-4 text-cyber-accent" />
            <h1 className="text-sm font-semibold text-cyber-text">Cases</h1>
            {data && (
              <span className="text-xs text-cyber-muted bg-cyber-border/30 px-1.5 py-0.5 rounded-full">
                {data.total}
              </span>
            )}
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="cyber-btn text-xs px-2.5 py-1.5"
          >
            <Plus className="w-3.5 h-3.5 mr-1" />
            New
          </button>
        </div>

        {/* Filters */}
        <div className="px-3 py-2 border-b border-cyber-border flex gap-2">
          <select
            className="cyber-input flex-1 text-xs"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
          <select
            className="cyber-input flex-1 text-xs"
            value={severityFilter}
            onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-12 text-cyber-muted">
              <RefreshCw className="w-5 h-5 animate-spin" />
            </div>
          )}
          {!isLoading && !data?.items?.length && (
            <div className="text-center py-12">
              <Briefcase className="w-8 h-8 text-cyber-muted/30 mx-auto mb-2" />
              <p className="text-sm text-cyber-muted">No cases found</p>
            </div>
          )}
          {data?.items.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedId(c.id)}
              className={`w-full text-left px-4 py-3 border-b border-cyber-border/40 hover:bg-cyber-border/10 transition-colors ${
                selectedId === c.id ? 'bg-cyber-accent/5 border-l-2 border-l-cyber-accent' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-cyber-text line-clamp-2 flex-1">{c.title}</p>
                <ChevronRight className="w-4 h-4 text-cyber-muted flex-shrink-0 mt-0.5" />
              </div>
              <div className="flex items-center gap-2 mt-1.5">
                <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${SEVERITY_COLORS[c.severity]}`}>
                  {c.severity}
                </span>
                <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${STATUS_COLORS[c.status]}`}>
                  {c.status}
                </span>
              </div>
              <div className="flex items-center gap-3 mt-1.5 text-xs text-cyber-muted">
                <span>{formatDate(c.created_at)}</span>
                {c.assigned_to && <span>@{c.assigned_to}</span>}
              </div>
            </button>
          ))}
        </div>

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-2 border-t border-cyber-border">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="text-xs text-cyber-muted disabled:opacity-40 hover:text-cyber-text"
            >Prev</button>
            <span className="text-xs text-cyber-muted">{page} / {data.pages}</span>
            <button
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={page === data.pages}
              className="text-xs text-cyber-muted disabled:opacity-40 hover:text-cyber-text"
            >Next</button>
          </div>
        )}
      </div>

      {/* Right Panel */}
      <div className="flex-1 overflow-hidden">
        {selectedId ? (
          <CaseDetail caseId={selectedId} />
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-cyber-muted">
            <Briefcase className="w-12 h-12 opacity-20 mb-3" />
            <p className="text-sm">Select a case to view details</p>
            <p className="text-xs mt-1 opacity-60">or create a new one</p>
          </div>
        )}
      </div>

      {showCreate && (
        <CreateCaseModal
          onClose={() => setShowCreate(false)}
          onCreate={handleCreate}
          loading={createMutation.isPending}
        />
      )}
    </div>
  );
};

export default Cases;
