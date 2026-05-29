import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Shield,
  FileText,
  Download,
  RefreshCw,
  CheckCircle,
  Clock,
  AlertTriangle,
  PlayCircle,
} from 'lucide-react';
import {
  getComplianceReports,
  generateComplianceReport,
  downloadComplianceCSV,
} from '../api/compliance';
import type { ComplianceFramework, ComplianceReport } from '../types';

const FRAMEWORKS: { id: ComplianceFramework; label: string; description: string }[] = [
  { id: 'pci_dss', label: 'PCI DSS', description: 'Payment Card Industry Data Security Standard' },
  { id: 'hipaa', label: 'HIPAA', description: 'Health Insurance Portability and Accountability Act' },
  { id: 'gdpr', label: 'GDPR', description: 'General Data Protection Regulation' },
  { id: 'soc2', label: 'SOC 2', description: 'Service Organization Control 2' },
  { id: 'nist', label: 'NIST CSF', description: 'NIST Cybersecurity Framework' },
];

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  if (status === 'completed') {
    return (
      <span className="flex items-center gap-1 text-xs text-green-400 bg-green-400/10 border border-green-400/30 px-2 py-0.5 rounded-full">
        <CheckCircle className="w-3 h-3" />
        Completed
      </span>
    );
  }
  if (status === 'pending') {
    return (
      <span className="flex items-center gap-1 text-xs text-yellow-400 bg-yellow-400/10 border border-yellow-400/30 px-2 py-0.5 rounded-full">
        <Clock className="w-3 h-3 animate-pulse" />
        Generating...
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-xs text-red-400 bg-red-400/10 border border-red-400/30 px-2 py-0.5 rounded-full">
      <AlertTriangle className="w-3 h-3" />
      Failed
    </span>
  );
};

const SummaryTable: React.FC<{ summary: Record<string, unknown> }> = ({ summary }) => {
  const rows = Object.entries(summary);
  if (!rows.length) return <p className="text-xs text-cyber-muted italic">No summary data.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-cyber-border">
            <th className="text-left text-xs font-medium text-cyber-muted pb-2">Control</th>
            <th className="text-right text-xs font-medium text-cyber-muted pb-2">Result</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-cyber-border/30">
          {rows.map(([key, value]) => (
            <tr key={key}>
              <td className="py-2 text-cyber-text">{key.replace(/_/g, ' ')}</td>
              <td className="py-2 text-right">
                {typeof value === 'boolean' ? (
                  <span className={value ? 'text-green-400' : 'text-red-400'}>
                    {value ? 'Pass' : 'Fail'}
                  </span>
                ) : (
                  <span className="font-mono text-cyber-muted">{String(value)}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const Compliance: React.FC = () => {
  const qc = useQueryClient();
  const [activeFramework, setActiveFramework] = useState<ComplianceFramework>('pci_dss');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());

  const { data: reportsData, isLoading } = useQuery({
    queryKey: ['compliance-reports', activeFramework],
    queryFn: () => getComplianceReports({ framework: activeFramework, page_size: 20 }),
    refetchInterval: pollingIds.size > 0 ? 3000 : false,
  });

  // Stop polling for reports that are no longer pending
  useEffect(() => {
    if (!reportsData) return;
    const pendingIds = new Set(
      reportsData.items.filter((r) => r.status === 'pending').map((r) => r.id)
    );
    setPollingIds((prev) => {
      const next = new Set<string>();
      prev.forEach((id) => {
        if (pendingIds.has(id)) next.add(id);
      });
      return next;
    });
  }, [reportsData]);

  const generateMutation = useMutation({
    mutationFn: () => generateComplianceReport(activeFramework),
    onSuccess: (report) => {
      qc.invalidateQueries({ queryKey: ['compliance-reports', activeFramework] });
      setPollingIds((prev) => new Set(prev).add(report.id));
    },
  });

  const currentFramework = FRAMEWORKS.find((f) => f.id === activeFramework)!;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-cyber-accent" />
          <div>
            <h1 className="text-2xl font-bold text-cyber-text">Compliance</h1>
            <p className="text-sm text-cyber-muted mt-0.5">
              Generate and download compliance reports for security frameworks
            </p>
          </div>
        </div>
      </div>

      {/* Framework Tabs */}
      <div className="flex gap-1 mb-6 p-1 bg-cyber-border/20 rounded-lg">
        {FRAMEWORKS.map((fw) => (
          <button
            key={fw.id}
            onClick={() => setActiveFramework(fw.id)}
            className={`flex-1 py-2 px-3 rounded-md text-xs font-medium transition-colors ${
              activeFramework === fw.id
                ? 'bg-cyber-accent text-black'
                : 'text-cyber-muted hover:text-cyber-text'
            }`}
          >
            {fw.label}
          </button>
        ))}
      </div>

      {/* Framework info + generate button */}
      <div className="cyber-card p-5 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-cyber-text">{currentFramework.label}</h2>
            <p className="text-sm text-cyber-muted mt-1">{currentFramework.description}</p>
          </div>
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="cyber-btn flex items-center gap-2"
          >
            {generateMutation.isPending ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <PlayCircle className="w-4 h-4" />
            )}
            Generate Report
          </button>
        </div>
      </div>

      {/* Reports History */}
      <div className="cyber-card overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-3.5 border-b border-cyber-border">
          <FileText className="w-4 h-4 text-cyber-muted" />
          <h3 className="text-sm font-semibold text-cyber-text uppercase tracking-wider">
            Report History
          </h3>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12 text-cyber-muted">
            <RefreshCw className="w-5 h-5 animate-spin" />
          </div>
        )}

        {!isLoading && !reportsData?.items.length && (
          <div className="text-center py-12">
            <FileText className="w-8 h-8 text-cyber-muted/30 mx-auto mb-2" />
            <p className="text-sm text-cyber-muted">No reports generated yet</p>
            <p className="text-xs text-cyber-muted/60 mt-1">Click "Generate Report" to create one</p>
          </div>
        )}

        <div className="divide-y divide-cyber-border/30">
          {reportsData?.items.map((report) => (
            <div key={report.id}>
              <div
                className="flex items-center gap-4 px-5 py-3.5 hover:bg-cyber-border/10 cursor-pointer"
                onClick={() =>
                  report.status === 'completed' &&
                  setExpandedId(expandedId === report.id ? null : report.id)
                }
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-cyber-text">
                    {FRAMEWORKS.find((f) => f.id === report.framework)?.label ?? report.framework}
                  </p>
                  <p className="text-xs text-cyber-muted mt-0.5">
                    {report.generated_at
                      ? `Generated ${formatDate(report.generated_at)}`
                      : `Created ${formatDate(report.created_at)}`}
                  </p>
                </div>
                <StatusBadge status={report.status} />
                {report.status === 'completed' && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      downloadComplianceCSV(report.id);
                    }}
                    className="cyber-btn-secondary text-xs px-2.5 py-1.5 flex items-center gap-1"
                  >
                    <Download className="w-3.5 h-3.5" />
                    CSV
                  </button>
                )}
              </div>

              {expandedId === report.id && report.summary && (
                <div className="px-5 pb-5">
                  <SummaryTable summary={report.summary} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Compliance;
