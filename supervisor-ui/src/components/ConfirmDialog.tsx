import { useState, useEffect } from 'react';

/**
 * ConfirmDialog - Modal dialog for confirming irreversible actions.
 */

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  consequences?: string[];
  confirmLabel: string;
  cancelLabel?: string;
  variant?: 'default' | 'warning' | 'danger';
  onConfirm: (reason?: string) => void;
  onCancel: () => void;
  loading?: boolean;
  requireReason?: boolean;
  reasonLabel?: string;
  reasonPlaceholder?: string;
}

const variantStyles = {
  default: {
    confirmBg: '#2563eb',
    confirmHoverBg: '#1d4ed8',
  },
  warning: {
    confirmBg: '#f59e0b',
    confirmHoverBg: '#d97706',
  },
  danger: {
    confirmBg: '#dc2626',
    confirmHoverBg: '#b91c1c',
  },
};

export function ConfirmDialog({
  open,
  title,
  message,
  consequences,
  confirmLabel,
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  onCancel,
  loading = false,
  requireReason = false,
  reasonLabel = 'Reason',
  reasonPlaceholder = 'Enter a reason for this action...',
}: ConfirmDialogProps) {
  const [reason, setReason] = useState('');

  // Reset reason when dialog opens
  useEffect(() => {
    if (open) {
      setReason('');
    }
  }, [open]);

  if (!open) return null;

  const colors = variantStyles[variant];
  const canConfirm = !requireReason || reason.trim().length > 0;

  const handleConfirm = () => {
    onConfirm(requireReason ? reason.trim() : undefined);
  };

  return (
    <div style={styles.overlay} onClick={onCancel}>
      <div
        style={styles.dialog}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
      >
        <h3 id="confirm-dialog-title" style={styles.title}>
          {title}
        </h3>
        <p style={styles.message}>{message}</p>

        {consequences && consequences.length > 0 && (
          <div style={styles.consequences}>
            <p style={styles.consequencesTitle}>This action will:</p>
            <ul style={styles.consequencesList}>
              {consequences.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {requireReason && (
          <div style={styles.reasonContainer}>
            <label style={styles.reasonLabel}>{reasonLabel} (needed)</label>
            <textarea
              style={styles.reasonInput}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={reasonPlaceholder}
              rows={3}
            />
          </div>
        )}

        <div style={styles.actions}>
          <button
            style={styles.cancelButton}
            onClick={onCancel}
            disabled={loading}
          >
            {cancelLabel}
          </button>
          <button
            style={{
              ...styles.confirmButton,
              background: colors.confirmBg,
              ...(canConfirm ? {} : { opacity: 0.5, cursor: 'not-allowed' }),
            }}
            onClick={handleConfirm}
            disabled={loading || !canConfirm}
          >
            {loading ? 'Processing...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  dialog: {
    background: '#fff',
    borderRadius: '12px',
    padding: '24px',
    maxWidth: '420px',
    width: '90%',
    boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
  },
  title: {
    fontSize: '18px',
    fontWeight: 600,
    color: '#111827',
    margin: '0 0 12px 0',
  },
  message: {
    fontSize: '14px',
    color: '#4b5563',
    lineHeight: 1.5,
    margin: '0 0 16px 0',
  },
  consequences: {
    background: '#fef3c7',
    border: '1px solid #fde68a',
    borderRadius: '6px',
    padding: '12px',
    marginBottom: '20px',
  },
  consequencesTitle: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#92400e',
    margin: '0 0 8px 0',
  },
  consequencesList: {
    margin: 0,
    paddingLeft: '18px',
    fontSize: '13px',
    color: '#78350f',
    lineHeight: 1.6,
  },
  actions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
  },
  cancelButton: {
    padding: '10px 16px',
    fontSize: '14px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#374151',
    cursor: 'pointer',
  },
  confirmButton: {
    padding: '10px 16px',
    fontSize: '14px',
    fontWeight: 500,
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
  },
  reasonContainer: {
    marginBottom: '20px',
  },
  reasonLabel: {
    display: 'block',
    fontSize: '13px',
    fontWeight: 500,
    color: '#374151',
    marginBottom: '8px',
  },
  reasonInput: {
    width: '100%',
    padding: '10px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxSizing: 'border-box' as const,
    resize: 'vertical' as const,
  },
};
