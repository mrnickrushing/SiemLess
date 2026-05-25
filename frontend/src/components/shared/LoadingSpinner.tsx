import React from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'w-4 h-4 border-2',
  md: 'w-8 h-8 border-2',
  lg: 'w-12 h-12 border-3',
};

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ size = 'md', className = '' }) => {
  return (
    <div
      className={`rounded-full border-cyber-border border-t-cyber-accent animate-spin ${sizeClasses[size]} ${className}`}
    />
  );
};

export const LoadingSkeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`animate-pulse bg-cyber-border rounded ${className}`} />
);

export const TableSkeleton: React.FC<{ rows?: number; cols?: number }> = ({
  rows = 5,
  cols = 5,
}) => (
  <div className="space-y-2">
    {Array.from({ length: rows }).map((_, rowIdx) => (
      <div key={rowIdx} className="flex gap-4 py-3 px-4">
        {Array.from({ length: cols }).map((_, colIdx) => (
          <LoadingSkeleton
            key={colIdx}
            className={`h-4 ${colIdx === 0 ? 'w-32' : colIdx === cols - 1 ? 'w-24' : 'flex-1'}`}
          />
        ))}
      </div>
    ))}
  </div>
);

export const CardSkeleton: React.FC = () => (
  <div className="bg-cyber-card border border-cyber-border rounded-lg p-6 animate-pulse">
    <div className="flex justify-between items-start mb-4">
      <LoadingSkeleton className="h-4 w-32" />
      <LoadingSkeleton className="h-8 w-8 rounded" />
    </div>
    <LoadingSkeleton className="h-8 w-24 mb-2" />
    <LoadingSkeleton className="h-3 w-48" />
  </div>
);

export default LoadingSpinner;
