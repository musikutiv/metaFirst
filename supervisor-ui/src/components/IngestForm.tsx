import { useState, useMemo } from 'react';
import { apiClient } from '../api/client';
import type { PendingIngest, RDMPField, Sample, StorageRoot, RDMPVersion, FileAnnotationCreate, RDMPRunField } from '../types';

interface IngestFormProps {
  ingest: PendingIngest;
  fields: RDMPField[];
  samples: Sample[];
  storageRoots: StorageRoot[];
  activeRdmpVersion?: RDMPVersion | null;
  onComplete: (rawDataItemId?: number) => void;
  onCancel: () => void;
}

export function IngestForm({
  ingest,
  fields,
  samples,
  storageRoots,
  activeRdmpVersion,
  onComplete,
  onCancel,
}: IngestFormProps) {
  // Use detected sample ID if available, fall back to inferred
  const initialIdentifier = ingest.detected_sample_id || ingest.inferred_sample_identifier || '';
  const hasDetectedId = !!ingest.detected_sample_id;

  // Derive multi-sample config from the active RDMP
  const ingestConfig = activeRdmpVersion?.content?.ingest as { measured_samples_mode?: string; multi?: { annotation_key?: string; index_fields?: string[]; run_fields?: RDMPRunField[] } } | undefined;
  const isMultiMode = ingestConfig?.measured_samples_mode === 'multi';
  const multiConfig = ingestConfig?.multi;
  const indexFields = multiConfig?.index_fields ?? [];
  const runFields = multiConfig?.run_fields ?? [];

  const [sampleOption, setSampleOption] = useState<'existing' | 'new'>(
    initialIdentifier ? 'new' : 'existing'
  );
  const [selectedSampleId, setSelectedSampleId] = useState<number | null>(null);
  const [newSampleIdentifier, setNewSampleIdentifier] = useState(initialIdentifier);
  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>({});
  // Multi-sample state
  const [runFieldValues, setRunFieldValues] = useState<Record<string, string>>({});
  const [measuredRows, setMeasuredRows] = useState<Array<{ sampleId: number | null; index: Record<string, string> }>>([
    { sampleId: null, index: {} },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const storageRoot = storageRoots.find(r => r.id === ingest.storage_root_id);

  const requiredFields = useMemo(
    () => fields.filter(f => f.required),
    [fields]
  );

  const formatFileSize = (bytes: number | null) => {
    if (bytes === null) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const handleFieldChange = (key: string, value: unknown) => {
    setFieldValues(prev => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      if (isMultiMode) {
        if (measuredRows.length === 0) {
          setError('Add at least one measured sample row.');
          setSubmitting(false);
          return;
        }
        for (let i = 0; i < measuredRows.length; i++) {
          const row = measuredRows[i];
          if (!row.sampleId) {
            setError(`Row ${i + 1}: select a sample.`);
            setSubmitting(false);
            return;
          }
          for (const f of indexFields) {
            if (!row.index[f]?.trim()) {
              setError(`Row ${i + 1}: "${f}" is required.`);
              setSubmitting(false);
              return;
            }
          }
        }

        const runAnnotations: FileAnnotationCreate[] = Object.entries(runFieldValues)
          .filter(([, v]) => v.trim() !== '')
          .map(([key, value]) => ({ key, sample_id: null, value_text: value }));

        const measuredSamples: FileAnnotationCreate[] = measuredRows.map(row => ({
          key: multiConfig?.annotation_key ?? 'observation',
          sample_id: row.sampleId,
          index: row.index,
        }));

        const result = await apiClient.finalizePendingIngest(ingest.id, {
          run_annotations: runAnnotations.length > 0 ? runAnnotations : undefined,
          measured_samples: measuredSamples,
        });
        onComplete(result.id);
      } else {
        let finalizeData: { sample_id?: number; sample_identifier?: string; field_values?: Record<string, unknown> } = {};

        if (sampleOption === 'existing' && selectedSampleId) {
          finalizeData.sample_id = selectedSampleId;
        } else if (sampleOption === 'new' && newSampleIdentifier.trim()) {
          finalizeData.sample_identifier = newSampleIdentifier.trim();
        }

        const filledFields = Object.entries(fieldValues).filter(([, v]) => v !== '' && v !== null);
        if (filledFields.length > 0) {
          finalizeData.field_values = Object.fromEntries(filledFields);
        }

        await apiClient.finalizePendingIngest(ingest.id, finalizeData);
        onComplete();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to finalize ingest');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelIngest = async () => {
    if (!confirm('Cancel this pending ingest? The file will still exist but will no longer appear in the inbox.')) {
      return;
    }

    try {
      setSubmitting(true);
      await apiClient.cancelPendingIngest(ingest.id);
      onCancel();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to cancel ingest');
      setSubmitting(false);
    }
  };

  const handleRunFieldChange = (key: string, value: string) => {
    setRunFieldValues(prev => ({ ...prev, [key]: value }));
  };

  const handleMeasuredRowSample = (rowIdx: number, sampleId: number | null) => {
    setMeasuredRows(prev => prev.map((r, i) => i === rowIdx ? { ...r, sampleId } : r));
  };

  const handleMeasuredRowIndex = (rowIdx: number, field: string, value: string) => {
    setMeasuredRows(prev => prev.map((r, i) =>
      i === rowIdx ? { ...r, index: { ...r.index, [field]: value } } : r
    ));
  };

  const addMeasuredRow = () => {
    setMeasuredRows(prev => [...prev, { sampleId: null, index: {} }]);
  };

  const removeMeasuredRow = (rowIdx: number) => {
    setMeasuredRows(prev => prev.filter((_, i) => i !== rowIdx));
  };

  const renderRunFieldInput = (field: RDMPRunField) => {
    const value = runFieldValues[field.key] ?? '';
    if (field.type === 'date') {
      return (
        <input
          type="date"
          style={styles.input}
          value={value}
          onChange={(e) => handleRunFieldChange(field.key, e.target.value)}
        />
      );
    }
    if (field.type === 'text') {
      return (
        <textarea
          style={{ ...styles.input, height: '64px', resize: 'vertical' }}
          value={value}
          onChange={(e) => handleRunFieldChange(field.key, e.target.value)}
        />
      );
    }
    return (
      <input
        type="text"
        style={styles.input}
        value={value}
        onChange={(e) => handleRunFieldChange(field.key, e.target.value)}
      />
    );
  };

  const renderFieldInput = (field: RDMPField) => {
    const value = fieldValues[field.key] ?? '';

    if (field.allowed_values && field.allowed_values.length > 0) {
      return (
        <select
          style={styles.input}
          value={value as string}
          onChange={(e) => handleFieldChange(field.key, e.target.value)}
        >
          <option value="">-- Select --</option>
          {field.allowed_values.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      );
    }

    if (field.type === 'number') {
      return (
        <input
          type="number"
          style={styles.input}
          value={value as string}
          onChange={(e) => handleFieldChange(field.key, e.target.value ? Number(e.target.value) : '')}
        />
      );
    }

    if (field.type === 'date') {
      return (
        <input
          type="date"
          style={styles.input}
          value={value as string}
          onChange={(e) => handleFieldChange(field.key, e.target.value)}
        />
      );
    }

    return (
      <input
        type="text"
        style={styles.input}
        value={value as string}
        onChange={(e) => handleFieldChange(field.key, e.target.value)}
      />
    );
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.title}>Complete Ingest</h2>
        <button onClick={onCancel} style={styles.closeButton}>
          &times;
        </button>
      </div>

      {/* File Info Section */}
      <div style={styles.fileInfo}>
        <div style={styles.fileInfoRow}>
          <span style={styles.fileInfoLabel}>File:</span>
          <span style={styles.filePath}>{ingest.relative_path}</span>
        </div>
        <div style={styles.fileInfoRow}>
          <span style={styles.fileInfoLabel}>Storage Root:</span>
          <span>{storageRoot?.name || `ID ${ingest.storage_root_id}`}</span>
        </div>
        <div style={styles.fileInfoRow}>
          <span style={styles.fileInfoLabel}>Size:</span>
          <span>{formatFileSize(ingest.file_size_bytes)}</span>
        </div>
        {ingest.file_hash_sha256 && (
          <div style={styles.fileInfoRow}>
            <span style={styles.fileInfoLabel}>SHA256:</span>
            <span style={styles.hash}>{ingest.file_hash_sha256.substring(0, 16)}...</span>
          </div>
        )}
      </div>

      {/* Sample ID Detection Panel — shown only in single-sample mode */}
      {!isMultiMode && (
        <div style={styles.detectionPanel}>
          <h4 style={styles.detectionTitle}>Detected Identifiers</h4>
          <div style={styles.detectionContent}>
            <div style={styles.detectionRow}>
              <span style={styles.detectionLabel}>Detected Sample ID:</span>
              <span style={hasDetectedId ? styles.detectedId : styles.noDetection}>
                {ingest.detected_sample_id || 'None'}
              </span>
            </div>
            <div style={styles.detectionRow}>
              <span style={styles.detectionLabel}>Rule:</span>
              <span style={styles.detectionValue}>
                {ingest.detection_info?.configured
                  ? `Filename regex: ${ingest.detection_info.regex || '(not set)'}`
                  : 'No rule configured'}
              </span>
            </div>
            {ingest.detection_info?.configured && (
              <div style={styles.detectionRow}>
                <span style={styles.detectionLabel}>Example:</span>
                <span style={styles.detectionExample}>
                  {ingest.detection_info.example_filename}
                  {' → '}
                  {ingest.detection_info.example_result || 'no match'}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {isMultiMode ? (
          <>
            {/* Run details */}
            {runFields.length > 0 && (
              <div style={styles.section}>
                <h3 style={styles.sectionTitle}>Run details</h3>
                {runFields.map((field) => (
                  <div key={field.key} style={styles.fieldGroup}>
                    <label style={styles.fieldLabel}>{field.label}</label>
                    {renderRunFieldInput(field)}
                  </div>
                ))}
              </div>
            )}

            {/* Measured samples grid */}
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Measured samples</h3>
              <p style={styles.hint}>Add a row for each sample measured in this run.</p>

              <div style={{ overflowX: 'auto' }}>
                <table style={styles.grid}>
                  <thead>
                    <tr>
                      <th style={styles.gridTh}>Sample</th>
                      {indexFields.map(f => (
                        <th key={f} style={styles.gridTh}>{f}</th>
                      ))}
                      <th style={styles.gridTh}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {measuredRows.map((row, idx) => (
                      <tr key={idx}>
                        <td style={styles.gridTd}>
                          <select
                            style={styles.gridInput}
                            value={row.sampleId ?? ''}
                            onChange={(e) => handleMeasuredRowSample(idx, e.target.value ? Number(e.target.value) : null)}
                          >
                            <option value="">-- select --</option>
                            {samples.map(s => (
                              <option key={s.id} value={s.id}>{s.sample_identifier}</option>
                            ))}
                          </select>
                        </td>
                        {indexFields.map(f => (
                          <td key={f} style={styles.gridTd}>
                            <input
                              type="text"
                              style={styles.gridInput}
                              value={row.index[f] ?? ''}
                              onChange={(e) => handleMeasuredRowIndex(idx, f, e.target.value)}
                            />
                          </td>
                        ))}
                        <td style={styles.gridTd}>
                          <button
                            type="button"
                            onClick={() => removeMeasuredRow(idx)}
                            style={styles.removeRowBtn}
                            disabled={measuredRows.length === 1}
                          >
                            &times;
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <button type="button" onClick={addMeasuredRow} style={styles.addRowBtn}>
                + Add row
              </button>
            </div>
          </>
        ) : (
          <>
            {/* Sample Selection */}
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Link to Sample</h3>

              <div style={styles.radioGroup}>
                <label style={styles.radioLabel}>
                  <input
                    type="radio"
                    name="sampleOption"
                    checked={sampleOption === 'existing'}
                    onChange={() => setSampleOption('existing')}
                  />
                  <span>Link to existing sample</span>
                </label>
                <label style={styles.radioLabel}>
                  <input
                    type="radio"
                    name="sampleOption"
                    checked={sampleOption === 'new'}
                    onChange={() => setSampleOption('new')}
                  />
                  <span>Create new sample</span>
                </label>
              </div>

              {sampleOption === 'existing' && (
                <select
                  style={styles.input}
                  value={selectedSampleId || ''}
                  onChange={(e) => setSelectedSampleId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">-- Select a sample (optional) --</option>
                  {samples.map((sample) => (
                    <option key={sample.id} value={sample.id}>
                      {sample.sample_identifier}
                    </option>
                  ))}
                </select>
              )}

              {sampleOption === 'new' && (
                <input
                  type="text"
                  style={styles.input}
                  placeholder="Sample identifier (optional)"
                  value={newSampleIdentifier}
                  onChange={(e) => setNewSampleIdentifier(e.target.value)}
                />
              )}
            </div>

            {/* RDMP Fields */}
            {requiredFields.length > 0 && (sampleOption === 'new' && newSampleIdentifier) && (
              <div style={styles.section}>
                <h3 style={styles.sectionTitle}>Required Metadata Fields</h3>
                <p style={styles.hint}>
                  Fill in required fields for the new sample. You can also complete these later.
                </p>

                {requiredFields.map((field) => (
                  <div key={field.key} style={styles.fieldGroup}>
                    <label style={styles.fieldLabel}>
                      {field.key}
                      {field.required && <span style={styles.required}>*</span>}
                    </label>
                    {field.description && (
                      <div style={styles.fieldDescription}>{field.description}</div>
                    )}
                    {renderFieldInput(field)}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {error && <div style={styles.error}>{error}</div>}

        <div style={styles.actions}>
          <button
            type="button"
            onClick={handleCancelIngest}
            style={styles.cancelButton}
            disabled={submitting}
          >
            Cancel Ingest
          </button>
          <button
            type="submit"
            style={styles.submitButton}
            disabled={submitting}
          >
            {submitting ? 'Processing...' : isMultiMode ? 'Save measurements' : 'Complete Ingest'}
          </button>
        </div>
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    maxWidth: '600px',
    margin: '0 auto',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px',
    borderBottom: '1px solid #e5e7eb',
  },
  title: {
    fontSize: '18px',
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
    padding: '0 8px',
  },
  fileInfo: {
    padding: '16px',
    background: '#f9fafb',
    borderBottom: '1px solid #e5e7eb',
  },
  fileInfoRow: {
    display: 'flex',
    gap: '8px',
    marginBottom: '8px',
    fontSize: '14px',
  },
  fileInfoLabel: {
    fontWeight: 500,
    color: '#6b7280',
    minWidth: '100px',
  },
  filePath: {
    fontFamily: 'monospace',
    color: '#111827',
    wordBreak: 'break-all',
  },
  hash: {
    fontFamily: 'monospace',
    fontSize: '12px',
    color: '#6b7280',
  },
  detectionPanel: {
    padding: '12px 16px',
    background: '#f0fdf4',
    borderBottom: '1px solid #bbf7d0',
  },
  detectionTitle: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#166534',
    margin: '0 0 8px 0',
  },
  detectionContent: {
    fontSize: '13px',
  },
  detectionRow: {
    display: 'flex',
    gap: '8px',
    marginBottom: '4px',
  },
  detectionLabel: {
    color: '#6b7280',
    minWidth: '130px',
  },
  detectionValue: {
    color: '#374151',
    fontFamily: 'monospace',
    fontSize: '12px',
  },
  detectedId: {
    color: '#166534',
    fontWeight: 600,
  },
  noDetection: {
    color: '#9ca3af',
    fontStyle: 'italic',
  },
  detectionExample: {
    color: '#6b7280',
    fontFamily: 'monospace',
    fontSize: '12px',
  },
  section: {
    padding: '16px',
    borderBottom: '1px solid #e5e7eb',
  },
  sectionTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 12px 0',
  },
  radioGroup: {
    display: 'flex',
    gap: '16px',
    marginBottom: '12px',
  },
  radioLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '14px',
    color: '#374151',
    cursor: 'pointer',
  },
  input: {
    width: '100%',
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxSizing: 'border-box',
  },
  hint: {
    fontSize: '13px',
    color: '#6b7280',
    marginBottom: '12px',
  },
  fieldGroup: {
    marginBottom: '16px',
  },
  fieldLabel: {
    display: 'block',
    fontSize: '14px',
    fontWeight: 500,
    color: '#374151',
    marginBottom: '4px',
  },
  fieldDescription: {
    fontSize: '12px',
    color: '#6b7280',
    marginBottom: '6px',
  },
  required: {
    color: '#dc2626',
    marginLeft: '4px',
  },
  error: {
    margin: '16px',
    padding: '12px',
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '6px',
    color: '#dc2626',
    fontSize: '14px',
  },
  actions: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '16px',
    gap: '12px',
  },
  cancelButton: {
    padding: '10px 16px',
    fontSize: '14px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#6b7280',
    cursor: 'pointer',
  },
  submitButton: {
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
  },
  grid: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px',
    marginBottom: '8px',
  },
  gridTh: {
    padding: '6px 8px',
    background: '#f3f4f6',
    border: '1px solid #e5e7eb',
    fontWeight: 600,
    textAlign: 'left' as const,
    color: '#374151',
    whiteSpace: 'nowrap' as const,
  },
  gridTd: {
    padding: '4px',
    border: '1px solid #e5e7eb',
  },
  gridInput: {
    width: '100%',
    padding: '5px 8px',
    fontSize: '13px',
    border: '1px solid #d1d5db',
    borderRadius: '4px',
    boxSizing: 'border-box' as const,
  },
  addRowBtn: {
    padding: '6px 12px',
    fontSize: '13px',
    background: '#f3f4f6',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    cursor: 'pointer',
    color: '#374151',
  },
  removeRowBtn: {
    padding: '2px 8px',
    fontSize: '16px',
    background: 'none',
    border: 'none',
    color: '#9ca3af',
    cursor: 'pointer',
  },
};
