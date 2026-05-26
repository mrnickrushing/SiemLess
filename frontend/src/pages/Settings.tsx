import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Settings as SettingsIcon,
  Database,
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
} from 'lucide-react';
import { checkBackendHealth } from '../api/stats';

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
  if (typeof row.value === 'boolean') {
    return <StatusPill value={row.value} />;
  }
  if (row.value === null || row.value === undefined || row.value === '') {
    return <span className="text-xs text-cyber-muted/50 italic">Not configured</span>;
  }
  return (
    <span className="text-sm font-mono text-cyber-text">
      {String(row.value)}
      {row.link && (
        <a
          href={row.link}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-2 inline-flex items-center gap-0.5 text-cyber-accent hover:underline"
        >
          <ExternalLink className="w-3 h-3" />
        </a>
      )}
    </span>
  );
};

const Settings: React.FC = () => {
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ['health', refreshKey],
    queryFn: async () => {
      const online = await checkBackendHealth();
      return { online };
    },
  });

  // Fetch system config from the /health and openapi endpoints
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
        {
          key: 'app_name',
          label: 'Application Name',
          description: 'Display name of this SiemLess instance',
          value: appTitle,
        },
        {
          key: 'app_version',
          label: 'Version',
          description: 'Current running version of the API',
          value: appVersion,
        },
        {
          key: 'api_docs',
          label: 'API Documentation',
          description: 'Interactive Swagger docs for all API endpoints',
          value: '/docs',
          link: '/docs',
        },
        {
          key: 'redoc',
          label: 'ReDoc',
          description: 'Alternative API reference documentation',
          value: '/redoc',
          link: '/redoc',
        },
      ],
    },
    {
      title: 'Security',
      icon: <Shield className="w-4 h-4" />,
      rows: [
        {
          key: 'admin_username',
          label: 'Admin Username',
          description: 'Username for the admin account (set via ADMIN_USERNAME env var)',
          value: 'admin',
        },
        {
          key: 'admin_password',
          label: 'Admin Password',
          description: 'Set via ADMIN_PASSWORD environment variable',
          value: true,
          sensitive: true,
        },
        {
          key: 'secret_key',
          label: 'JWT Secret Key',
          description: 'Set via SECRET_KEY environment variable. Use openssl rand -hex 32 to generate.',
          value: true,
          sensitive: true,
        },
        {
          key: 'token_expiry',
          label: 'Session Duration',
          description: 'JWT access token lifetime (ACCESS_TOKEN_EXPIRE_MINUTES)',
          value: '60 minutes',
        },
        {
          key: 'brute_force',
          label: 'Brute-Force Protection',
          description: 'Max 10 failed login attempts per 5 min window before lockout',
          value: true,
        },
        {
          key: 'security_headers',
          label: 'Security Headers',
          description: 'X-Frame-Options, X-XSS-Protection, CSP, Permissions-Policy applied on all responses',
          value: true,
        },
      ],
    },
    {
      title: 'Syslog Ingestion',
      icon: <Wifi className="w-4 h-4" />,
      rows: [
        {
          key: 'syslog_enabled',
          label: 'Syslog Server',
          description: 'UDP/TCP syslog listener (SYSLOG_ENABLED)',
          value: true,
        },
        {
          key: 'syslog_host',
          label: 'Listen Host',
          description: 'Interface the syslog server binds to (SYSLOG_HOST)',
          value: '0.0.0.0',
        },
        {
          key: 'syslog_port',
          label: 'Listen Port',
          description: 'UDP/TCP port for syslog (SYSLOG_PORT)',
          value: 514,
        },
      ],
    },
    {
      title: 'SLA Tracking',
      icon: <Clock className="w-4 h-4" />,
      rows: [
        {
          key: 'sla_critical',
          label: 'Critical SLA',
          description: 'Minutes before a critical-severity open alert is marked SLA breached (SLA_CRITICAL_MINUTES)',
          value: '15 minutes',
        },
        {
          key: 'sla_high',
          label: 'High SLA',
          description: 'Minutes before a high-severity open alert is marked SLA breached (SLA_HIGH_MINUTES)',
          value: '60 minutes',
        },
        {
          key: 'sla_check_interval',
          label: 'Check Interval',
          description: 'How often the SLA checker runs (SLA_CHECK_INTERVAL)',
          value: '300 seconds',
        },
      ],
    },
    {
      title: 'Data Retention',
      icon: <Trash2 className="w-4 h-4" />,
      rows: [
        {
          key: 'retention_days',
          label: 'Event Retention',
          description: 'Security events older than this are automatically purged (EVENT_RETENTION_DAYS). Set to 0 to disable.',
          value: '90 days',
        },
        {
          key: 'retention_interval',
          label: 'Purge Interval',
          description: 'How often the retention purge task runs (RETENTION_CHECK_INTERVAL)',
          value: '86400 seconds (1 day)',
        },
      ],
    },
    {
      title: 'Alerting & Integrations',
      icon: <Bell className="w-4 h-4" />,
      rows: [
        {
          key: 'smtp',
          label: 'SMTP Email Alerts',
          description: 'Configure via SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL',
          value: null,
          sensitive: false,
        },
        {
          key: 'slack',
          label: 'Slack Webhook',
          description: 'Configure via SLACK_WEBHOOK_URL',
          value: null,
          sensitive: false,
        },
        {
          key: 'webhook',
          label: 'Generic Webhook',
          description: 'Configure via ALERT_WEBHOOK_URL',
          value: null,
          sensitive: false,
        },
        {
          key: 'virustotal',
          label: 'VirusTotal API Key',
          description: 'Configure via THREAT_INTEL_VIRUSTOTAL_KEY',
          value: null,
          sensitive: true,
        },
        {
          key: 'abuseipdb',
          label: 'AbuseIPDB API Key',
          description: 'Configure via THREAT_INTEL_ABUSEIPDB_KEY',
          value: null,
          sensitive: true,
        },
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
      <div
        className={`cyber-card p-4 mb-6 flex items-center gap-3 border ${
          health?.online
            ? 'border-cyber-accent/20 bg-cyber-accent/5'
            : 'border-cyber-danger/20 bg-cyber-danger/5'
        }`}
      >
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

      {/* Sections */}
      <div className="space-y-6">
        {sections.map((section) => (
          <div key={section.title} className="cyber-card overflow-hidden">
            <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-cyber-border bg-cyber-bg/30">
              <span className="text-cyber-muted">{section.icon}</span>
              <h2 className="text-sm font-semibold text-cyber-text uppercase tracking-wider">
                {section.title}
              </h2>
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

      {/* Footer */}
      <div className="mt-6 text-center">
        <p className="text-xs text-cyber-muted/50">
          SiemLess {appVersion} · To modify settings, update your environment variables and restart the backend.
        </p>
      </div>
    </div>
  );
};

export default Settings;
