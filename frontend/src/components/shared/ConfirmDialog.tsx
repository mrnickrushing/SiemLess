import React from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
}

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  danger = true,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative bg-cyber-card border border-cyber-border rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 animate-fade-in">
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 text-cyber-muted hover:text-cyber-text transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
        <div className="flex items-start gap-4">
          <div
            className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
              danger ? 'bg-red-900/30' : 'bg-yellow-900/30'
            }`}
          >
            <AlertTriangle
              className={`w-5 h-5 ${danger ? 'text-red-400' : 'text-yellow-400'}`}
            />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-cyber-text mb-1">{title}</h3>
            <p className="text-sm text-cyber-muted">{message}</p>
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onCancel} className="cyber-btn-secondary">
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={danger ? 'cyber-btn-danger' : 'cyber-btn-primary'}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
