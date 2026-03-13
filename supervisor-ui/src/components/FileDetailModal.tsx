import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import type { FileAnnotation, RawDataItem, Sample, StorageRoot, LabRole } from '../types';
import { MeasuredSamplesTable } from './MeasuredSamplesTable';
import { AddMeasuredSamplesModal } from './AddMeasuredSamplesModal';
import { hasPermission } from './PermissionHint';

interface FileDetailModalProps {
  item: RawDataItem;
  samples: Sample[];
  storageRoots: StorageRoot[];
  userRole: LabRole | null;
  onClose: () => void;
}

export function FileDetailModal({
  item,
  samples,
  storageRoots,
  userRole,
  onClose,
}: FileDetailModalProps) {
  const [annotations, setAnnotations] = useState<FileAnnotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  const storageRootName =
    storageRoots.find((r) => r.id === item.storage_root_id)?.name ??
    `Root ${item.storage_root_id}`;

  const primarySample =
    item.sample_id !== null ? samples.find((s) => s.id === item.sample_id) : undefined;

  useEffect(() => {
    let active = true;
    setLoading(true);
    apiClient
      .getFileAnnotations(item.id)
      .then((data) => {
        if (active) {
          setAnnotations(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [item.id]);

  const sampleAnnotations = annotations.filter((a) => a.sample_id !== null);
  const fileAnnotations = annotations.filter((a) => a.sample_id === null);

  const handleAnnotationCreated = (created: FileAnnotation[]) => {
    setAnnotations((prev) => [...prev, ...created]);
    setShowAddModal(false);
  };

  const formatFileSize = (bytes: number | null) => {
    if (bytes === null) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const formatDate = (dateStr: string) => new Date(dateStr).toLocaleString();

  const canEdit = hasPermission(userRole, 'RESEARCHER');

  return (
    <>
      <div style={styles.overlay} onClick={onClose}>
        <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div style={styles.header}>
            <div style={styles.headerText}>
              <span style={styles.filePath}>{item.relative_path}</span>
              <span style={styles.storageRootBadge}>{storageRootName}</span>
            </div>
            <button onClick={onClose} style={styles.closeButton}>&times;</button>
          </div>

          {/* File info strip */}
          <div style={styles.infoStrip}>
            <span>{formatFileSize(item.file_size_bytes)}</span>
            <span style={styles.dot}>·</span>
            <span>{formatDate(item.created_at)}</span>
          </div>

          {loading ? (
            <div style={styles.loading}>Loading…</div>
          ) : (
            <>
              {/* Overview: Measured Samples or Primary Sample */}
              {sampleAnnotations.length > 0 ? (
                <div style={styles.section}>
                  <div style={styles.sectionHeader}>
                    <h3 style={styles.sectionTitle}>
                      Measured samples ({sampleAnnotations.length})
                    </h3>
                    {canEdit && (
                      <button
                        style={styles.addButton}
                        onClick={() => setShowAddModal(true)}
                      >
                        + Add
                      </button>
                    )}
                  </div>
                  <MeasuredSamplesTable annotations={sampleAnnotations} samples={samples} />
                </div>
              ) : (
                <div style={styles.section}>
                  <div style={styles.sectionHeader}>
                    <h3 style={styles.sectionTitle}>Primary sample</h3>
                    {canEdit && (
                      <button
                        style={styles.addButton}
                        onClick={() => setShowAddModal(true)}
                      >
                        + Add measured samples
                      </button>
                    )}
                  </div>
                  {primarySample ? (
                    <div style={styles.primarySample}>
                      <span style={styles.sampleIdText}>
                        {primarySample.sample_identifier}
                      </span>
                    </div>
                  ) : (
                    <p style={styles.muted}>No sample assigned.</p>
                  )}
                </div>
              )}

              {/* Run notes (file-level annotations) */}
              {(sampleAnnotations.length > 0 || fileAnnotations.length > 0) && (
                <div style={styles.section}>
                  <h3 style={styles.sectionTitle}>Run notes</h3>
                  {fileAnnotations.length === 0 ? (
                    <p style={styles.muted}>No run-level notes.</p>
                  ) : (
                    <div style={styles.noteList}>
                      {fileAnnotations.map((ann) => (
                        <div key={ann.id} style={styles.noteRow}>
                          <code style={styles.noteKey}>{ann.key}</code>
                          <span style={styles.noteValue}>
                            {ann.value_text ?? JSON.stringify(ann.value_json)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Footer */}
          <div style={styles.footer}>
            <button onClick={onClose} style={styles.doneButton}>Done</button>
          </div>
        </div>
      </div>

      {showAddModal && (
        <AddMeasuredSamplesModal
          rawDataItemId={item.id}
          samples={samples}
          onClose={() => setShowAddModal(false)}
          onCreated={handleAnnotationCreated}
        />
      )}
    </>
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
    zIndex: 2000,
  },
  modal: {
    background: '#fff',
    borderRadius: '8px',
    width: '90%',
    maxWidth: '720px',
    maxHeight: '80vh',
    overflow: 'auto',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    padding: '16px 20px',
    borderBottom: '1px solid #e5e7eb',
    position: 'sticky',
    top: 0,
    background: '#fff',
    zIndex: 1,
  },
  headerText: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    minWidth: 0,
  },
  filePath: {
    fontFamily: 'monospace',
    fontSize: '14px',
    color: '#111827',
    wordBreak: 'break-all',
  },
  storageRootBadge: {
    fontSize: '12px',
    color: '#2563eb',
    fontWeight: 500,
  },
  closeButton: {
    background: 'none',
    border: 'none',
    fontSize: '28px',
    color: '#6b7280',
    cursor: 'pointer',
    padding: '0 8px',
    lineHeight: 1,
    flexShrink: 0,
  },
  infoStrip: {
    padding: '8px 20px',
    background: '#f9fafb',
    borderBottom: '1px solid #e5e7eb',
    fontSize: '12px',
    color: '#6b7280',
    display: 'flex',
    gap: '4px',
  },
  dot: {
    color: '#d1d5db',
  },
  loading: {
    padding: '40px',
    textAlign: 'center',
    color: '#6b7280',
  },
  section: {
    padding: '16px 20px',
    borderBottom: '1px solid #e5e7eb',
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  sectionTitle: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#374151',
    margin: 0,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  addButton: {
    padding: '4px 10px',
    fontSize: '13px',
    fontWeight: 500,
    background: '#2563eb',
    border: 'none',
    borderRadius: '5px',
    color: '#fff',
    cursor: 'pointer',
  },
  primarySample: {
    padding: '8px 12px',
    background: '#f9fafb',
    borderRadius: '4px',
    border: '1px solid #e5e7eb',
  },
  sampleIdText: {
    fontWeight: 500,
    color: '#2563eb',
  },
  muted: {
    color: '#9ca3af',
    fontStyle: 'italic',
    fontSize: '13px',
    margin: 0,
  },
  noteList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  noteRow: {
    display: 'flex',
    gap: '12px',
    alignItems: 'baseline',
    padding: '6px 10px',
    background: '#f9fafb',
    borderRadius: '4px',
  },
  noteKey: {
    fontFamily: 'monospace',
    background: '#e5e7eb',
    padding: '1px 5px',
    borderRadius: '3px',
    fontSize: '12px',
    whiteSpace: 'nowrap',
  },
  noteValue: {
    fontSize: '13px',
    color: '#374151',
  },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    padding: '12px 20px',
    position: 'sticky',
    bottom: 0,
    background: '#fff',
    borderTop: '1px solid #e5e7eb',
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
