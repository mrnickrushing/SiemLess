import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import { List, Plus, Trash2, Search, Tag, Globe, User, Hash, Server, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { getWatchlist, createWatchlistEntry, deleteWatchlistEntry } from '../api/watchlist';
import { TableSkeleton } from '../components/shared/LoadingSpinner';
import EmptyState from '../components/shared/EmptyState';
import ConfirmDialog from '../components/shared/ConfirmDialog';
import type { WatchlistEntry } from '../types';

type EntryType = 'ip' | 'user' | 'hash' | 'domain';

const TYPE_STYLES: Record<EntryType, string> = {
  ip:     'bg-blue-500/20 text-blue-400 border-blue-500/30',
  user:   'bg-purple-500/20 text-purple-400 border-purple-500/30',
  hash:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  domain: 'bg-green-500/20 text-green-400 border-green-500/30',
};

const TYPE_ICONS: Record<EntryType, React.ReactNode> = {
  ip:     <Globe className="w-3 h-3" />,
  user:   <User className="w-3 h-3" />,
  hash:   <Hash className="w-3 h-3" />,
  domain: <Server className="w-3 h-3" />,
};

const TYPE_PLACEHOLDERS: Record<EntryType, string> = {
  ip:     '192.168.1.1',
  user:   'jsmith',
  hash:   'sha256:abc123…',
  domain: 'evil.example.com',
};

interface FormData {
  entry_type: EntryType;
  value: string;
  label: string;
  tags: string;
  notes: string;
}

const DEFAULT_FORM: FormData = { entry_type: 'ip', value: '', label: '', tags: '', notes: '' };

const AddForm: React.FC<{ onClose: () => void; onSaved: () => void }> = ({ onClose, onSaved }) => {
  const [form, setForm] = useState<FormData>(DEFAULT_FORM);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      createWatchlistEntry({
        entry_type: form.entry_type,
        value: form.value.trim(),
        label: form.label.trim() || undefined,
        tags: form.tags.trim()
          ? form.tags.split(',').map((t) => t.trim()).filter(Boolean)
          : undefined,
        notes: form.notes.trim() || undefined,
      }),
    onSuccess: () => {
      toast.success('Entry added to watchlist');
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      onSaved();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.value.trim()) return;
    mutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="cyber-card w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-cyber-border">
          <h2 className="text-sm font-semibold text-cyber-text">Add Watchlist Entry</h2>
          <button onClick={onClose} className="text-cyber-muted hover:text-cyber-text">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-cyber-muted mb-1.5">
                Type <span className="text-cyber-danger">*</span>
              </label>
              <select
                className="cyber-input w-full text-sm"
                value={form.entry_type}
                onChange={(e) => setForm((f) => ({ ...f, entry_type: e.target.value as EntryType }))}
              >
                <option value="ip">IP Address</option>
                <option value="user">User</option>
                <option value="hash">File Hash</option>
                <option value="domain">Domain</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-cyber-muted mb-1.5">
                Value <span className="text-cyber-danger">*</span>
              </label>
              <input
                className="cyber-input w-full text-sm font-mono"
                value={form.value}
                onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
                placeholder={TYPE_PLACEHOLDERS[form.entry_type]}
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1.5">Label</label>
            <input
              className="cyber-input w-full text-sm"
              value={form.label}
              onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
              placeholder="e.g. Known attacker, Internal scanner"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1.5">
              Tags{' '}
              <span className="text-xs text-cyber-muted/60 font-normal">(comma-separated)</span>
            </label>
            <input
              className="cyber-input w-full text-sm"
              value={form.tags}
              onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value }))}
              placeholder="e.g. threat, investigation, vpn"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1.5">Notes</label>
            <textarea
              className="cyber-input w-full text-sm resize-none"
              rows={2}
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="Optional notes about this entry"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="cyber-btn-secondary text-sm px-4 py-2">
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending || !form.value.trim()}
              className="cyber-btn-primary text-sm px-4 py-2"
            >
              {mutation.isPending ? 'Adding…' : 'Add Entry'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const TypeBadge: React.FC<{ type: EntryType }> = ({ type }) => (
  <span
    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold uppercase tracking-wide ${TYPE_STYLES[type]}`}
  >
    {TYPE_ICONS[type]}
    {type}
  </span>
);

const Watchlist: React.FC = () => {
  const [showForm, setShowForm] = useState(false);
  const [deleting, setDeleting] = useState<WatchlistEntry | null>(null);
  const [typeFilter, setTypeFilter] = useState('');
  const [search, setSearch] = useState('');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['watchlist', typeFilter],
    queryFn: () => getWatchlist(typeFilter ? { entry_type: typeFilter } : undefined),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteWatchlistEntry(id),
    onSuccess: () => {
      toast.success('Entry removed');
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      setDeleting(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const items = (data?.items ?? []).filter((item) =>
    search.trim()
      ? item.value.toLowerCase().includes(search.toLowerCase()) ||
        (item.label ?? '').toLowerCase().includes(search.toLowerCase())
      : true
  );

  const formatTs = (ts: string) => {
    try {
      return format(parseISO(ts), 'MMM d, yyyy');
    } catch {
      return ts;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-cyber-text flex items-center gap-2">
            <List className="w-6 h-6 text-cyber-accent" />
            Watchlist
          </h1>
          <p className="text-sm text-cyber-muted mt-1">
            Track IPs, users, hashes, and domains — matching events are auto-tagged on ingest
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="cyber-btn-primary flex items-center gap-2 text-sm px-4 py-2"
        >
          <Plus className="w-4 h-4" />
          Add Entry
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-cyber-muted" />
          <input
            className="cyber-input w-full pl-9 text-sm"
            placeholder="Filter by value or label…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-1">
          {(['', 'ip', 'user', 'hash', 'domain'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                typeFilter === t
                  ? 'bg-cyber-accent text-cyber-bg'
                  : 'bg-cyber-border/40 text-cyber-muted hover:text-cyber-text'
              }`}
            >
              {t === '' ? 'All' : t.toUpperCase()}
            </button>
          ))}
        </div>
        {data && (
          <span className="text-xs text-cyber-muted ml-auto">
            {data.total} {data.total === 1 ? 'entry' : 'entries'}
          </span>
        )}
      </div>

      <div className="cyber-card overflow-hidden">
        {isLoading ? (
          <TableSkeleton rows={5} cols={5} />
        ) : items.length === 0 ? (
          <EmptyState
            title="No watchlist entries"
            description="Add IPs, users, file hashes, or domains to monitor. Matching events are automatically tagged on ingest."
            icon={<List className="w-8 h-8 text-cyber-muted" />}
          />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-cyber-border bg-cyber-bg/30">
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Type</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Value</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider hidden md:table-cell">Label</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider hidden lg:table-cell">Tags</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider hidden xl:table-cell">Notes</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider hidden lg:table-cell">Added</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-cyber-border/30">
              {items.map((item) => (
                <tr key={item.id} className="table-row-hover">
                  <td className="px-5 py-3">
                    <TypeBadge type={item.entry_type} />
                  </td>
                  <td className="px-5 py-3 font-mono text-sm text-cyber-text">{item.value}</td>
                  <td className="px-5 py-3 text-sm text-cyber-muted hidden md:table-cell">
                    {item.label || '—'}
                  </td>
                  <td className="px-5 py-3 hidden lg:table-cell">
                    {item.tags && item.tags.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {item.tags.map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 bg-cyber-border/40 text-cyber-muted rounded font-mono"
                          >
                            <Tag className="w-2.5 h-2.5" />
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-cyber-muted/40">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-xs text-cyber-muted hidden xl:table-cell max-w-[200px]">
                    <span className="truncate block" title={item.notes ?? undefined}>
                      {item.notes || '—'}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-cyber-muted hidden lg:table-cell whitespace-nowrap">
                    {formatTs(item.created_at)}
                  </td>
                  <td className="px-5 py-3">
                    <button
                      onClick={() => setDeleting(item)}
                      title="Remove"
                      className="p-1.5 text-cyber-muted hover:text-cyber-danger rounded transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <AddForm onClose={() => setShowForm(false)} onSaved={() => setShowForm(false)} />
      )}

      {deleting && (
        <ConfirmDialog
          isOpen={!!deleting}
          title="Remove watchlist entry"
          message={`Remove "${deleting.value}" from the watchlist? Existing event tags will not be changed.`}
          confirmLabel="Remove"
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onCancel={() => setDeleting(null)}
          danger
        />
      )}
    </div>
  );
};

export default Watchlist;
