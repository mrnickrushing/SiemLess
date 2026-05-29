import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Cloud,
  Plus,
  RefreshCw,
  Trash2,
  CheckCircle,
  AlertTriangle,
  Clock,
  X,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  getConnectors,
  createConnector,
  updateConnector,
  deleteConnector,
  pollConnector,
} from '../api/connectors';
import type { ConnectorType } from '../types';

const CONNECTOR_TYPES: { id: ConnectorType; label: string; fields: { key: string; label: string; sensitive?: boolean }[] }[] = [
  {
    id: 'aws_cloudtrail',
    label: 'AWS CloudTrail',
    fields: [
      { key: 'aws_access_key_id', label: 'Access Key ID', sensitive: true },
      { key: 'aws_secret_access_key', label: 'Secret Access Key', sensitive: true },
      { key: 'aws_region', label: 'AWS Region' },
      { key: 's3_bucket', label: 'S3 Bucket' },
      { key: 's3_prefix', label: 'S3 Prefix' },
    ],
  },
  {
    id: 'azure_activity',
    label: 'Azure Activity Log',
    fields: [
      { key: 'tenant_id', label: 'Tenant ID' },
      { key: 'client_id', label: 'Client ID' },
      { key: 'client_secret', label: 'Client Secret', sensitive: true },
      { key: 'subscription_id', label: 'Subscription ID' },
    ],
  },
  {
    id: 'gcp_logging',
    label: 'GCP Cloud Logging',
    fields: [
      { key: 'project_id', label: 'Project ID' },
      { key: 'credentials_json', label: 'Service Account JSON', sensitive: true },
    ],
  },
];

/**
 * Format an ISO 8601 date-time string into a localized short month/day and time.
 *
 * @param iso - The ISO 8601 date-time string to format.
 * @returns A localized date-time string showing short month, numeric day, and two-digit hour and minute (for example, "May 5, 03:30 PM").
 */
function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

const AddConnectorModal: React.FC<{
  onClose: () => void;
  onCreate: (data: {
    name: string;
    connector_type: ConnectorType;
    config: Record<string, unknown>;
    enabled: boolean;
  }) => void;
  loading: boolean;
}> = ({ onClose, onCreate, loading }) => {
  const [name, setName] = useState('');
  const [connType, setConnType] = useState<ConnectorType>('aws_cloudtrail');
  const [configFields, setConfigFields] = useState<Record<string, string>>({});

  const typeInfo = CONNECTOR_TYPES.find((t) => t.id === connType)!;

  const handleSubmit = () => {
    const config: Record<string, unknown> = {};
    typeInfo.fields.forEach((f) => {
      if (configFields[f.key]) config[f.key] = configFields[f.key];
    });
    onCreate({ name, connector_type: connType, config, enabled: true });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="cyber-card w-full max-w-lg mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-cyber-text">Add Cloud Connector</h2>
          <button onClick={onClose} className="text-cyber-muted hover:text-cyber-text">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1">Name</label>
            <input
              className="cyber-input w-full"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Production AWS"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-cyber-muted mb-1">Type</label>
            <select
              className="cyber-input w-full"
              value={connType}
              onChange={(e) => {
                setConnType(e.target.value as ConnectorType);
                setConfigFields({});
              }}
            >
              {CONNECTOR_TYPES.map((t) => (
                <option key={t.id} value={t.id}>{t.label}</option>
              ))}
            </select>
          </div>
          {typeInfo.fields.map((field) => (
            <div key={field.key}>
              <label className="block text-xs font-medium text-cyber-muted mb-1">
                {field.label}
              </label>
              <input
                className="cyber-input w-full font-mono text-sm"
                type={field.sensitive ? 'password' : 'text'}
                value={configFields[field.key] ?? ''}
                onChange={(e) =>
                  setConfigFields((prev) => ({ ...prev, [field.key]: e.target.value }))
                }
                placeholder={field.sensitive ? '••••••••' : field.label}
              />
            </div>
          ))}
        </div>

        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="cyber-btn-secondary flex-1">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim() || loading}
            className="cyber-btn flex-1"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin mx-auto" /> : 'Add Connector'}
          </button>
        </div>
      </div>
    </div>
  );
};

const Connectors: React.FC = () => {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => getConnectors({ page_size: 50 }),
  });

  const createMutation = useMutation({
    mutationFn: createConnector,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connectors'] });
      setShowCreate(false);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateConnector(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connectors'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteConnector,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connectors'] }),
  });

  const pollMutation = useMutation({
    mutationFn: pollConnector,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connectors'] }),
  });

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Cloud className="w-6 h-6 text-cyber-accent" />
          <div>
            <h1 className="text-2xl font-bold text-cyber-text">Cloud Connectors</h1>
            <p className="text-sm text-cyber-muted mt-0.5">
              Ingest logs from AWS, Azure, and GCP
            </p>
          </div>
        </div>
        <button onClick={() => setShowCreate(true)} className="cyber-btn flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Add Connector
        </button>
      </div>

      {/* Connectors List */}
      <div className="cyber-card overflow-hidden">
        {isLoading && (
          <div className="flex items-center justify-center py-12 text-cyber-muted">
            <RefreshCw className="w-5 h-5 animate-spin" />
          </div>
        )}
        {!isLoading && !data?.items.length && (
          <div className="text-center py-12">
            <Cloud className="w-10 h-10 text-cyber-muted/30 mx-auto mb-3" />
            <p className="text-sm text-cyber-muted">No connectors configured</p>
            <p className="text-xs text-cyber-muted/60 mt-1">
              Add a connector to start ingesting cloud logs
            </p>
          </div>
        )}
        <div className="divide-y divide-cyber-border/30">
          {data?.items.map((connector) => {
            const typeInfo = CONNECTOR_TYPES.find((t) => t.id === connector.connector_type);
            const isExpanded = expandedId === connector.id;

            return (
              <div key={connector.id}>
                <div className="px-5 py-4">
                  <div className="flex items-center gap-4">
                    {/* Status indicator */}
                    <div
                      className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                        connector.enabled
                          ? connector.last_error
                            ? 'bg-red-400'
                            : 'bg-cyber-accent animate-pulse-slow'
                          : 'bg-cyber-muted/30'
                      }`}
                    />

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-cyber-text">{connector.name}</p>
                        <span className="text-xs text-cyber-muted bg-cyber-border/30 px-1.5 py-0.5 rounded">
                          {typeInfo?.label ?? connector.connector_type}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 mt-1">
                        {connector.last_polled_at ? (
                          <span className="flex items-center gap-1 text-xs text-cyber-muted">
                            <Clock className="w-3 h-3" />
                            {formatDate(connector.last_polled_at)}
                          </span>
                        ) : (
                          <span className="text-xs text-cyber-muted italic">Never polled</span>
                        )}
                        <span className="text-xs text-cyber-muted">
                          {connector.events_ingested.toLocaleString()} events
                        </span>
                        {connector.last_error && (
                          <span className="flex items-center gap-1 text-xs text-red-400">
                            <AlertTriangle className="w-3 h-3" />
                            Error
                          </span>
                        )}
                        {connector.enabled && !connector.last_error && connector.last_polled_at && (
                          <span className="flex items-center gap-1 text-xs text-cyber-accent">
                            <CheckCircle className="w-3 h-3" />
                            OK
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => pollMutation.mutate(connector.id)}
                        disabled={!connector.enabled || pollMutation.isPending}
                        className="cyber-btn-secondary text-xs px-2.5 py-1.5"
                        title="Poll now"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${pollMutation.isPending ? 'animate-spin' : ''}`} />
                      </button>
                      <button
                        onClick={() =>
                          toggleMutation.mutate({ id: connector.id, enabled: !connector.enabled })
                        }
                        className={`text-xs px-3 py-1.5 rounded border font-medium transition-colors ${
                          connector.enabled
                            ? 'border-cyber-muted/30 text-cyber-muted hover:border-cyber-danger/50 hover:text-cyber-danger'
                            : 'border-cyber-accent/30 text-cyber-accent hover:bg-cyber-accent/10'
                        }`}
                      >
                        {connector.enabled ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        onClick={() =>
                          confirm(`Delete connector "${connector.name}"?`) &&
                          deleteMutation.mutate(connector.id)
                        }
                        className="text-cyber-muted hover:text-cyber-danger p-1.5 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : connector.id)}
                        className="text-cyber-muted hover:text-cyber-text p-1.5 rounded"
                      >
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded error details */}
                {isExpanded && connector.last_error && (
                  <div className="px-5 pb-4 bg-red-400/5 border-t border-cyber-border/30">
                    <p className="text-xs font-medium text-red-400 mb-1">Last Error</p>
                    <pre className="text-xs text-cyber-muted font-mono whitespace-pre-wrap break-all">
                      {connector.last_error}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {showCreate && (
        <AddConnectorModal
          onClose={() => setShowCreate(false)}
          onCreate={(data) => createMutation.mutate(data)}
          loading={createMutation.isPending}
        />
      )}
    </div>
  );
};

export default Connectors;
