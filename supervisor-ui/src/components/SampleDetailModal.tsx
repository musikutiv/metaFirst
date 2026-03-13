import { useMemo, useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import type { Sample, RawDataItem, RDMPField, StorageRoot, FileAnnotation } from '../types';

interface SampleDetailModalProps {
  sample: Sample;
  rawData: RawDataItem[];
  fields: RDMPField[];
  storageRoots: StorageRoot[];
  onClose: () => void;
  onSelectFile?: (item: RawDataItem) => void;
}

export function SampleDetailModal({
  sample,
  rawData,
  fields,
  storageRoots,
  onClose,
  onSelectFile,
}: SampleDetailModalProps) {
  const [measurements, setMeasurements] = useState<FileAnnotation[]>([]);
  const [measurementsLoading, setMeasurementsLoading] = useState(false);
  // Build storage root name lookup
  const storageRootNames = useMemo(() => {
    const names: Record<number, string> = {};
    for (const root of storageRoots) {
      names[root.id] = root.name;
    }
    return names;
  }, [storageRoots]);

  // Fetch annotations for this sample across ALL project raw data items.
  // This covers both directly-linked files (sample_id FK) and measurement
  // files that reference this sample only via FileAnnotation rows.
  useEffect(() => {
    if (rawData.length === 0) return;
    let active = true;
    setMeasurementsLoading(true);
    Promise.all(
      rawData.map((item) =>
        apiClient.getFileAnnotations(item.id, { sampleId: sample.id }).catch(() => [] as FileAnnotation[])
      )
    ).then((results) => {
      if (active) {
        setMeasurements(results.flat());
        setMeasurementsLoading(false);
      }
    });
    return () => { active = false; };
  }, [sample.id, rawData]);

  const formatFileSize = (bytes: number | null) => {
    if (bytes === null) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>{sample.sample_identifier}</h2>
          <button onClick={onClose} style={styles.closeButton}>
            &times;
          </button>
        </div>

        {/* Completeness Status */}
        <div style={styles.statusSection}>
          {sample.completeness.is_complete ? (
            <div style={styles.completeStatus}>
              Metadata complete ({sample.completeness.total_filled}/{sample.completeness.total_required} required fields)
            </div>
          ) : (
            <div style={styles.incompleteStatus}>
              Missing fields: {sample.completeness.missing_fields.join(', ')}
            </div>
          )}
        </div>

        {/* Metadata Fields */}
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Metadata Fields</h3>
          <div style={styles.fieldGrid}>
            {fields.map((field) => {
              const value = sample.fields[field.key];
              const isFilled = value !== undefined && value !== null && value !== '';

              return (
                <div key={field.key} style={styles.fieldRow}>
                  <span style={styles.fieldLabel}>
                    {field.key}
                    {field.required && <span style={styles.required}>*</span>}
                  </span>
                  <span style={{
                    ...styles.fieldValue,
                    ...(isFilled ? {} : styles.fieldEmpty),
                  }}>
                    {isFilled ? String(value) : '-'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Raw Data Files — direct links + files linked via annotations */}
        {(() => {
          const annotationFileIds = new Set(measurements.map((m) => m.raw_data_item_id));
          const allLinkedFiles = rawData.filter(
            (item) => item.sample_id === sample.id || annotationFileIds.has(item.id)
          );
          const fileCount = measurementsLoading ? '…' : allLinkedFiles.length;
          return (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Linked Files ({fileCount})</h3>
              {measurementsLoading ? (
                <div style={styles.emptyFiles}>Loading…</div>
              ) : allLinkedFiles.length === 0 ? (
                <div style={styles.emptyFiles}>No files linked to this sample.</div>
              ) : (
                <div style={styles.fileList}>
                  {allLinkedFiles.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        ...styles.fileItem,
                        ...(onSelectFile ? styles.fileItemClickable : {}),
                      }}
                      onClick={() => onSelectFile?.(item)}
                    >
                      <div style={styles.filePath}>{item.relative_path}</div>
                      <div style={styles.fileMeta}>
                        <span style={styles.storageRoot}>
                          {storageRootNames[item.storage_root_id] || `Root ${item.storage_root_id}`}
                        </span>
                        <span style={styles.separator}>|</span>
                        <span>{formatFileSize(item.file_size_bytes)}</span>
                        <span style={styles.separator}>|</span>
                        <span>{formatDate(item.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })()}

        {/* Measurements (file annotations linking back to this sample) */}
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>
            Measurements {measurementsLoading ? '…' : `(${measurements.length})`}
          </h3>
          {measurementsLoading ? (
            <div style={styles.emptyFiles}>Loading…</div>
          ) : measurements.length === 0 ? (
            <div style={styles.emptyFiles}>No measurements recorded for this sample.</div>
          ) : (
            <div style={styles.fileList}>
              {measurements.map((ann) => {
                const file = rawData.find((r) => r.id === ann.raw_data_item_id);
                return (
                  <div key={ann.id} style={styles.measurementRow}>
                    <code style={styles.measurementKey}>{ann.key}</code>
                    <span style={styles.measurementValue}>
                      {ann.value_text ?? JSON.stringify(ann.value_json)}
                    </span>
                    {ann.index !== null && ann.index !== undefined && (
                      <span style={styles.measurementIndex}>
                        {JSON.stringify(ann.index)}
                      </span>
                    )}
                    {file && (
                      <span style={styles.measurementFile}>{file.relative_path}</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={styles.footer}>
          <span style={styles.footerText}>
            Created: {formatDate(sample.created_at)}
          </span>
          <button onClick={onClose} style={styles.doneButton}>
            Done
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
  modal: {
    background: '#fff',
    borderRadius: '8px',
    width: '90%',
    maxWidth: '700px',
    maxHeight: '80vh',
    overflow: 'auto',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderBottom: '1px solid #e5e7eb',
    position: 'sticky',
    top: 0,
    background: '#fff',
    zIndex: 1,
  },
  title: {
    fontSize: '20px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  closeButton: {
    background: 'none',
    border: 'none',
    fontSize: '28px',
    color: '#6b7280',
    cursor: 'pointer',
    padding: '0 8px',
    lineHeight: 1,
  },
  statusSection: {
    padding: '12px 20px',
    background: '#f9fafb',
    borderBottom: '1px solid #e5e7eb',
  },
  completeStatus: {
    color: '#059669',
    fontWeight: 500,
    fontSize: '14px',
  },
  incompleteStatus: {
    color: '#dc2626',
    fontSize: '14px',
  },
  section: {
    padding: '20px',
    borderBottom: '1px solid #e5e7eb',
  },
  sectionTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 12px 0',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  fieldGrid: {
    display: 'grid',
    gap: '8px',
  },
  fieldRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 12px',
    background: '#f9fafb',
    borderRadius: '4px',
  },
  fieldLabel: {
    fontSize: '14px',
    color: '#374151',
    fontWeight: 500,
  },
  required: {
    color: '#dc2626',
    marginLeft: '4px',
  },
  fieldValue: {
    fontSize: '14px',
    color: '#111827',
  },
  fieldEmpty: {
    color: '#9ca3af',
    fontStyle: 'italic',
  },
  emptyFiles: {
    padding: '20px',
    textAlign: 'center',
    color: '#6b7280',
    fontStyle: 'italic',
  },
  fileList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  fileItem: {
    padding: '10px 12px',
    background: '#f9fafb',
    borderRadius: '4px',
    border: '1px solid #e5e7eb',
  },
  filePath: {
    fontSize: '13px',
    fontFamily: 'monospace',
    color: '#111827',
    wordBreak: 'break-all',
  },
  fileMeta: {
    fontSize: '12px',
    color: '#6b7280',
    marginTop: '4px',
  },
  storageRoot: {
    color: '#2563eb',
    fontWeight: 500,
  },
  separator: {
    margin: '0 6px',
    color: '#d1d5db',
  },
  fileItemClickable: {
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  measurementRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '6px 10px',
    background: '#f9fafb',
    borderRadius: '4px',
    border: '1px solid #e5e7eb',
    flexWrap: 'wrap' as const,
  },
  measurementKey: {
    fontFamily: 'monospace',
    background: '#e5e7eb',
    padding: '1px 5px',
    borderRadius: '3px',
    fontSize: '12px',
    whiteSpace: 'nowrap' as const,
  },
  measurementValue: {
    fontSize: '13px',
    color: '#374151',
  },
  measurementIndex: {
    fontFamily: 'monospace',
    fontSize: '11px',
    color: '#6b7280',
  },
  measurementFile: {
    fontSize: '11px',
    color: '#9ca3af',
    fontStyle: 'italic',
    marginLeft: 'auto',
    maxWidth: '200px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderTop: '1px solid #e5e7eb',
    position: 'sticky',
    bottom: 0,
    background: '#fff',
  },
  footerText: {
    fontSize: '12px',
    color: '#6b7280',
  },
  doneButton: {
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
