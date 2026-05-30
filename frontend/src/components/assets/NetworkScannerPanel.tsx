import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, Radar, Server, ShieldAlert } from 'lucide-react';
import { getNetworkScan, getNetworkScans, startNetworkScan } from '../../api/assets';
import type { NetworkScan } from '../../types';

function formatDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function progress(scan: NetworkScan) {
  if (!scan.hosts_total) return 0;
  return Math.round((scan.hosts_scanned / scan.hosts_total) * 100);
}

const STATUS_CLASS: Record<string, string> = {
  queued: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  running: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  completed: 'text-cyber-accent bg-cyber-accent/10 border-cyber-accent/30',
  failed: 'text-red-400 bg-red-400/10 border-red-400/30',
};

const NetworkScannerPanel: React.FC = () => {
  const qc = useQueryClient();
  const [targetCidr, setTargetCidr] = useState('192.168.1.0/24');
  const [ports, setPorts] = useState('22,80,443,445,3389');
  const [selectedScanId, setSelectedScanId] = useState<string | null>(null);

  const { data: scans, isFetching } = useQuery({
    queryKey: ['network-scans'],
    queryFn: () => getNetworkScans({ page_size: 5 }),
    refetchInterval: 5000,
  });

  const { data: selectedScan } = useQuery({
    queryKey: ['network-scan', selectedScanId],
    queryFn: () => getNetworkScan(selectedScanId!),
    enabled: !!selectedScanId,
    refetchInterval: 5000,
  });

  const startMutation = useMutation({
    mutationFn: () => startNetworkScan({ target_cidr: targetCidr.trim(), ports: ports.trim() }),
    onSuccess: (scan) => {
      setSelectedScanId(scan.id);
      qc.invalidateQueries({ queryKey: ['network-scans'] });
      qc.invalidateQueries({ queryKey: ['assets'] });
    },
  });

  return (
    <div className="border-b border-cyber-border p-3 space-y-3 bg-cyber-bg/20">
      <div className="flex items-center gap-2">
        <Radar className="w-4 h-4 text-cyber-accent" />
        <div className="min-w-0 flex-1">
          <h2 className="text-xs font-semibold text-cyber-text uppercase tracking-wider">Network Scanner</h2>
          <p className="text-[11px] text-cyber-muted">Private CIDR discovery only</p>
        </div>
        {isFetching && <RefreshCw className="w-3.5 h-3.5 text-cyber-muted animate-spin" />}
      </div>

      <div className="grid grid-cols-1 gap-2">
        <input
          value={targetCidr}
          onChange={(e) => setTargetCidr(e.target.value)}
          className="cyber-input text-xs font-mono"
          placeholder="192.168.1.0/24"
        />
        <input
          value={ports}
          onChange={(e) => setPorts(e.target.value)}
          className="cyber-input text-xs font-mono"
          placeholder="22,80,443 or 1-1024"
        />
        <button
          onClick={() => startMutation.mutate()}
          disabled={startMutation.isPending || !targetCidr.trim()}
          className="cyber-btn-primary text-xs py-2 flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {startMutation.isPending ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Radar className="w-3.5 h-3.5" />}
          Start Scan
        </button>
        {startMutation.isError && (
          <div className="text-xs text-red-400 bg-red-400/10 border border-red-400/30 rounded p-2">
            {(startMutation.error as Error).message}
          </div>
        )}
      </div>

      <div className="space-y-2">
        {(scans?.items ?? []).map((scan) => (
          <button
            key={scan.id}
            onClick={() => setSelectedScanId(scan.id)}
            className={`w-full text-left rounded border p-2 transition-colors ${
              selectedScanId === scan.id ? 'border-cyber-accent bg-cyber-accent/5' : 'border-cyber-border bg-cyber-card/60 hover:bg-cyber-border/20'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-mono text-cyber-text truncate">{scan.target_cidr}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${STATUS_CLASS[scan.status] ?? 'text-cyber-muted border-cyber-border'}`}>
                {scan.status}
              </span>
            </div>
            <div className="mt-2 h-1.5 bg-cyber-border/50 rounded overflow-hidden">
              <div className="h-full bg-cyber-accent" style={{ width: `${progress(scan)}%` }} />
            </div>
            <div className="flex justify-between text-[11px] text-cyber-muted mt-1">
              <span>{scan.hosts_up} up</span>
              <span>{scan.open_ports} open ports</span>
              <span>{formatDate(scan.created_at)}</span>
            </div>
          </button>
        ))}
      </div>

      {selectedScan && (
        <div className="border border-cyber-border rounded-lg bg-cyber-card/70 p-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-cyber-text">Discovered Hosts</span>
            <span className="text-[11px] text-cyber-muted">{selectedScan.hosts_up} live</span>
          </div>
          <div className="space-y-1 max-h-44 overflow-y-auto">
            {selectedScan.hosts.filter((host) => host.status === 'up').length === 0 && (
              <div className="flex items-center gap-2 text-xs text-cyber-muted py-2">
                <ShieldAlert className="w-3.5 h-3.5" />
                No live hosts found yet.
              </div>
            )}
            {selectedScan.hosts.filter((host) => host.status === 'up').map((host) => (
              <div key={host.id} className="rounded bg-cyber-bg/70 border border-cyber-border/60 p-2">
                <div className="flex items-center gap-2">
                  <Server className="w-3.5 h-3.5 text-cyber-accent" />
                  <span className="text-xs font-mono text-cyber-text">{host.ip_address}</span>
                  {host.hostname && <span className="text-[11px] text-cyber-muted truncate">{host.hostname}</span>}
                </div>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {host.services.map((svc) => (
                    <span key={`${host.id}-${svc.port}`} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyber-border/40 text-cyber-muted">
                      {svc.port}/{svc.service}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default NetworkScannerPanel;
