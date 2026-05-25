import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Shield, AlertTriangle } from 'lucide-react';
import { getAlerts } from '../api/alerts';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import type { Alert, Severity } from '../types';

// ATT&CK Enterprise tactics (TA IDs) with a curated subset of techniques
const TACTICS: { id: string; name: string; techniques: { id: string; name: string }[] }[] = [
  {
    id: 'TA0001', name: 'Initial Access',
    techniques: [
      { id: 'T1190', name: 'Exploit Public-Facing App' },
      { id: 'T1078', name: 'Valid Accounts' },
      { id: 'T1566', name: 'Phishing' },
      { id: 'T1133', name: 'External Remote Services' },
    ],
  },
  {
    id: 'TA0002', name: 'Execution',
    techniques: [
      { id: 'T1059', name: 'Command and Scripting' },
      { id: 'T1053', name: 'Scheduled Task/Job' },
      { id: 'T1204', name: 'User Execution' },
    ],
  },
  {
    id: 'TA0003', name: 'Persistence',
    techniques: [
      { id: 'T1098', name: 'Account Manipulation' },
      { id: 'T1136', name: 'Create Account' },
      { id: 'T1543', name: 'Create/Modify System Process' },
    ],
  },
  {
    id: 'TA0004', name: 'Privilege Escalation',
    techniques: [
      { id: 'T1548', name: 'Abuse Elevation Control' },
      { id: 'T1548.003', name: 'Sudo / Sudo Caching' },
      { id: 'T1134', name: 'Access Token Manipulation' },
    ],
  },
  {
    id: 'TA0005', name: 'Defense Evasion',
    techniques: [
      { id: 'T1070', name: 'Indicator Removal' },
      { id: 'T1036', name: 'Masquerading' },
      { id: 'T1562', name: 'Impair Defenses' },
    ],
  },
  {
    id: 'TA0006', name: 'Credential Access',
    techniques: [
      { id: 'T1110', name: 'Brute Force' },
      { id: 'T1110.001', name: 'Password Guessing' },
      { id: 'T1003', name: 'OS Credential Dumping' },
      { id: 'T1555', name: 'Credentials from Stores' },
    ],
  },
  {
    id: 'TA0007', name: 'Discovery',
    techniques: [
      { id: 'T1046', name: 'Network Service Scan' },
      { id: 'T1082', name: 'System Info Discovery' },
      { id: 'T1083', name: 'File & Dir Discovery' },
      { id: 'T1018', name: 'Remote System Discovery' },
    ],
  },
  {
    id: 'TA0008', name: 'Lateral Movement',
    techniques: [
      { id: 'T1021', name: 'Remote Services' },
      { id: 'T1550', name: 'Use Alt Auth Material' },
    ],
  },
  {
    id: 'TA0009', name: 'Collection',
    techniques: [
      { id: 'T1005', name: 'Data from Local System' },
      { id: 'T1114', name: 'Email Collection' },
    ],
  },
  {
    id: 'TA0011', name: 'Command & Control',
    techniques: [
      { id: 'T1071', name: 'App Layer Protocol' },
      { id: 'T1095', name: 'Non-App Layer Protocol' },
      { id: 'T1041', name: 'Exfil Over C2 Channel' },
    ],
  },
  {
    id: 'TA0010', name: 'Exfiltration',
    techniques: [
      { id: 'T1048', name: 'Exfil Over Alt Protocol' },
      { id: 'T1567', name: 'Exfil Over Web Service' },
    ],
  },
  {
    id: 'TA0040', name: 'Impact',
    techniques: [
      { id: 'T1485', name: 'Data Destruction' },
      { id: 'T1486', name: 'Data Encrypted for Impact' },
      { id: 'T1498', name: 'Network DoS' },
    ],
  },
];

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'bg-red-600/80 border-red-500 text-white',
  high: 'bg-orange-600/80 border-orange-500 text-white',
  medium: 'bg-yellow-600/80 border-yellow-500 text-white',
  low: 'bg-blue-600/60 border-blue-500 text-white',
  info: 'bg-cyan-600/60 border-cyan-500 text-white',
};

const SEVERITY_DOT: Record<Severity, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
  info: 'bg-cyan-500',
};

type TechniqueHit = { count: number; maxSeverity: Severity; alerts: Alert[] };

const MitreMatrix: React.FC = () => {
  // Fetch all open/investigating alerts with MITRE data (up to 200)
  const { data, isLoading } = useQuery({
    queryKey: ['mitre-alerts'],
    queryFn: () => getAlerts({ page_size: 100, page: 1 }),
    refetchInterval: 60_000,
  });

  const alerts = data?.items ?? [];

  // Build lookup: technique_id -> { count, maxSeverity, alerts }
  const hitMap = useMemo<Map<string, TechniqueHit>>(() => {
    const map = new Map<string, TechniqueHit>();
    for (const alert of alerts) {
      if (!alert.mitre_technique) continue;
      // Normalise: T1110.001 matches T1110 too
      const keys = new Set<string>();
      keys.add(alert.mitre_technique.trim());
      // parent technique (strip sub-technique suffix)
      const parent = alert.mitre_technique.split('.')[0];
      if (parent !== alert.mitre_technique) keys.add(parent);

      for (const key of keys) {
        const existing = map.get(key);
        const sev = (alert.severity ?? 'low') as Severity;
        if (!existing) {
          map.set(key, { count: 1, maxSeverity: sev, alerts: [alert] });
        } else {
          const RANK: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };
          map.set(key, {
            count: existing.count + 1,
            maxSeverity: RANK[sev] > RANK[existing.maxSeverity] ? sev : existing.maxSeverity,
            alerts: [...existing.alerts, alert],
          });
        }
      }
    }
    return map;
  }, [alerts]);

  // Tactic-level stats
  const tacticHits = useMemo(() => {
    return TACTICS.map((tactic) => {
      let count = 0;
      let maxSev: Severity = 'low';
      const RANK: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };
      for (const tech of tactic.techniques) {
        const h = hitMap.get(tech.id);
        if (h) {
          count += h.count;
          if (RANK[h.maxSeverity] > RANK[maxSev]) maxSev = h.maxSeverity;
        }
      }
      return { id: tactic.id, count, maxSev };
    });
  }, [hitMap]);

  const totalHits = alerts.filter((a) => a.mitre_technique).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-cyber-text flex items-center gap-2">
            <Shield className="w-6 h-6 text-cyber-accent" />
            MITRE ATT&amp;CK Matrix
          </h1>
          <p className="text-sm text-cyber-muted mt-1">
            Active alerts mapped to ATT&amp;CK Enterprise tactics and techniques
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-cyber-text tabular-nums">{totalHits}</div>
          <div className="text-xs text-cyber-muted">alerts with technique mapping</div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-cyber-muted flex-wrap">
        <span className="font-medium">Severity:</span>
        {(['critical', 'high', 'medium', 'low'] as Severity[]).map((s) => (
          <span key={s} className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-sm ${SEVERITY_DOT[s]}`} />
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </span>
        ))}
        <span className="text-cyber-muted/50 ml-2">· Cells with alerts are highlighted · Number = alert count</span>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="cyber-card p-3 animate-pulse h-48" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {TACTICS.map((tactic, ti) => {
            const th = tacticHits[ti];
            const tacticActive = th.count > 0;
            return (
              <div
                key={tactic.id}
                className={`cyber-card flex flex-col transition-all duration-200 ${
                  tacticActive ? 'border-cyber-accent/40' : ''
                }`}
              >
                {/* Tactic header */}
                <div
                  className={`px-3 py-2 rounded-t-md border-b border-cyber-border flex items-center justify-between ${
                    tacticActive ? 'bg-cyber-accent/5' : ''
                  }`}
                >
                  <div>
                    <div className="text-[10px] font-mono text-cyber-muted">{tactic.id}</div>
                    <div className="text-xs font-semibold text-cyber-text leading-tight">{tactic.name}</div>
                  </div>
                  {tacticActive && (
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${SEVERITY_COLORS[th.maxSev]}`}
                    >
                      {th.count}
                    </span>
                  )}
                </div>

                {/* Technique cells */}
                <div className="flex flex-col gap-1 p-2 flex-1">
                  {tactic.techniques.map((tech) => {
                    const hit = hitMap.get(tech.id);
                    return (
                      <div
                        key={tech.id}
                        title={hit ? `${hit.count} alert(s) — ${hit.maxSeverity}` : tech.name}
                        className={`px-2 py-1 rounded text-[10px] border transition-all cursor-default select-none ${
                          hit
                            ? `${SEVERITY_COLORS[hit.maxSeverity]} font-semibold`
                            : 'bg-cyber-bg/40 border-cyber-border/30 text-cyber-muted'
                        }`}
                      >
                        <div className="font-mono opacity-70">{tech.id}</div>
                        <div className="leading-tight truncate">{tech.name}</div>
                        {hit && (
                          <div className="flex items-center gap-1 mt-0.5 opacity-90">
                            <AlertTriangle className="w-2.5 h-2.5 flex-shrink-0" />
                            <span>{hit.count} alert{hit.count !== 1 ? 's' : ''}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Recent mapped alerts */}
      {alerts.filter((a) => a.mitre_technique).length > 0 && (
        <div className="cyber-card">
          <div className="px-5 py-3 border-b border-cyber-border">
            <h2 className="text-sm font-semibold text-cyber-text">Recent Mapped Alerts</h2>
          </div>
          <div className="divide-y divide-cyber-border">
            {alerts
              .filter((a) => a.mitre_technique)
              .slice(0, 10)
              .map((alert) => (
                <div key={alert.id} className="px-5 py-3 flex items-center gap-3 text-sm">
                  <SeverityBadge severity={alert.severity} />
                  <span className="flex-1 truncate text-cyber-text">{alert.title}</span>
                  <span className="font-mono text-[11px] text-cyber-muted bg-cyber-bg/60 px-2 py-0.5 rounded">
                    {alert.mitre_technique}
                  </span>
                  {alert.mitre_tactic && (
                    <span className="text-[11px] text-cyber-muted hidden lg:block">{alert.mitre_tactic}</span>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

      {totalHits === 0 && !isLoading && (
        <div className="cyber-card flex flex-col items-center justify-center py-16 text-center">
          <Shield className="w-10 h-10 text-cyber-muted mb-3" />
          <div className="text-cyber-text font-medium">No mapped alerts</div>
          <div className="text-cyber-muted text-sm mt-1">
            Alerts with MITRE ATT&amp;CK technique mappings will appear here.
          </div>
        </div>
      )}
    </div>
  );
};

export default MitreMatrix;
