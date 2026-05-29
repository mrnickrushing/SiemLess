import React from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  ExternalLink,
  Server,
  User,
  Tag,
  Shield,
  Copy,
  Check,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { getEvent } from '../api/events';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import { LoadingSpinner } from '../components/shared/LoadingSpinner';
import JsonViewer from '../components/shared/JsonViewer';
import type { SecurityEvent } from '../types';

const FieldRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4 py-2.5 border-b border-cyber-border/40 last:border-0">
    <span className="text-xs font-medium text-cyber-muted uppercase tracking-wider sm:w-44 flex-shrink-0">
      {label}
    </span>
    <span className="text-sm text-cyber-text font-mono flex-1 break-all">{value}</span>
  </div>
);

const CopyButton: React.FC<{ value: string }> = ({ value }) => {
  const [copied, setCopied] = React.useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <button
      onClick={handleCopy}
      className="ml-2 p-1 rounded text-cyber-muted hover:text-cyber-accent transition-colors"
      title="Copy to clipboard"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-cyber-accent" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
};

const EventDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: event, isLoading, isError, error } = useQuery({
    queryKey: ['event', id],
    queryFn: () => getEvent(id!),
    enabled: !!id,
  });

  const formatTs = (ts: string | null) => {
    if (!ts) return '—';
    try {
      return format(parseISO(ts), 'yyyy-MM-dd HH:mm:ss.SSS \'UTC\'');
    } catch {
      return ts;
    }
  };

  const handleSearchIP = (ip: string) => {
    navigate(`/search?q=${encodeURIComponent(`source_ip:${ip}`)}`);
  };

  const handleSearchUser = (user: string) => {
    navigate(`/search?q=${encodeURIComponent(`username:${user}`)}`);
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-6">
        <Link
          to="/events"
          className="flex items-center gap-1.5 text-sm text-cyber-muted hover:text-cyber-text transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Events
        </Link>
        <span className="text-cyber-muted/40">/</span>
        <span className="text-sm text-cyber-text font-mono truncate max-w-xs">{id}</span>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-32">
          <LoadingSpinner size="lg" />
        </div>
      )}

      {isError && (
        <div className="cyber-card p-12 text-center">
          <p className="text-cyber-danger text-sm">{(error as Error).message}</p>
          <button onClick={() => navigate('/events')} className="cyber-btn-secondary mt-4 text-sm">
            Back to Events
          </button>
        </div>
      )}

      {event && (
        <div className="space-y-6">
          {/* Header */}
          <div className="cyber-card p-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <div className="flex items-center gap-3 flex-wrap mb-2">
                  <SeverityBadge severity={event.severity} size="lg" />
                  <span className="text-sm font-mono text-cyber-muted">{event.event_type}</span>
                  <span className="text-cyber-muted/40">·</span>
                  <span className="text-sm text-cyber-muted">{event.category}</span>
                  <span className="text-cyber-muted/40">·</span>
                  <span className="text-sm text-cyber-muted">{event.log_type}</span>
                </div>
                <div className="flex items-center gap-2">
                  <p className="text-xs font-mono text-cyber-muted/60">{event.id}</p>
                  <CopyButton value={event.id} />
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-cyber-muted uppercase tracking-wider mb-1">Timestamp</p>
                <p className="text-sm font-mono text-cyber-text">{formatTs(event.timestamp)}</p>
              </div>
            </div>

            {/* Message */}
            <div className="mt-4 bg-cyber-bg border border-cyber-border rounded-lg p-3">
              <p className="text-sm text-cyber-text font-mono leading-relaxed break-all">{event.message}</p>
            </div>
          </div>

          {/* Network & Identity */}
          <div className="cyber-card p-6">
            <h2 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-3 flex items-center gap-2">
              <Server className="w-3.5 h-3.5" />
              Network &amp; Identity
            </h2>
            <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg px-4">
              <FieldRow label="Source IP"
                value={
                  event.source_ip ? (
                    <span className="inline-flex items-center gap-1">
                      <button onClick={() => handleSearchIP(event.source_ip!)} className="text-cyber-accent hover:underline inline-flex items-center gap-1">
                        {event.source_ip}<ExternalLink className="w-3 h-3" />
                      </button>
                      <CopyButton value={event.source_ip} />
                    </span>
                  ) : '—'
                }
              />
              <FieldRow label="Source Port" value={event.source_port ?? '—'} />
              <FieldRow label="Destination IP"
                value={
                  event.destination_ip ? (
                    <span className="inline-flex items-center gap-1">
                      <button onClick={() => handleSearchIP(event.destination_ip!)} className="text-cyber-accent hover:underline inline-flex items-center gap-1">
                        {event.destination_ip}<ExternalLink className="w-3 h-3" />
                      </button>
                      <CopyButton value={event.destination_ip} />
                    </span>
                  ) : '—'
                }
              />
              <FieldRow label="Destination Port" value={event.destination_port ?? '—'} />
              <FieldRow label="Hostname" value={event.hostname ?? '—'} />
              <FieldRow label="Username"
                value={
                  event.username ? (
                    <button onClick={() => handleSearchUser(event.username!)} className="text-blue-400 hover:underline inline-flex items-center gap-1">
                      <User className="w-3 h-3" />{event.username}<ExternalLink className="w-3 h-3" />
                    </button>
                  ) : '—'
                }
              />
              <FieldRow label="Ingested At" value={formatTs(event.ingested_at)} />
            </div>
          </div>

          {/* MITRE */}
          {(event.mitre_tactic || event.mitre_technique) && (
            <div className="cyber-card p-6">
              <h2 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-3 flex items-center gap-2">
                <Shield className="w-3.5 h-3.5" />
                MITRE ATT&CK
              </h2>
              <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg px-4">
                {event.mitre_tactic && <FieldRow label="Tactic" value={event.mitre_tactic} />}
                {event.mitre_technique && <FieldRow label="Technique" value={event.mitre_technique} />}
              </div>
            </div>
          )}

          {/* Tags */}
          {(event.tags ?? []).length > 0 && (
            <div className="cyber-card p-6">
              <h2 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-3 flex items-center gap-2">
                <Tag className="w-3.5 h-3.5" />
                Tags
              </h2>
              <div className="flex flex-wrap gap-2">
                {(event.tags ?? []).map((tag) => (
                  <span key={tag} className="text-xs px-2 py-1 bg-cyber-border/40 text-cyber-muted border border-cyber-border/50 rounded font-mono">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* References */}
          {(event.rule_id || event.alert_id) && (
            <div className="cyber-card p-6">
              <h2 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-3">References</h2>
              <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg px-4">
                {event.rule_id && (
                  <FieldRow label="Rule ID" value={
                    <Link to="/rules" className="text-cyber-accent hover:underline inline-flex items-center gap-1">
                      {event.rule_id}<ExternalLink className="w-3 h-3" />
                    </Link>
                  } />
                )}
                {event.alert_id && (
                  <FieldRow label="Alert ID" value={
                    <Link to="/alerts" className="text-cyber-accent hover:underline inline-flex items-center gap-1">
                      {event.alert_id}<ExternalLink className="w-3 h-3" />
                    </Link>
                  } />
                )}
              </div>
            </div>
          )}

          {/* Parsed Fields */}
          {event.parsed_fields && Object.keys(event.parsed_fields).length > 0 && (
            <div className="cyber-card p-6">
              <h2 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-3">Parsed Fields</h2>
              <JsonViewer data={event.parsed_fields} maxHeight="400px" />
            </div>
          )}

          {/* Raw Log */}
          {event.raw_log && (
            <div className="cyber-card p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-medium text-cyber-muted uppercase tracking-wider">Raw Log</h2>
                <CopyButton value={event.raw_log} />
              </div>
              <div className="bg-cyber-bg border border-cyber-border rounded-lg p-3 max-h-64 overflow-auto">
                <pre className="text-xs text-cyber-muted font-mono whitespace-pre-wrap break-all leading-relaxed">
                  {event.raw_log}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EventDetailPage;
