import { useState } from 'react';
import { apiClient } from '../api/client';
import type { FileAnnotation, Sample } from '../types';

interface AddMeasuredSamplesModalProps {
  rawDataItemId: number;
  samples: Sample[];
  onClose: () => void;
  onCreated: (annotations: FileAnnotation[]) => void;
}

export function AddMeasuredSamplesModal({
  rawDataItemId,
  samples,
  onClose,
  onCreated,
}: AddMeasuredSamplesModalProps) {
  const [sampleId, setSampleId] = useState<string>('');
  const [key, setKey] = useState('');
  const [valueText, setValueText] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!sampleId) {
      setError('Please select a sample.');
      return;
    }
    if (!key.trim()) {
      setError('Key is required.');
      return;
    }
    if (!valueText.trim()) {
      setError('Value is required.');
      return;
    }

    setSaving(true);
    try {
      const created = await apiClient.createFileAnnotations(rawDataItemId, [
        {
          key: key.trim(),
          sample_id: Number(sampleId),
          value_text: valueText.trim(),
        },
      ]);
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save annotation.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h3 style={styles.title}>Add measured sample</h3>
          <button onClick={onClose} style={styles.closeButton}>&times;</button>
        </div>

        <form onSubmit={handleSubmit} style={styles.body}>
          {error && <div style={styles.error}>{error}</div>}

          <label style={styles.label}>
            Sample
            <select
              value={sampleId}
              onChange={(e) => setSampleId(e.target.value)}
              style={styles.input}
              required
            >
              <option value="">— select —</option>
              {samples.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.sample_identifier}
                </option>
              ))}
            </select>
          </label>

          <label style={styles.label}>
            Key
            <input
              type="text"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="e.g. lane, channel, condition"
              style={styles.input}
              required
            />
          </label>

          <label style={styles.label}>
            Value
            <input
              type="text"
              value={valueText}
              onChange={(e) => setValueText(e.target.value)}
              placeholder="e.g. treated, lane 2"
              style={styles.input}
              required
            />
          </label>

          <div style={styles.footer}>
            <button type="button" onClick={onClose} style={styles.cancelButton}>
              Cancel
            </button>
            <button type="submit" style={styles.submitButton} disabled={saving}>
              {saving ? 'Saving…' : 'Add'}
            </button>
          </div>
        </form>
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
    zIndex: 2100,
  },
  modal: {
    background: '#fff',
    borderRadius: '8px',
    width: '90%',
    maxWidth: '440px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderBottom: '1px solid #e5e7eb',
  },
  title: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  closeButton: {
    background: 'none',
    border: 'none',
    fontSize: '24px',
    color: '#6b7280',
    cursor: 'pointer',
    lineHeight: 1,
    padding: '0 4px',
  },
  body: {
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
  },
  label: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    fontSize: '13px',
    fontWeight: 500,
    color: '#374151',
  },
  input: {
    padding: '8px 10px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#111827',
    background: '#fff',
  },
  error: {
    padding: '8px 12px',
    background: '#fee2e2',
    color: '#dc2626',
    borderRadius: '4px',
    fontSize: '13px',
  },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '10px',
    marginTop: '6px',
  },
  cancelButton: {
    padding: '8px 16px',
    fontSize: '14px',
    background: 'none',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#374151',
    cursor: 'pointer',
  },
  submitButton: {
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
  },
};
