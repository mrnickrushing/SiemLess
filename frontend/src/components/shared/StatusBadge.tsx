import React from 'react';
import type { AlertStatus } from '../../types';

interface StatusBadgeProps {
  status: AlertStatus;
  size?: 'sm' | 'md' | 'lg';
}

const statusConfig: Record<AlertStatus, { label: string; classes: string; dot: string }> = {
  open: {
    label: 'Open',
    classes: 'bg-red-900/30 text-red-400 border border-red-700/50',
    dot: 'bg-red-400',
  },
  investigating: {
    label: 'Investigating',
    classes: 'bg-orange-900/30 text-orange-400 border border-orange-700/50',
    dot: 'bg-orange-400',
  },
  resolved: {
    label: 'Resolved',
    classes: 'bg-green-900/30 text-green-400 border border-green-700/50',
    dot: 'bg-green-400',
  },
  false_positive: {
    label: 'False Positive',
    classes: 'bg-slate-800/50 text-slate-400 border border-slate-600/50',
    dot: 'bg-slate-400',
  },
};

const sizeClasses = {
  sm: 'text-[10px] px-1.5 py-0.5',
  md: 'text-xs px-2 py-0.5',
  lg: 'text-sm px-2.5 py-1',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const config = statusConfig[status] || statusConfig.open;
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded ${config.classes} ${sizeClasses[size]}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
};

export default StatusBadge;
