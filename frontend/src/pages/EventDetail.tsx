import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, ExternalLink, Server, User, Tag, Shield } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import { getEvent } from '../api/events';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import { LoadingSpinner } from '../components/shared/LoadingSpinner';
import JsonViewer from '../components/shared/JsonViewer';
import type { SecurityEvent } from '../types';

interface EventDetailProps {
  eventId: string;
  onClose: () => void;
}

const FieldRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-4 py-2.5 border-b border-cyber-border/40 last:border-0">
    <span className="text-xs font-medium text-cyber-muted uppercase tracking-wider sm:w-40 flex-shrink-0">
      {label}
    </span>
    <span className="text-sm text-cyber-text font-mono flex-1 break-all">{value}</span>
  </div>
);

const EventDetailPanel: React.FC<EventDetailProps> = ({ eventId, onClose }) => {
  const navigate = useNavigate();

  const { data: event, isLoading, isError, error } = useQuery({
    queryKey: ['event', eventId],
    queryFn: () => getEvent(eventId),
    enabled: !!eventId,
  });

  const formatTs = (ts: string | null) => {
    if (!ts) return '—';
    try {
      return format(parseISO(ts), 'yyyy-MM-dd HH:mm:ss.SSS');
    } catch {
      return ts;
    }
  };

  const handleSearchIP = (ip: string) => {
    navigate(`/search?q=${encodeURIComponent(`source_ip:${ip}`)}`);
    onClose();
  };

  const handleSearchUser = (user: string) => {
    navigate(`/search?q=${encodeURIComponent(`username:${user}`)}`);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="w-full max-w-2xl bg-cyber-card border-l border-cyber-border flex flex-col shadow-2xl animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-cyber-border flex-shrink-0">
          <div>
            <h2 className="text-base font-semibold text-cyber-text">Event Detail</h2>
            {event && (
              <p className="text-xs text-cyber-muted font-mono mt-0.5">{event.id}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-20">
              <LoadingSpinner size="lg" />
            </div>
          )}

          {isError && (
            <div className="p-6 text-center">
              <p className="text-cyber-danger">{(error as Error).message}</p>
            </div>
          )}

          {event && <EventDetailContent event={event} onSearchIP={handleSearchIP} onSearchUser={handleSearchUser} formatTs={formatTs} />}
        </div>
      </div>
    </div>
  );
};

const EventDetailContent: React.FC<{
  event: SecurityEvent;
  onSearchIP: (ip: string) => void;
  onSearchUser: (user: string) => void;
  formatTs: (ts: string | null) => string;
}> = ({ event, onSearchIP, onSearchUser, formatTs }) => (
  <div className="p-6 space-y-6">
    {/* Severity and meta */}
    <div className="flex items-center gap-3 flex-wrap">
      <SeverityBadge severity={event.severity} size="lg" />
      <span className="text-sm text-cyber-muted font-mono">{event.event_type}</span>
      <span className="text-sm text-cyber-muted">·</span>
      <span className="text-sm text-cyber-muted">{event.category}</span>
      <span className="text-sm text-cyber-muted">·</span>
      <span className="text-sm text-cyber-muted">{event.log_type}</span>
    </div>

    {/* Message */}
    <div>
      <h3 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-2">Message</h3>
      <div className="bg-cyber-bg border border-cyber-border rounded-lg p-3">
        <p className="text-sm text-cyber-text font-mono leading-relaxed break-all">{event.message}</p>
      </div>
    </div>

    {/* Core Fields */}
    <div>
      <h3 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-2 flex items-center gap-2">
        <Server className="w-3.5 h-3.5" />
        Core Fields
      </h3>
      <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg px-4">
        <FieldRow label="Timestamp" value={formatTs(event.timestamp)} />
        <FieldRow label="Ingested At" value={formatTs(event.ingested_at)} />
        <FieldRow
          label="Source IP"
          value={
            event.source_ip ? (
              <button
                onClick={() => onSearchIP(event.source_ip!)}
                className="text-cyber-accent hover:underline inline-flex items-center gap-1"
              >
                {event.source_ip}
                <ExternalLink className="w-3 h-3" />
              </button>
            ) : '—'
          }
        />
        <FieldRow label="Source Port" value={event.source_port ?? '—'} />
        <FieldRow
          label="Destination IP"
          value={
            event.destination_ip ? (
              <button
                onClick={() => onSearchIP(event.destination_ip!)}
                className="text-cyber-accent hover:underline inline-flex items-center gap-1"
              >
                {event.destination_ip}
                <ExternalLink className="w-3 h-3" />
              </button>
            ) : '—'
          }
        />
        <FieldRow label="Dest Port" value={event.destination_port ?? '—'} />
        <FieldRow label="Hostname" value={event.hostname ?? '—'} />
        <FieldRow
          label="Username"
          value={
            event.username ? (
              <button
                onClick={() => onSearchUser(event.username!)}
                className="text-blue-400 hover:underline inline-flex items-center gap-1"
              >
                <User className="w-3 h-3" />
                {event.username}
                <ExternalLink className="w-3 h-3" />
              </button>
            ) : '—'
          }
        />
      </div>
    </div>

    {/* MITRE */}
    {(event.mitre_tactic || event.mitre_technique) && (
      <div>
        <h3 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-2 flex items-center gap-2">
          <Shield className="w-3.5 h-3.5" />
          MITRE ATT&CK
        </h3>
        <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg px-4">
          {event.mitre_tactic && <FieldRow label="Tactic" value={event.mitre_tactic} />}
          {event.mitre_technique && <FieldRow label="Technique" value={event.mitre_technique} />}
        </div>
      </div>
    )}

    {/* Tags */}
    {event.tags.length > 0 && (
      <div>
        <h3 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-2 flex items-center gap-2">
          <Tag className="w-3.5 h-3.5" />
          Tags
        </h3>
        <div className="flex flex-wrap gap-2">
          {event.tags.map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-1 bg-cyber-border/40 text-cyber-muted border border-cyber-border/50 rounded font-mono"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
    )}

    {/* Parsed Fields */}
    {event.parsed_fields && Object.keys(event.parsed_fields).length > 0 && (
      <div>
        <h3 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-2">
          Parsed Fields
        </h3>
        <JsonViewer data={event.parsed_fields} maxHeight="300px" />
      </div>
    )}

    {/* Raw Log */}
    {event.raw_log && (
      <div>
        <h3 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-2">
          Raw Log
        </h3>
        <div className="bg-cyber-bg border border-cyber-border rounded-lg p-3 max-h-48 overflow-auto">
          <pre className="text-xs text-cyber-muted font-mono whitespace-pre-wrap break-all leading-relaxed">
            {event.raw_log}
          </pre>
        </div>
      </div>
    )}

    {/* Rule & Alert Links */}
    {(event.rule_id || event.alert_id) && (
      <div>
        <h3 className="text-xs font-medium text-cyber-muted uppercase tracking-wider mb-2">
          References
        </h3>
        <div className="bg-cyber-bg/50 border border-cyber-border/50 rounded-lg px-4">
          {event.rule_id && <FieldRow label="Rule ID" value={event.rule_id} />}
          {event.alert_id && <FieldRow label="Alert ID" value={event.alert_id} />}
        </div>
      </div>
    )}
  </div>
);

export default EventDetailPanel;
