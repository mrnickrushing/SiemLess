import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Brain,
  RefreshCw,
  AlertTriangle,
  User,
  Clock,
  Globe,
  Navigation,
  CheckCircle,
  Filter,
} from 'lucide-react';
import { getUEBAProfiles, getUEBAAnomalies, acknowledgeAnomaly, refreshBaselines } from '../api/ueba';

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const ANOMALY_TYPE_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  unusual_hour: {
    label: 'Unusual Hour',
    icon: <Clock className="w-4 h-4" />,
    color: 'text-yellow-400',
  },
  new_source_ip: {
    label: 'New Source IP',
    icon: <Globe className="w-4 h-4" />,
    color: 'text-orange-400',
  },
  impossible_travel: {
    label: 'Impossible Travel',
    icon: <Navigation className="w-4 h-4" />,
    color: 'text-red-400',
  },
};

function getAnomalyMeta(type: string) {
  return (
    ANOMALY_TYPE_META[type] ?? {
      label: type,
      icon: <AlertTriangle className="w-4 h-4" />,
      color: 'text-cyber-muted',
    }
  );
}

type ActiveTab = 'anomalies' | 'profiles';

const UEBA: React.FC = () => {
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<ActiveTab>('anomalies');
  const [anomalyTypeFilter, setAnomalyTypeFilter] = useState('');
  const [showAcknowledged, setShowAcknowledged] = useState(false);
  const [page, setPage] = useState(1);
  const [profilePage, setProfilePage] = useState(1);

  const { data: anomaliesData, isLoading: anomaliesLoading } = useQuery({
    queryKey: ['ueba-anomalies', page, anomalyTypeFilter, showAcknowledged],
    queryFn: () =>
      getUEBAAnomalies({
        page,
        page_size: 20,
        anomaly_type: anomalyTypeFilter || undefined,
        acknowledged: showAcknowledged ? undefined : false,
      }),
    enabled: activeTab === 'anomalies',
  });

  const { data: profilesData, isLoading: profilesLoading } = useQuery({
    queryKey: ['ueba-profiles', profilePage],
    queryFn: () => getUEBAProfiles({ page: profilePage, page_size: 20 }),
    enabled: activeTab === 'profiles',
  });

  const ackMutation = useMutation({
    mutationFn: acknowledgeAnomaly,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ueba-anomalies'] }),
  });

  const refreshMutation = useMutation({
    mutationFn: refreshBaselines,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ueba-profiles'] }),
  });

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-cyber-accent" />
          <div>
            <h1 className="text-2xl font-bold text-cyber-text">UEBA</h1>
            <p className="text-sm text-cyber-muted mt-0.5">User and Entity Behavior Analytics</p>
          </div>
        </div>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="cyber-btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${refreshMutation.isPending ? 'animate-spin' : ''}`} />
          Refresh Baselines
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 bg-cyber-border/20 rounded-lg w-fit">
        <button
          onClick={() => setActiveTab('anomalies')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'anomalies'
              ? 'bg-cyber-accent text-black'
              : 'text-cyber-muted hover:text-cyber-text'
          }`}
        >
          Anomalies
          {anomaliesData && anomaliesData.total > 0 && (
            <span className="ml-2 text-xs bg-cyber-danger text-white px-1.5 py-0.5 rounded-full">
              {anomaliesData.total}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('profiles')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'profiles'
              ? 'bg-cyber-accent text-black'
              : 'text-cyber-muted hover:text-cyber-text'
          }`}
        >
          User Profiles
        </button>
      </div>

      {activeTab === 'anomalies' && (
        <div>
          {/* Filters */}
          <div className="flex items-center gap-3 mb-4">
            <Filter className="w-4 h-4 text-cyber-muted" />
            <select
              className="cyber-input text-sm"
              value={anomalyTypeFilter}
              onChange={(e) => { setAnomalyTypeFilter(e.target.value); setPage(1); }}
            >
              <option value="">All Types</option>
              <option value="unusual_hour">Unusual Hour</option>
              <option value="new_source_ip">New Source IP</option>
              <option value="impossible_travel">Impossible Travel</option>
            </select>
            <label className="flex items-center gap-2 text-sm text-cyber-muted cursor-pointer">
              <input
                type="checkbox"
                checked={showAcknowledged}
                onChange={(e) => { setShowAcknowledged(e.target.checked); setPage(1); }}
                className="accent-cyber-accent"
              />
              Show Acknowledged
            </label>
          </div>

          {/* Anomalies Table */}
          <div className="cyber-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cyber-border">
                    <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">Type</th>
                    <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">User</th>
                    <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">Score</th>
                    <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">Details</th>
                    <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">Detected</th>
                    <th className="text-right text-xs font-medium text-cyber-muted px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cyber-border/30">
                  {anomaliesLoading && (
                    <tr>
                      <td colSpan={6} className="text-center py-10 text-cyber-muted">
                        <RefreshCw className="w-5 h-5 animate-spin inline" />
                      </td>
                    </tr>
                  )}
                  {!anomaliesLoading && !anomaliesData?.items.length && (
                    <tr>
                      <td colSpan={6} className="text-center py-10 text-cyber-muted text-sm">
                        No anomalies detected
                      </td>
                    </tr>
                  )}
                  {anomaliesData?.items.map((anomaly) => {
                    const meta = getAnomalyMeta(anomaly.anomaly_type);
                    return (
                      <tr
                        key={anomaly.id}
                        className={`hover:bg-cyber-border/10 ${anomaly.acknowledged ? 'opacity-50' : ''}`}
                      >
                        <td className="px-4 py-3">
                          <div className={`flex items-center gap-2 ${meta.color}`}>
                            {meta.icon}
                            <span className="text-xs font-medium">{meta.label}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <User className="w-3.5 h-3.5 text-cyber-muted" />
                            <span className="text-cyber-text font-mono">{anomaly.username}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 rounded-full bg-cyber-border overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  anomaly.score >= 60
                                    ? 'bg-red-400'
                                    : anomaly.score >= 30
                                    ? 'bg-orange-400'
                                    : 'bg-yellow-400'
                                }`}
                                style={{ width: `${Math.min(100, anomaly.score)}%` }}
                              />
                            </div>
                            <span className="text-xs font-mono text-cyber-muted">{anomaly.score}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <p className="text-xs text-cyber-muted font-mono max-w-[200px] truncate">
                            {anomaly.detail
                              ? Object.entries(anomaly.detail)
                                  .map(([k, v]) => `${k}=${v}`)
                                  .join(' ')
                              : '—'}
                          </p>
                        </td>
                        <td className="px-4 py-3 text-xs text-cyber-muted">
                          {formatDate(anomaly.detected_at)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {!anomaly.acknowledged && (
                            <button
                              onClick={() => ackMutation.mutate(anomaly.id)}
                              disabled={ackMutation.isPending}
                              className="cyber-btn-secondary text-xs px-2 py-1 flex items-center gap-1 ml-auto"
                            >
                              <CheckCircle className="w-3.5 h-3.5" />
                              Ack
                            </button>
                          )}
                          {anomaly.acknowledged && (
                            <span className="text-xs text-cyber-muted">Acknowledged</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {anomaliesData && anomaliesData.pages > 1 && (
              <div className="flex items-center justify-between px-4 py-2 border-t border-cyber-border">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="text-xs text-cyber-muted disabled:opacity-40 hover:text-cyber-text"
                >Prev</button>
                <span className="text-xs text-cyber-muted">{page} / {anomaliesData.pages}</span>
                <button
                  onClick={() => setPage((p) => Math.min(anomaliesData.pages, p + 1))}
                  disabled={page === anomaliesData.pages}
                  className="text-xs text-cyber-muted disabled:opacity-40 hover:text-cyber-text"
                >Next</button>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'profiles' && (
        <div className="cyber-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cyber-border">
                  <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">User</th>
                  <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">Known IPs</th>
                  <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">Events (30d)</th>
                  <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">Typical Hours</th>
                  <th className="text-left text-xs font-medium text-cyber-muted px-4 py-3">Last Activity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cyber-border/30">
                {profilesLoading && (
                  <tr>
                    <td colSpan={5} className="text-center py-10 text-cyber-muted">
                      <RefreshCw className="w-5 h-5 animate-spin inline" />
                    </td>
                  </tr>
                )}
                {!profilesLoading && !profilesData?.items.length && (
                  <tr>
                    <td colSpan={5} className="text-center py-10 text-cyber-muted text-sm">
                      No user profiles yet
                    </td>
                  </tr>
                )}
                {profilesData?.items.map((profile) => (
                  <tr key={profile.id} className="hover:bg-cyber-border/10">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-cyber-accent/10 border border-cyber-accent/20 flex items-center justify-center">
                          <User className="w-3.5 h-3.5 text-cyber-accent" />
                        </div>
                        <span className="font-mono text-cyber-text">{profile.username}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(profile.known_source_ips ?? []).slice(0, 3).map((ip) => (
                          <span key={ip} className="text-xs font-mono text-cyber-muted bg-cyber-border/20 px-1.5 py-0.5 rounded">
                            {ip}
                          </span>
                        ))}
                        {(profile.known_source_ips ?? []).length > 3 && (
                          <span className="text-xs text-cyber-muted">
                            +{(profile.known_source_ips ?? []).length - 3}
                          </span>
                        )}
                        {!(profile.known_source_ips ?? []).length && (
                          <span className="text-xs text-cyber-muted/50 italic">None</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-cyber-text font-mono">{profile.event_count_30d.toLocaleString()}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-0.5">
                        {Array.from({ length: 24 }, (_, h) => (
                          <div
                            key={h}
                            className={`w-1 h-3 rounded-sm ${
                              (profile.typical_hours ?? []).includes(h)
                                ? 'bg-cyber-accent'
                                : 'bg-cyber-border/40'
                            }`}
                            title={`${h}:00`}
                          />
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-cyber-muted">
                      {profile.last_activity ? formatDate(profile.last_activity) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {profilesData && profilesData.pages > 1 && (
            <div className="flex items-center justify-between px-4 py-2 border-t border-cyber-border">
              <button
                onClick={() => setProfilePage((p) => Math.max(1, p - 1))}
                disabled={profilePage === 1}
                className="text-xs text-cyber-muted disabled:opacity-40 hover:text-cyber-text"
              >Prev</button>
              <span className="text-xs text-cyber-muted">{profilePage} / {profilesData.pages}</span>
              <button
                onClick={() => setProfilePage((p) => Math.min(profilesData.pages, p + 1))}
                disabled={profilePage === profilesData.pages}
                className="text-xs text-cyber-muted disabled:opacity-40 hover:text-cyber-text"
              >Next</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default UEBA;
