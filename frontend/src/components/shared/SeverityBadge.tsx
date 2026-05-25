import React from 'react';
import type { Severity } from '../../types';

interface SeverityBadgeProps {
  severity: Severity;
  size?: 'sm' | 'md' | 'lg';
}

const severityConfig: Record<Severity, { label: string; classes: string }> = {
  critical: {
    label: 'CRITICAL',
    classes: 'bg-red-900/40 text-red-400 border border-red-700/50 shadow-red-900/20',
  },
  high: {
    label: 'HIGH',
    classes: 'bg-orange-900/40 text-orange-400 border border-orange-700/50',
  },
  medium: {
    label: 'MEDIUM',
    classes: 'bg-yellow-900/40 text-yellow-400 border border-yellow-700/50',
  },
  low: {
    label: 'LOW',
    classes: 'bg-blue-900/40 text-blue-400 border border-blue-700/50',
  },
  info: {
    label: 'INFO',
    classes: 'bg-cyan-900/40 text-cyan-400 border border-cyan-700/50',
  },
};

const sizeClasses = {
  sm: 'text-[10px] px-1.5 py-0.5',
  md: 'text-xs px-2 py-0.5',
  lg: 'text-sm px-2.5 py-1',
};

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, size = 'md' }) => {
  const config = severityConfig[severity] || severityConfig.info;
  return (
    <span
      className={`inline-flex items-center font-mono font-semibold rounded ${config.classes} ${sizeClasses[size]}`}
    >
      {config.label}
    </span>
  );
};

export default SeverityBadge;
