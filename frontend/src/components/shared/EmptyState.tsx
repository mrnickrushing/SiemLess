import React from 'react';
import { InboxIcon } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-16 h-16 rounded-full bg-cyber-border/40 flex items-center justify-center mb-4">
        {icon || <InboxIcon className="w-8 h-8 text-cyber-muted" />}
      </div>
      <h3 className="text-lg font-semibold text-cyber-text mb-2">{title}</h3>
      {description && (
        <p className="text-cyber-muted text-sm max-w-md mb-6">{description}</p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
};

export default EmptyState;
