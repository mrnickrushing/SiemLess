import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import { Bookmark, Plus, Play, Edit2, Trash2, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { getSavedSearches, createSavedSearch, updateSavedSearch, deleteSavedSearch } from '../api/savedSearches';
import { TableSkeleton } from '../components/shared/LoadingSpinner';
import EmptyState from '../components/shared/EmptyState';
import ConfirmDialog from '../components/shared/ConfirmDialog';
import type { SavedSearch } from '../types';

interface FormData {
  name: string;
  description: string;
  query: string;
}

const DEFAULT_FORM: FormData = { name: '', description: '', query: '' };

interface SavedSearchFormProps {
  initial?: SavedSearch | null;
  onClose: () => void;
  onSaved: () => void;
}

const SavedSearchForm: React.FC<SavedSearchFormProps> = ({ initial, onClose, onSaved }) => {
  const [form, setForm] = useState<FormData>(
    initial
      ? { name: initial.name, description: initial.description || '', query: initial.query }
      : DEFAULT_FORM
  );
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      initial ? updateSavedSearch(initial.id, data) : createSavedSearch(data),
    onSuccess: () => {
      toast.success(initial ? 'Search updated' : 'Search saved');
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
      onSaved();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.query.trim()) return;
    mutation.mutate(form);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="cyber-card w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-cyber-border">
          <h2 className="text-sm font-semibold text-cyber-text">
            {initial ? 'Edit Saved Search' : 'Save Search'}
          </h2>
          <button onClick={onClose} className="text-cyber-muted hover:text-cyber-text">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1.5">
              Name <span className="text-cyber-danger">*</span>
            </label>
            <input
              className="cyber-input w-full text-sm"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Failed SSH logins"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1.5">
              Query <span className="text-cyber-danger">*</span>
            </label>
            <input
              className="cyber-input w-full text-sm font-mono"
              value={form.query}
              onChange={(e) => setForm((f) => ({ ...f, query: e.target.value }))}
              placeholder="e.g. severity:high AND category:authentication"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1.5">Description</label>
            <textarea
              className="cyber-input w-full text-sm resize-none"
              rows={2}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Optional description"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="cyber-btn-secondary text-sm px-4 py-2">
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending || !form.name.trim() || !form.query.trim()}
              className="cyber-btn-primary text-sm px-4 py-2"
            >
              {mutation.isPending ? 'Saving…' : initial ? 'Update' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const SavedSearches: React.FC = () => {
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<SavedSearch | null>(null);
  const [deleting, setDeleting] = useState<SavedSearch | null>(null);
  const queryClient = useQueryClient();

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['saved-searches'],
    queryFn: getSavedSearches,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSavedSearch(id),
    onSuccess: () => {
      toast.success('Search deleted');
      queryClient.invalidateQueries({ queryKey: ['saved-searches'] });
      setDeleting(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

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
            <Bookmark className="w-6 h-6 text-cyber-accent" />
            Saved Searches
          </h1>
          <p className="text-sm text-cyber-muted mt-1">Store and reuse frequently used search queries</p>
        </div>
        <button
          onClick={() => { setEditing(null); setShowForm(true); }}
          className="cyber-btn-primary flex items-center gap-2 text-sm px-4 py-2"
        >
          <Plus className="w-4 h-4" />
          New Search
        </button>
      </div>

      <div className="cyber-card overflow-hidden">
        {isLoading ? (
          <TableSkeleton rows={5} cols={4} />
        ) : items.length === 0 ? (
          <EmptyState
            title="No saved searches"
            description="Save a search query to quickly re-run it later."
            icon={<Bookmark className="w-8 h-8 text-cyber-muted" />}
          />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-cyber-border bg-cyber-bg/30">
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Name</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">Query</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider hidden md:table-cell">Description</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider hidden lg:table-cell">Created</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-cyber-border/30">
              {items.map((item) => (
                <tr key={item.id} className="table-row-hover">
                  <td className="px-5 py-3 text-sm font-medium text-cyber-text">{item.name}</td>
                  <td className="px-5 py-3 max-w-xs">
                    <span
                      className="text-xs font-mono text-cyber-accent bg-cyber-accent/5 px-2 py-1 rounded truncate block"
                      title={item.query}
                    >
                      {item.query}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-cyber-muted hidden md:table-cell">
                    {item.description || '—'}
                  </td>
                  <td className="px-5 py-3 text-xs text-cyber-muted hidden lg:table-cell">
                    {formatTs(item.created_at)}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => navigate(`/search?q=${encodeURIComponent(item.query)}`)}
                        title="Run search"
                        className="p-1.5 text-cyber-muted hover:text-cyber-accent rounded transition-colors"
                      >
                        <Play className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => { setEditing(item); setShowForm(true); }}
                        title="Edit"
                        className="p-1.5 text-cyber-muted hover:text-cyber-text rounded transition-colors"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeleting(item)}
                        title="Delete"
                        className="p-1.5 text-cyber-muted hover:text-cyber-danger rounded transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <SavedSearchForm
          initial={editing}
          onClose={() => { setShowForm(false); setEditing(null); }}
          onSaved={() => { setShowForm(false); setEditing(null); }}
        />
      )}

      {deleting && (
        <ConfirmDialog
          isOpen={!!deleting}
          title="Delete saved search"
          message={`Delete "${deleting.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onCancel={() => setDeleting(null)}
          danger
        />
      )}
    </div>
  );
};

export default SavedSearches;
