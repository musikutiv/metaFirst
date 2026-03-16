import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { PendingIngest, Project, StorageRoot } from '../types';
import { getFullLocalPath } from '../utils';

interface IngestInboxProps {
  project: Project;
  onSelectIngest: (ingest: PendingIngest) => void;
  storageRoots: StorageRoot[];
  hasActiveRDMP?: boolean;
}

export function IngestInbox({ project, onSelectIngest, storageRoots, hasActiveRDMP = true }: IngestInboxProps) {
  const navigate = useNavigate();
  const [pendingIngests, setPendingIngests] = useState<PendingIngest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPendingIngests = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getPendingIngests(project.id, 'PENDING');
      setPendingIngests(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load pending ingests');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPendingIngests();
    // Refresh every 10 seconds
    const interval = setInterval(loadPendingIngests, 10000);
    return () => clearInterval(interval);
  }, [project.id]);

  const getStorageRoot = (storageRootId: number): StorageRoot | undefined =>
    storageRoots.find(r => r.id === storageRootId);

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

  if (loading && pendingIngests.length === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h2 style={styles.title}>Incoming Files</h2>
        </div>
        <div style={styles.loading}>Loading incoming files...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h2 style={styles.title}>Incoming Files</h2>
          <button onClick={loadPendingIngests} style={styles.refreshButton}>
            Refresh
          </button>
        </div>
        <div style={styles.error}>{error}</div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.title}>
          Incoming Files
          {pendingIngests.length > 0 && (
            <span style={styles.badge}>{pendingIngests.length}</span>
          )}
        </h2>
        <button onClick={loadPendingIngests} style={styles.refreshButton}>
          Refresh
        </button>
      </div>

      {/* Blocking banner when no active RDMP */}
      {!hasActiveRDMP && (
        <div style={styles.blockedBanner}>
          <div style={styles.blockedContent}>
            <span style={styles.blockedIcon}>&#9888;</span>
            <div>
              <p style={styles.blockedTitle}>Add data not available</p>
              <p style={styles.blockedText}>
                Activate an RDMP to add data to this project.
              </p>
            </div>
          </div>
          <button
            style={styles.blockedButton}
            onClick={() => navigate('/rdmps')}
          >
            Go to RDMPs
          </button>
        </div>
      )}

      {pendingIngests.length === 0 ? (
        <div style={styles.empty}>
          <p>No pending files.</p>
          <p style={styles.emptyHint}>
            New files detected by the file watcher will appear here.
          </p>
        </div>
      ) : (
        <div style={styles.list}>
          {pendingIngests.map((ingest) => (
            <div
              key={ingest.id}
              style={{
                ...styles.card,
                ...(hasActiveRDMP ? {} : styles.cardDisabled),
              }}
              onClick={() => hasActiveRDMP && onSelectIngest(ingest)}
            >
              <div style={styles.cardMain}>
                {(() => {
                  const root = getStorageRoot(ingest.storage_root_id);
                  const fullPath = root ? getFullLocalPath(root, ingest.relative_path) : null;
                  return (
                    <>
                      <div style={styles.deviceName}>
                        {root?.name ?? `Root ${ingest.storage_root_id}`}
                      </div>
                      <div style={styles.filePath}>
                        {fullPath ?? ingest.relative_path}
                      </div>
                      {!fullPath && root && (
                        <div style={styles.noPathNote}>(no local path configured)</div>
                      )}
                    </>
                  );
                })()}
                <div style={styles.cardMeta}>
                  <span>{formatFileSize(ingest.file_size_bytes)}</span>
                  <span style={styles.separator}>|</span>
                  <span>{formatDate(ingest.created_at)}</span>
                </div>
                {ingest.inferred_sample_identifier && (
                  <div style={styles.inferred}>
                    Suggested: {ingest.inferred_sample_identifier}
                  </div>
                )}
              </div>
              <div style={styles.cardAction}>
                <span style={styles.arrow}>&#8250;</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    padding: '16px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px',
  },
  title: {
    fontSize: '18px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  badge: {
    background: '#f59e0b',
    color: '#fff',
    fontSize: '12px',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '12px',
  },
  refreshButton: {
    padding: '6px 12px',
    fontSize: '14px',
    background: '#f3f4f6',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    cursor: 'pointer',
    color: '#374151',
  },
  loading: {
    padding: '40px',
    textAlign: 'center',
    color: '#6b7280',
  },
  error: {
    padding: '16px',
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '6px',
    color: '#dc2626',
  },
  empty: {
    padding: '40px',
    textAlign: 'center',
    color: '#6b7280',
  },
  emptyHint: {
    fontSize: '14px',
    marginTop: '8px',
    color: '#9ca3af',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  card: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    background: '#f9fafb',
    border: '1px solid #e5e7eb',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  cardMain: {
    flex: 1,
    minWidth: 0,
  },
  deviceName: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#2563eb',
    marginBottom: '2px',
  },
  filePath: {
    fontSize: '13px',
    fontWeight: 500,
    color: '#111827',
    fontFamily: 'monospace',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  noPathNote: {
    fontSize: '11px',
    color: '#9ca3af',
    fontStyle: 'italic',
    marginTop: '1px',
  },
  cardMeta: {
    fontSize: '12px',
    color: '#6b7280',
    marginTop: '4px',
  },
  separator: {
    margin: '0 6px',
    color: '#d1d5db',
  },
  inferred: {
    fontSize: '12px',
    color: '#059669',
    marginTop: '4px',
    fontStyle: 'italic',
  },
  cardAction: {
    marginLeft: '16px',
  },
  arrow: {
    fontSize: '24px',
    color: '#9ca3af',
  },
  cardDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  blockedBanner: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px',
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    marginBottom: '16px',
  },
  blockedContent: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
  },
  blockedIcon: {
    fontSize: '20px',
    color: '#dc2626',
  },
  blockedTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#991b1b',
    margin: '0 0 4px 0',
  },
  blockedText: {
    fontSize: '13px',
    color: '#b91c1c',
    margin: 0,
  },
  blockedButton: {
    padding: '8px 16px',
    fontSize: '13px',
    fontWeight: 500,
    background: '#dc2626',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
};
