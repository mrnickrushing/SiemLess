import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Monitor,
  Search,
  RefreshCw,
  Shield,
  Package,
  AlertTriangle,
  Activity,
  ChevronRight,
  ScanLine,
} from 'lucide-react';
import {
  getAssets,
  getAssetSoftware,
  getAssetVulnerabilities,
  getAssetEvents,
  scanAssetCVEs,
} from '../api/assets';
import type { Asset } from '../types';

const CRITICALITY_COLORS: Record<string, string> = {
  critical: 'text-red-400 bg-red-400/10 border-red-400/30',
  high: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  medium: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  low: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
};

const CVSS_COLOR = (score: number) => {
  if (score >= 9) return 'text-red-400';
  if (score >= 7) return 'text-orange-400';
  if (score >= 4) return 'text-yellow-400';
  return 'text-blue-400';
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

type AssetTab = 'overview' | 'software' | 'vulnerabilities' | 'events';

const AssetDetail: React.FC<{ asset: Asset }> = ({ asset }) => {
  const [activeTab, setActiveTab] = useState<AssetTab>('overview');
  const qc = useQueryClient();

  const { data: software } = useQuery({
    queryKey: ['asset-software', asset.id],
    queryFn: () => getAssetSoftware(asset.id),
    enabled: activeTab === 'software',
  });

  const { data: vulns } = useQuery({
    queryKey: ['asset-vulns', asset.id],
    queryFn: () => getAssetVulnerabilities(asset.id),
    enabled: activeTab === 'vulnerabilities',
  });

  const { data: events } = useQuery({
    queryKey: ['asset-events', asset.id],
    queryFn: () => getAssetEvents(asset.id, { page_size: 20 }),
    enabled: activeTab === 'events',
  });

  const scanMutation = useMutation({
    mutationFn: () => scanAssetCVEs(asset.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['asset-vulns', asset.id] });
      qc.invalidateQueries({ queryKey: ['assets'] });
    },
  });

  const tabs: { id: AssetTab; label: string; icon: React.ReactNode }[] = [
    { id: 'overview', label: 'Overview', icon: <Monitor className="w-4 h-4" /> },
    { id: 'software', label: 'Software', icon: <Package className="w-4 h-4" /> },
    { id: 'vulnerabilities', label: `CVEs (${asset.cve_count})`, icon: <Shield className="w-4 h-4" /> },
    { id: 'events', label: 'Events', icon: <Activity className="w-4 h-4" /> },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-cyber-border flex-shrink-0">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold font-mono text-cyber-text truncate">
              {asset.hostname}
            </h2>
            <div className="flex flex-wrap items-center gap-2 mt-1.5">
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                CRITICALITY_COLORS[asset.criticality] ?? 'text-cyber-muted border-cyber-border'
              }`}>
                {asset.criticality}
              </span>
              <span className="text-xs text-cyber-muted bg-cyber-border/30 px-1.5 py-0.5 rounded">
                {asset.asset_type}
              </span>
              {asset.os_type && (
                <span className="text-xs text-cyber-muted">{asset.os_type} {asset.os_version}</span>
              )}
            </div>
          </div>
          <button
            onClick={() => scanMutation.mutate()}
            disabled={scanMutation.isPending}
            className="cyber-btn-secondary text-xs px-2.5 py-1.5 flex items-center gap-1.5 flex-shrink-0"
          >
            {scanMutation.isPending ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ScanLine className="w-3.5 h-3.5" />
            )}
            Scan CVEs
          </button>
        </div>
        <div className="flex flex-wrap gap-1 mt-2">
          {(asset.ip_addresses ?? []).map((ip) => (
            <span key={ip} className="text-xs font-mono text-cyber-muted bg-cyber-border/20 px-1.5 py-0.5 rounded">
              {ip}
            </span>
          ))}
        </div>
        {(asset.tags ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {(asset.tags ?? []).map((tag) => (
              <span key={tag} className="text-xs px-1.5 py-0.5 rounded-full bg-cyber-border/40 text-cyber-muted">
                {tag}
              </span>
            ))}
          </div>
        )}
        <p className="text-xs text-cyber-muted/60 mt-2">
          First seen {formatDate(asset.first_seen)} · Last seen {formatDate(asset.last_seen)}
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
        {activeTab === 'overview' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Asset Type', value: asset.asset_type },
                { label: 'Criticality', value: asset.criticality },
                { label: 'OS Type', value: asset.os_type ?? '—' },
                { label: 'OS Version', value: asset.os_version ?? '—' },
                { label: 'CVE Count', value: String(asset.cve_count) },
              ].map((row) => (
                <div key={row.label} className="cyber-card p-3">
                  <p className="text-xs text-cyber-muted">{row.label}</p>
                  <p className="text-sm font-medium text-cyber-text mt-0.5">{row.value}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'software' && (
          <div className="space-y-2">
            {!software?.length && (
              <p className="text-xs text-cyber-muted text-center py-8">No software inventory.</p>
            )}
            {software?.map((sw) => (
              <div key={sw.id} className="cyber-card p-3 flex items-center gap-3">
                <Package className="w-4 h-4 text-cyber-muted flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-cyber-text">{sw.name}</p>
                  {sw.version && (
                    <p className="text-xs text-cyber-muted">v{sw.version}</p>
                  )}
                  {sw.cpe && (
                    <p className="text-xs font-mono text-cyber-muted/60 truncate">{sw.cpe}</p>
                  )}
                </div>
                <p className="text-xs text-cyber-muted flex-shrink-0">
                  {formatDate(sw.last_scanned)}
                </p>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'vulnerabilities' && (
          <div className="space-y-2">
            {!vulns?.length && (
              <div className="text-center py-8">
                <Shield className="w-8 h-8 text-cyber-accent/30 mx-auto mb-2" />
                <p className="text-xs text-cyber-muted">No vulnerabilities found</p>
                <p className="text-xs text-cyber-muted/60 mt-1">
                  Run a CVE scan to check for known vulnerabilities
                </p>
              </div>
            )}
            {vulns?.map((v) => (
              <div key={v.id} className="cyber-card p-3">
                <div className="flex items-start gap-3">
                  <AlertTriangle className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                    v.severity === 'critical' ? 'text-red-400' :
                    v.severity === 'high' ? 'text-orange-400' :
                    v.severity === 'medium' ? 'text-yellow-400' : 'text-blue-400'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-medium text-cyber-text">{v.cve_id}</span>
                      {v.cvss_score !== null && (
                        <span className={`text-xs font-bold ${CVSS_COLOR(v.cvss_score)}`}>
                          CVSS {v.cvss_score.toFixed(1)}
                        </span>
                      )}
                    </div>
                    {v.description && (
                      <p className="text-xs text-cyber-muted mt-1 leading-relaxed line-clamp-2">
                        {v.description}
                      </p>
                    )}
                    <p className="text-xs text-cyber-muted/60 mt-1">
                      {v.published_at ? `Published ${formatDate(v.published_at)}` : ''}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'events' && (
          <div className="space-y-2">
            {!events?.items.length && (
              <p className="text-xs text-cyber-muted text-center py-8">No events linked to this asset.</p>
            )}
            {events?.items.map((e) => (
              <div key={e.id} className="cyber-card p-3 flex items-center gap-3">
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  e.severity === 'critical' ? 'bg-red-400' :
                  e.severity === 'high' ? 'bg-orange-400' :
                  e.severity === 'medium' ? 'bg-yellow-400' : 'bg-blue-400'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-cyber-text truncate">{e.message}</p>
                  <p className="text-xs text-cyber-muted">{e.event_type} · {formatDate(e.timestamp)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const Assets: React.FC = () => {
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [search, setSearch] = useState('');
  const [critFilter, setCritFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['assets', page, search, critFilter, typeFilter],
    queryFn: () =>
      getAssets({
        page,
        page_size: 25,
        search: search || undefined,
        criticality: critFilter || undefined,
        asset_type: typeFilter || undefined,
      }),
  });

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left Panel */}
      <div className="w-80 flex-shrink-0 border-r border-cyber-border flex flex-col">
        {/* Header */}
        <div className="px-4 py-3 border-b border-cyber-border">
          <div className="flex items-center gap-2 mb-3">
            <Monitor className="w-4 h-4 text-cyber-accent" />
            <h1 className="text-sm font-semibold text-cyber-text">Assets</h1>
            {data && (
              <span className="text-xs text-cyber-muted bg-cyber-border/30 px-1.5 py-0.5 rounded-full ml-auto">
                {data.total}
              </span>
            )}
          </div>
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-cyber-muted" />
            <input
              className="cyber-input w-full pl-8 text-xs"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="Search hostname, IP..."
            />
          </div>
        </div>

        {/* Filters */}
        <div className="px-3 py-2 border-b border-cyber-border flex gap-2">
          <select
            className="cyber-input flex-1 text-xs"
            value={critFilter}
            onChange={(e) => { setCritFilter(e.target.value); setPage(1); }}
          >
            <option value="">All Criticalities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select
            className="cyber-input flex-1 text-xs"
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          >
            <option value="">All Types</option>
            <option value="server">Server</option>
            <option value="workstation">Workstation</option>
            <option value="network">Network</option>
            <option value="cloud">Cloud</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-12 text-cyber-muted">
              <RefreshCw className="w-5 h-5 animate-spin" />
            </div>
          )}
          {!isLoading && !data?.items.length && (
            <div className="text-center py-12">
              <Monitor className="w-8 h-8 text-cyber-muted/30 mx-auto mb-2" />
              <p className="text-sm text-cyber-muted">No assets found</p>
              <p className="text-xs text-cyber-muted/60 mt-1">
                Assets are auto-discovered from events
              </p>
            </div>
          )}
          {data?.items.map((asset) => (
            <button
              key={asset.id}
              onClick={() => setSelectedAsset(asset)}
              className={`w-full text-left px-4 py-3 border-b border-cyber-border/40 hover:bg-cyber-border/10 transition-colors ${
                selectedAsset?.id === asset.id
                  ? 'bg-cyber-accent/5 border-l-2 border-l-cyber-accent'
                  : ''
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium font-mono text-cyber-text truncate flex-1">
                  {asset.hostname}
                </p>
                <ChevronRight className="w-4 h-4 text-cyber-muted flex-shrink-0 mt-0.5" />
              </div>
              <div className="flex items-center gap-2 mt-1.5">
                <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${
                  CRITICALITY_COLORS[asset.criticality] ?? 'text-cyber-muted border-cyber-border'
                }`}>
                  {asset.criticality}
                </span>
                <span className="text-xs text-cyber-muted">{asset.asset_type}</span>
                {asset.cve_count > 0 && (
                  <span className="text-xs text-red-400 ml-auto">
                    {asset.cve_count} CVE{asset.cve_count !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              {(asset.ip_addresses ?? []).length > 0 && (
                <p className="text-xs font-mono text-cyber-muted/60 mt-1 truncate">
                  {(asset.ip_addresses ?? []).join(', ')}
                </p>
              )}
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
        {selectedAsset ? (
          <AssetDetail asset={selectedAsset} />
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-cyber-muted">
            <Monitor className="w-12 h-12 opacity-20 mb-3" />
            <p className="text-sm">Select an asset to view details</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Assets;
