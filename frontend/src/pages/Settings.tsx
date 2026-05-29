import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings as SettingsIcon,
  Shield,
  Bell,
  Clock,
  Trash2,
  Wifi,
  AlertTriangle,
  CheckCircle,
  Info,
  RefreshCw,
  ExternalLink,
  Key,
  Users,
  LogIn,
  Database,
  Link2,
  Rss,
  Plus,
  X,
  Eye,
  EyeOff,
} from 'lucide-react';
import { checkBackendHealth } from '../api/stats';
import client from '../api/client';
import type { OrgUser, APIToken, IntegrationConfig, ThreatFeedConnector } from '../types';

// ─── Shared display helpers ────────────────────────────────────────────────

interface SettingRow {
  key: string;
  label: string;
  description: string;
  value: string | number | boolean | null;
  sensitive?: boolean;
  link?: string;
}

interface SettingSection {
  title: string;
  icon: React.ReactNode;
  rows: SettingRow[];
}

const StatusPill: React.FC<{ value: boolean; trueLabel?: string; falseLabel?: string }> = ({
  value,
  trueLabel = 'Enabled',
  falseLabel = 'Disabled',
}) => (
  <span
    className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
      value
        ? 'bg-cyber-accent/10 text-cyber-accent border border-cyber-accent/20'
        : 'bg-cyber-border/30 text-cyber-muted border border-cyber-border/50'
    }`}
  >
    {value ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
    {value ? trueLabel : falseLabel}
  </span>
);

const ValueDisplay: React.FC<{ row: SettingRow }> = ({ row }) => {
  if (row.sensitive) {
    return (
      <span className="text-xs font-mono text-cyber-muted bg-cyber-border/20 px-2 py-0.5 rounded">
        {row.value ? '••••••••' : <span className="text-cyber-danger">Not set</span>}
      </span>
    );
  }
  if (typeof row.value === 'boolean') return <StatusPill value={row.value} />;
  if (row.value === null || row.value === undefined || row.value === '') {
    return <span className="text-xs text-cyber-muted/50 italic">Not configured</span>;
  }
  return (
    <span className="text-sm font-mono text-cyber-text">
      {String(row.value)}
      {row.link && (
        <a href={row.link} target="_blank" rel="noopener noreferrer"
          className="ml-2 inline-flex items-center gap-0.5 text-cyber-accent hover:underline">
          <ExternalLink className="w-3 h-3" />
        </a>
      )}
    </span>
  );
};

// ─── SSO Configuration section ────────────────────────────────────────────

interface SSOConfig {
  id: string;
  provider_name: string;
  client_id: string;
  client_secret_masked: string;
  authorization_endpoint: string;
  token_endpoint: string;
  userinfo_endpoint: string | null;
  jwks_uri: string;
  scopes: string;
  enabled: boolean;
}

const SSOSection: React.FC = () => {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    provider_name: '',
    client_id: '',
    client_secret: '',
    authorization_endpoint: '',
    token_endpoint: '',
    userinfo_endpoint: '',
    jwks_uri: '',
    scopes: 'openid email profile',
    enabled: true,
  });

  const { data: configs } = useQuery<SSOConfig[]>({
    queryKey: ['sso-configs'],
    queryFn: async () => {
      const res = await client.get('/auth/sso/configs');
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      const res = await client.post('/auth/sso/configs', data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sso-configs'] });
      setShowForm(false);
      setForm({ provider_name: '', client_id: '', client_secret: '', authorization_endpoint: '',
        token_endpoint: '', userinfo_endpoint: '', jwks_uri: '', scopes: 'openid email profile', enabled: true });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await client.delete(`/auth/sso/configs/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sso-configs'] }),
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
      await client.patch(`/auth/sso/configs/${id}`, { enabled });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sso-configs'] }),
  });

  return (
    <div className="cyber-card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-cyber-border bg-cyber-bg/30">
        <div className="flex items-center gap-2.5">
          <LogIn className="w-4 h-4 text-cyber-muted" />
          <h2 className="text-sm font-semibold text-cyber-text uppercase tracking-wider">SSO Configuration</h2>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="cyber-btn-secondary text-xs px-2.5 py-1.5">
          <Plus className="w-3.5 h-3.5 mr-1" /> Add Provider
        </button>
      </div>

      {showForm && (
        <div className="p-4 border-b border-cyber-border bg-cyber-border/5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            {[
              { key: 'provider_name' as const, label: 'Provider Name', placeholder: 'e.g. Okta' },
              { key: 'client_id' as const, label: 'Client ID', placeholder: '' },
              { key: 'client_secret' as const, label: 'Client Secret', placeholder: '••••' },
              { key: 'scopes' as const, label: 'Scopes', placeholder: 'openid email profile' },
            ].map((f) => (
              <div key={f.key}>
                <label className="block text-xs text-cyber-muted mb-1">{f.label}</label>
                <input
                  className="cyber-input w-full text-sm"
                  type={f.key === 'client_secret' ? 'password' : 'text'}
                  value={form[f.key]}
                  onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                />
              </div>
            ))}
          </div>
          {[
            { key: 'authorization_endpoint' as const, label: 'Authorization Endpoint' },
            { key: 'token_endpoint' as const, label: 'Token Endpoint' },
            { key: 'userinfo_endpoint' as const, label: 'UserInfo Endpoint (optional)' },
            { key: 'jwks_uri' as const, label: 'JWKS URI' },
          ].map((f) => (
            <div key={f.key}>
              <label className="block text-xs text-cyber-muted mb-1">{f.label}</label>
              <input
                className="cyber-input w-full text-sm font-mono"
                value={form[f.key]}
                onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                placeholder="https://"
              />
            </div>
          ))}
          <div className="flex gap-2">
            <button onClick={() => setShowForm(false)} className="cyber-btn-secondary flex-1 text-xs">Cancel</button>
            <button
              onClick={() => createMutation.mutate(form)}
              disabled={!form.provider_name || !form.client_id || createMutation.isPending}
              className="cyber-btn flex-1 text-xs"
            >
              {createMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin mx-auto" /> : 'Save'}
            </button>
          </div>
        </div>
      )}

      <div className="divide-y divide-cyber-border/30">
        {!configs?.length && !showForm && (
          <p className="text-xs text-cyber-muted text-center py-6">No SSO providers configured.</p>
        )}
        {configs?.map((cfg) => (
          <div key={cfg.id} className="flex items-center gap-4 px-5 py-3.5">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-cyber-text">{cfg.provider_name}</p>
              <p className="text-xs text-cyber-muted font-mono truncate">{cfg.client_id}</p>
            </div>
            <StatusPill value={cfg.enabled} />
            <button
              onClick={() => toggleMutation.mutate({ id: cfg.id, enabled: !cfg.enabled })}
              className="text-xs cyber-btn-secondary px-2 py-1"
            >{cfg.enabled ? 'Disable' : 'Enable'}</button>
            <button
              onClick={() => confirm(`Delete SSO provider "${cfg.provider_name}"?`) && deleteMutation.mutate(cfg.id)}
              className="text-cyber-muted hover:text-cyber-danger"
            ><X className="w-4 h-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Users & Roles section ────────────────────────────────────────────────

const UsersSection: React.FC = () => {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ username: '', email: '', role: 'analyst' });

  const { data: users } = useQuery<{ items: OrgUser[]; total: number }>({
    queryKey: ['org-users'],
    queryFn: async () => {
      const res = await client.get('/admin/users');
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      const res = await client.post('/admin/users', data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['org-users'] });
      setShowForm(false);
      setForm({ username: '', email: '', role: 'analyst' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => { await client.delete(`/admin/users/${id}`); },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['org-users'] }),
  });

  const updateRoleMutation = useMutation({
    mutationFn: async ({ id, role }: { id: string; role: string }) => {
      await client.patch(`/admin/users/${id}`, { role });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['org-users'] }),
  });

  return (
    <div className="cyber-card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-cyber-border bg-cyber-bg/30">
        <div className="flex items-center gap-2.5">
          <Users className="w-4 h-4 text-cyber-muted" />
          <h2 className="text-sm font-semibold text-cyber-text uppercase tracking-wider">Users & Roles</h2>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="cyber-btn-secondary text-xs px-2.5 py-1.5">
          <Plus className="w-3.5 h-3.5 mr-1" /> Add User
        </button>
      </div>

      {showForm && (
        <div className="p-4 border-b border-cyber-border bg-cyber-border/5">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Username *</label>
              <input className="cyber-input w-full text-sm" value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} placeholder="username" />
            </div>
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Email</label>
              <input className="cyber-input w-full text-sm" value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} placeholder="user@example.com" />
            </div>
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Role</label>
              <select className="cyber-input w-full text-sm" value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
                <option value="read_only">Read Only</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={() => setShowForm(false)} className="cyber-btn-secondary flex-1 text-xs">Cancel</button>
            <button onClick={() => createMutation.mutate(form)}
              disabled={!form.username || createMutation.isPending}
              className="cyber-btn flex-1 text-xs">
              {createMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin mx-auto" /> : 'Add User'}
            </button>
          </div>
        </div>
      )}

      <div className="divide-y divide-cyber-border/30">
        {!users?.items.length && !showForm && (
          <p className="text-xs text-cyber-muted text-center py-6">No additional users configured.</p>
        )}
        {users?.items.map((user) => (
          <div key={user.id} className="flex items-center gap-4 px-5 py-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-cyber-text">{user.username}</p>
              {user.email && <p className="text-xs text-cyber-muted">{user.email}</p>}
            </div>
            <select
              className="cyber-input text-xs"
              value={user.role}
              onChange={(e) => updateRoleMutation.mutate({ id: user.id, role: e.target.value })}
            >
              <option value="analyst">Analyst</option>
              <option value="admin">Admin</option>
              <option value="read_only">Read Only</option>
            </select>
            <button onClick={() => confirm(`Remove user "${user.username}"?`) && deleteMutation.mutate(user.id)}
              className="text-cyber-muted hover:text-cyber-danger">
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── API Tokens section ────────────────────────────────────────────────────

const APITokensSection: React.FC = () => {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ description: '', expires_days: '' });
  const [newToken, setNewToken] = useState<string | null>(null);
  const [showToken, setShowToken] = useState(false);

  const { data: tokens } = useQuery<{ items: APIToken[]; total: number }>({
    queryKey: ['api-tokens'],
    queryFn: async () => {
      const res = await client.get('/admin/tokens');
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      const payload: Record<string, unknown> = { description: data.description };
      if (data.expires_days) payload.expires_days = Number(data.expires_days);
      const res = await client.post('/admin/tokens', payload);
      return res.data as APIToken;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['api-tokens'] });
      if (data.raw_token) {
        setNewToken(data.raw_token);
        setShowToken(true);
      }
      setShowForm(false);
      setForm({ description: '', expires_days: '' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => { await client.delete(`/admin/tokens/${id}`); },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-tokens'] }),
  });

  return (
    <div className="cyber-card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-cyber-border bg-cyber-bg/30">
        <div className="flex items-center gap-2.5">
          <Key className="w-4 h-4 text-cyber-muted" />
          <h2 className="text-sm font-semibold text-cyber-text uppercase tracking-wider">API Tokens</h2>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="cyber-btn-secondary text-xs px-2.5 py-1.5">
          <Plus className="w-3.5 h-3.5 mr-1" /> Issue Token
        </button>
      </div>

      {newToken && (
        <div className="px-5 py-3 bg-cyber-accent/5 border-b border-cyber-accent/20">
          <p className="text-xs font-medium text-cyber-accent mb-2">New token (copy now — not shown again):</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono bg-cyber-border/20 px-3 py-2 rounded truncate">
              {showToken ? newToken : '••••••••••••••••••••••••••••••••'}
            </code>
            <button onClick={() => setShowToken(!showToken)} className="text-cyber-muted hover:text-cyber-text">
              {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
            <button onClick={() => navigator.clipboard.writeText(newToken)}
              className="cyber-btn-secondary text-xs px-2 py-1">Copy</button>
            <button onClick={() => setNewToken(null)} className="text-cyber-muted hover:text-cyber-text">
              <X className="w-4 h-4" /></button>
          </div>
        </div>
      )}

      {showForm && (
        <div className="p-4 border-b border-cyber-border bg-cyber-border/5">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Description</label>
              <input className="cyber-input w-full text-sm" value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="e.g. CI Pipeline" />
            </div>
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Expires (days, optional)</label>
              <input className="cyber-input w-full text-sm" type="number" value={form.expires_days}
                onChange={(e) => setForm((f) => ({ ...f, expires_days: e.target.value }))}
                placeholder="365" />
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <button onClick={() => setShowForm(false)} className="cyber-btn-secondary flex-1 text-xs">Cancel</button>
            <button onClick={() => createMutation.mutate(form)}
              disabled={createMutation.isPending}
              className="cyber-btn flex-1 text-xs">
              {createMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin mx-auto" /> : 'Issue'}
            </button>
          </div>
        </div>
      )}

      <div className="divide-y divide-cyber-border/30">
        {!tokens?.items.length && !showForm && (
          <p className="text-xs text-cyber-muted text-center py-6">No API tokens issued.</p>
        )}
        {tokens?.items.map((token) => (
          <div key={token.id} className="flex items-center gap-4 px-5 py-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-cyber-text">{token.description ?? 'Unnamed token'}</p>
              <p className="text-xs text-cyber-muted">
                @{token.username} ·
                {token.expires_at
                  ? ` Expires ${new Date(token.expires_at).toLocaleDateString()}`
                  : ' No expiry'}
              </p>
            </div>
            <button onClick={() => confirm('Revoke this API token?') && deleteMutation.mutate(token.id)}
              className="text-cyber-muted hover:text-cyber-danger">
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Integrations section ─────────────────────────────────────────────────

const IntegrationsSection: React.FC = () => {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: '',
    integration_type: 'jira',
    config_raw: '{}',
    enabled: true,
  });

  const { data: integrations } = useQuery<{ items: IntegrationConfig[]; total: number }>({
    queryKey: ['integrations'],
    queryFn: async () => {
      const res = await client.get('/integrations');
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      const res = await client.post('/integrations', {
        name: data.name,
        integration_type: data.integration_type,
        config: JSON.parse(data.config_raw),
        enabled: data.enabled,
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['integrations'] });
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => { await client.delete(`/integrations/${id}`); },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['integrations'] }),
  });

  const testMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await client.post(`/integrations/${id}/test`);
      return res.data;
    },
  });

  return (
    <div className="cyber-card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-cyber-border bg-cyber-bg/30">
        <div className="flex items-center gap-2.5">
          <Link2 className="w-4 h-4 text-cyber-muted" />
          <h2 className="text-sm font-semibold text-cyber-text uppercase tracking-wider">Integrations</h2>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="cyber-btn-secondary text-xs px-2.5 py-1.5">
          <Plus className="w-3.5 h-3.5 mr-1" /> Add
        </button>
      </div>

      {showForm && (
        <div className="p-4 border-b border-cyber-border bg-cyber-border/5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Name</label>
              <input className="cyber-input w-full text-sm" value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="My Jira" />
            </div>
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Type</label>
              <select className="cyber-input w-full text-sm" value={form.integration_type}
                onChange={(e) => setForm((f) => ({ ...f, integration_type: e.target.value }))}>
                <option value="jira">Jira</option>
                <option value="servicenow">ServiceNow</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-cyber-muted mb-1">Config JSON</label>
            <textarea className="cyber-input w-full h-24 resize-none text-xs font-mono" value={form.config_raw}
              onChange={(e) => setForm((f) => ({ ...f, config_raw: e.target.value }))}
              placeholder='{"url": "https://...", "api_token": "..."}'/>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowForm(false)} className="cyber-btn-secondary flex-1 text-xs">Cancel</button>
            <button onClick={() => createMutation.mutate(form)}
              disabled={!form.name || createMutation.isPending}
              className="cyber-btn flex-1 text-xs">Save</button>
          </div>
        </div>
      )}

      <div className="divide-y divide-cyber-border/30">
        {!integrations?.items.length && !showForm && (
          <p className="text-xs text-cyber-muted text-center py-6">No integrations configured.</p>
        )}
        {integrations?.items.map((integ) => (
          <div key={integ.id} className="flex items-center gap-4 px-5 py-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-cyber-text">{integ.name}</p>
              <p className="text-xs text-cyber-muted">{integ.integration_type}</p>
            </div>
            <StatusPill value={integ.enabled} />
            <button onClick={() => testMutation.mutate(integ.id)}
              disabled={testMutation.isPending}
              className="cyber-btn-secondary text-xs px-2 py-1">Test</button>
            <button onClick={() => confirm(`Delete integration "${integ.name}"?`) && deleteMutation.mutate(integ.id)}
              className="text-cyber-muted hover:text-cyber-danger">
              <X className="w-4 h-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Threat Feeds section ─────────────────────────────────────────────────

const ThreatFeedsSection: React.FC = () => {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: '', feed_type: 'misp', url: '', api_key: '', pull_interval_hours: '24',
  });

  const { data: feeds } = useQuery<{ items: ThreatFeedConnector[]; total: number }>({
    queryKey: ['threat-feeds'],
    queryFn: async () => {
      const res = await client.get('/threat-feeds');
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      const res = await client.post('/threat-feeds', {
        ...data,
        pull_interval_hours: Number(data.pull_interval_hours),
        enabled: true,
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['threat-feeds'] });
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => { await client.delete(`/threat-feeds/${id}`); },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['threat-feeds'] }),
  });

  const pullMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await client.post(`/threat-feeds/${id}/pull`);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['threat-feeds'] }),
  });

  return (
    <div className="cyber-card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-cyber-border bg-cyber-bg/30">
        <div className="flex items-center gap-2.5">
          <Rss className="w-4 h-4 text-cyber-muted" />
          <h2 className="text-sm font-semibold text-cyber-text uppercase tracking-wider">Threat Feeds</h2>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="cyber-btn-secondary text-xs px-2.5 py-1.5">
          <Plus className="w-3.5 h-3.5 mr-1" /> Add Feed
        </button>
      </div>

      {showForm && (
        <div className="p-4 border-b border-cyber-border bg-cyber-border/5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Name</label>
              <input className="cyber-input w-full text-sm" value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Type</label>
              <select className="cyber-input w-full text-sm" value={form.feed_type}
                onChange={(e) => setForm((f) => ({ ...f, feed_type: e.target.value }))}>
                <option value="misp">MISP</option>
                <option value="opencti">OpenCTI</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-cyber-muted mb-1">URL</label>
              <input className="cyber-input w-full text-sm font-mono" value={form.url}
                onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} placeholder="https://" />
            </div>
            <div>
              <label className="block text-xs text-cyber-muted mb-1">API Key</label>
              <input className="cyber-input w-full text-sm" type="password" value={form.api_key}
                onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))} placeholder="••••" />
            </div>
            <div>
              <label className="block text-xs text-cyber-muted mb-1">Pull Interval (hours)</label>
              <input className="cyber-input w-full text-sm" type="number" value={form.pull_interval_hours}
                onChange={(e) => setForm((f) => ({ ...f, pull_interval_hours: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowForm(false)} className="cyber-btn-secondary flex-1 text-xs">Cancel</button>
            <button onClick={() => createMutation.mutate(form)}
              disabled={!form.name || !form.url || createMutation.isPending}
              className="cyber-btn flex-1 text-xs">Save</button>
          </div>
        </div>
      )}

      <div className="divide-y divide-cyber-border/30">
        {!feeds?.items.length && !showForm && (
          <p className="text-xs text-cyber-muted text-center py-6">No threat feeds configured.</p>
        )}
        {feeds?.items.map((feed) => (
          <div key={feed.id} className="flex items-center gap-4 px-5 py-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-cyber-text">{feed.name}</p>
              <p className="text-xs text-cyber-muted">
                {feed.feed_type} · {feed.indicator_count.toLocaleString()} indicators
                {feed.last_pulled_at && ` · Last pull: ${new Date(feed.last_pulled_at).toLocaleDateString()}`}
              </p>
              {feed.last_error && (
                <p className="text-xs text-red-400 truncate">{feed.last_error}</p>
              )}
            </div>
            <StatusPill value={feed.enabled} />
            <button onClick={() => pullMutation.mutate(feed.id)}
              disabled={pullMutation.isPending}
              className="cyber-btn-secondary text-xs px-2 py-1">
              {pullMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : 'Pull Now'}
            </button>
            <button onClick={() => confirm(`Delete feed "${feed.name}"?`) && deleteMutation.mutate(feed.id)}
              className="text-cyber-muted hover:text-cyber-danger">
              <X className="w-4 h-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Main Settings page ───────────────────────────────────────────────────

const Settings: React.FC = () => {
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ['health', refreshKey],
    queryFn: async () => {
      const online = await checkBackendHealth();
      return { online };
    },
  });

  const { data: openApi } = useQuery({
    queryKey: ['openapi'],
    queryFn: async () => {
      const res = await fetch('/openapi.json');
      if (!res.ok) return null;
      return res.json();
    },
    staleTime: Infinity,
  });

  const appVersion = openApi?.info?.version ?? '—';
  const appTitle = openApi?.info?.title ?? 'SiemLess';

  const sections: SettingSection[] = [
    {
      title: 'Application',
      icon: <SettingsIcon className="w-4 h-4" />,
      rows: [
        { key: 'app_name', label: 'Application Name', description: 'Display name of this SiemLess instance', value: appTitle },
        { key: 'app_version', label: 'Version', description: 'Current running version of the API', value: appVersion },
        { key: 'api_docs', label: 'API Documentation', description: 'Interactive Swagger docs for all API endpoints', value: '/docs', link: '/docs' },
        { key: 'redoc', label: 'ReDoc', description: 'Alternative API reference documentation', value: '/redoc', link: '/redoc' },
      ],
    },
    {
      title: 'Security',
      icon: <Shield className="w-4 h-4" />,
      rows: [
        { key: 'admin_username', label: 'Admin Username', description: 'Username for the admin account (set via ADMIN_USERNAME env var)', value: 'admin' },
        { key: 'admin_password', label: 'Admin Password', description: 'Set via ADMIN_PASSWORD environment variable', value: true, sensitive: true },
        { key: 'secret_key', label: 'JWT Secret Key', description: 'Set via SECRET_KEY environment variable. Use openssl rand -hex 32 to generate.', value: true, sensitive: true },
        { key: 'token_expiry', label: 'Session Duration', description: 'JWT access token lifetime (ACCESS_TOKEN_EXPIRE_MINUTES)', value: '60 minutes' },
        { key: 'brute_force', label: 'Brute-Force Protection', description: 'Max 10 failed login attempts per 5 min window before lockout', value: true },
        { key: 'security_headers', label: 'Security Headers', description: 'X-Frame-Options, X-XSS-Protection, CSP, Permissions-Policy applied on all responses', value: true },
      ],
    },
    {
      title: 'Syslog Ingestion',
      icon: <Wifi className="w-4 h-4" />,
      rows: [
        { key: 'syslog_enabled', label: 'Syslog Server', description: 'UDP/TCP syslog listener (SYSLOG_ENABLED)', value: true },
        { key: 'syslog_host', label: 'Listen Host', description: 'Interface the syslog server binds to (SYSLOG_HOST)', value: '0.0.0.0' },
        { key: 'syslog_port', label: 'Listen Port', description: 'UDP/TCP port for syslog (SYSLOG_PORT)', value: 514 },
      ],
    },
    {
      title: 'SLA Tracking',
      icon: <Clock className="w-4 h-4" />,
      rows: [
        { key: 'sla_critical', label: 'Critical SLA', description: 'Minutes before a critical-severity open alert is marked SLA breached (SLA_CRITICAL_MINUTES)', value: '15 minutes' },
        { key: 'sla_high', label: 'High SLA', description: 'Minutes before a high-severity open alert is marked SLA breached (SLA_HIGH_MINUTES)', value: '60 minutes' },
        { key: 'sla_check_interval', label: 'Check Interval', description: 'How often the SLA checker runs (SLA_CHECK_INTERVAL)', value: '300 seconds' },
      ],
    },
    {
      title: 'Data Retention',
      icon: <Trash2 className="w-4 h-4" />,
      rows: [
        { key: 'retention_days', label: 'Event Retention', description: 'Security events older than this are automatically purged (EVENT_RETENTION_DAYS). Set to 0 to disable.', value: '90 days' },
        { key: 'retention_interval', label: 'Purge Interval', description: 'How often the retention purge task runs (RETENTION_CHECK_INTERVAL)', value: '86400 seconds (1 day)' },
      ],
    },
    {
      title: 'Alerting & Integrations',
      icon: <Bell className="w-4 h-4" />,
      rows: [
        { key: 'smtp', label: 'SMTP Email Alerts', description: 'Configure via SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL', value: null },
        { key: 'slack', label: 'Slack Webhook', description: 'Configure via SLACK_WEBHOOK_URL', value: null },
        { key: 'webhook', label: 'Generic Webhook', description: 'Configure via ALERT_WEBHOOK_URL', value: null },
        { key: 'virustotal', label: 'VirusTotal API Key', description: 'Configure via THREAT_INTEL_VIRUSTOTAL_KEY', value: null, sensitive: true },
        { key: 'abuseipdb', label: 'AbuseIPDB API Key', description: 'Configure via THREAT_INTEL_ABUSEIPDB_KEY', value: null, sensitive: true },
      ],
    },
  ];

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-cyber-text">Settings</h1>
          <p className="text-sm text-cyber-muted mt-1">
            Runtime configuration overview. All values are set via environment variables.
          </p>
        </div>
        <button
          onClick={() => { setRefreshKey((k) => k + 1); refetchHealth(); }}
          className="flex items-center gap-2 cyber-btn-secondary"
          disabled={healthLoading}
        >
          <RefreshCw className={`w-4 h-4 ${healthLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Backend Status Banner */}
      <div className={`cyber-card p-4 mb-6 flex items-center gap-3 border ${
        health?.online ? 'border-cyber-accent/20 bg-cyber-accent/5' : 'border-cyber-danger/20 bg-cyber-danger/5'
      }`}>
        {health?.online ? (
          <CheckCircle className="w-5 h-5 text-cyber-accent flex-shrink-0" />
        ) : (
          <AlertTriangle className="w-5 h-5 text-cyber-danger flex-shrink-0" />
        )}
        <div>
          <p className={`text-sm font-medium ${health?.online ? 'text-cyber-accent' : 'text-cyber-danger'}`}>
            {healthLoading ? 'Checking backend…' : health?.online ? 'Backend connected and healthy' : 'Backend unreachable'}
          </p>
          <p className="text-xs text-cyber-muted mt-0.5">
            Health endpoint: <span className="font-mono">/health</span> · API: <span className="font-mono">/api/v1</span>
          </p>
        </div>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 p-4 rounded-lg bg-cyber-border/10 border border-cyber-border/30 mb-6">
        <Info className="w-4 h-4 text-cyber-muted flex-shrink-0 mt-0.5" />
        <p className="text-xs text-cyber-muted leading-relaxed">
          SiemLess is configured entirely via environment variables or a <span className="font-mono">.env</span> file.
          Restart the backend service after changing any value. Sensitive fields (passwords, API keys) are masked for security.
        </p>
      </div>

      {/* Static config sections */}
      <div className="space-y-6 mb-8">
        {sections.map((section) => (
          <div key={section.title} className="cyber-card overflow-hidden">
            <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-cyber-border bg-cyber-bg/30">
              <span className="text-cyber-muted">{section.icon}</span>
              <h2 className="text-sm font-semibold text-cyber-text uppercase tracking-wider">{section.title}</h2>
            </div>
            <div className="divide-y divide-cyber-border/30">
              {section.rows.map((row) => (
                <div key={row.key} className="flex flex-col sm:flex-row sm:items-center gap-2 px-5 py-3.5">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-cyber-text">{row.label}</p>
                    <p className="text-xs text-cyber-muted mt-0.5 leading-relaxed">{row.description}</p>
                  </div>
                  <div className="sm:text-right flex-shrink-0">
                    <ValueDisplay row={row} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Management sections */}
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-cyber-text mb-4 flex items-center gap-2">
            <Database className="w-5 h-5 text-cyber-accent" />
            Management
          </h2>
        </div>
        <SSOSection />
        <UsersSection />
        <APITokensSection />
        <IntegrationsSection />
        <ThreatFeedsSection />
      </div>

      {/* Footer */}
      <div className="mt-8 text-center">
        <p className="text-xs text-cyber-muted/50">
          SiemLess {appVersion} · To modify settings, update your environment variables and restart the backend.
        </p>
      </div>
    </div>
  );
};

export default Settings;
