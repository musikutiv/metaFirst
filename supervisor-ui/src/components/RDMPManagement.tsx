import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';
import type { Project, RDMPVersion, LabRole } from '../types';
import { PermissionHint, hasPermission } from './PermissionHint';
import { ConfirmDialog } from './ConfirmDialog';

interface RDMPManagementProps {
  project: Project;
  onRDMPActivated?: (activeRDMP: RDMPVersion) => void;
  userRole?: LabRole | null;
}

export function RDMPManagement({ project, onRDMPActivated, userRole }: RDMPManagementProps) {
  const canActivate = hasPermission(userRole ?? null, 'PI');
  const [rdmps, setRdmps] = useState<RDMPVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Create form state
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('{}');
  const [creating, setCreating] = useState(false);

  // Edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);

  // Activating state
  const [activatingId, setActivatingId] = useState<number | null>(null);

  // Confirmation dialog state
  const [confirmActivate, setConfirmActivate] = useState<RDMPVersion | null>(null);

  // Reset state when project changes to prevent showing stale data
  useEffect(() => {
    setRdmps([]);
    setLoading(true);
    setError(null);
    setShowCreateForm(false);
    setEditingId(null);
  }, [project.id]);

  const loadRDMPs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.listRDMPVersions(project.id);
      setRdmps(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load RDMPs');
    } finally {
      setLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    loadRDMPs();
  }, [loadRDMPs]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setCreating(true);

    try {
      // Validate JSON
      let contentObj: Record<string, unknown>;
      try {
        contentObj = JSON.parse(newContent);
      } catch {
        throw new Error('Invalid JSON in content field');
      }

      await apiClient.createRDMPDraft(project.id, {
        title: newTitle,
        content: contentObj,
      });

      setNewTitle('');
      setNewContent('{}');
      setShowCreateForm(false);
      await loadRDMPs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create RDMP');
    } finally {
      setCreating(false);
    }
  };

  const handleStartEdit = (rdmp: RDMPVersion) => {
    setEditingId(rdmp.id);
    setEditTitle(rdmp.title);
    setEditContent(JSON.stringify(rdmp.content, null, 2));
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditTitle('');
    setEditContent('');
  };

  const handleSaveEdit = async (rdmpId: number) => {
    setError(null);
    setSaving(true);

    try {
      let contentObj: Record<string, unknown>;
      try {
        contentObj = JSON.parse(editContent);
      } catch {
        throw new Error('Invalid JSON in content field');
      }

      await apiClient.updateRDMPDraft(rdmpId, {
        title: editTitle,
        content: contentObj,
      });

      setEditingId(null);
      await loadRDMPs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update RDMP');
    } finally {
      setSaving(false);
    }
  };

  const handleActivateClick = (rdmp: RDMPVersion) => {
    setConfirmActivate(rdmp);
  };

  const handleActivateConfirm = async () => {
    if (!confirmActivate) return;

    setError(null);
    setActivatingId(confirmActivate.id);

    try {
      const activatedRDMP = await apiClient.activateRDMP(confirmActivate.id);
      setConfirmActivate(null);
      await loadRDMPs();
      onRDMPActivated?.(activatedRDMP);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to activate RDMP');
      setConfirmActivate(null);
    } finally {
      setActivatingId(null);
    }
  };

  const hasActiveRDMP = rdmps.some(r => r.status === 'ACTIVE');

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  };

  const getStatusBadgeStyle = (status: string): React.CSSProperties => {
    switch (status) {
      case 'ACTIVE':
        return { ...styles.badge, background: '#d1fae5', color: '#065f46' };
      case 'DRAFT':
        return { ...styles.badge, background: '#fef3c7', color: '#92400e' };
      case 'SUPERSEDED':
        return { ...styles.badge, background: '#e5e7eb', color: '#6b7280' };
      default:
        return styles.badge;
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <p style={styles.loading}>Loading RDMPs...</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={styles.title}>RDMP Management</h3>
        {!showCreateForm && (
          <button
            style={styles.createButton}
            onClick={() => setShowCreateForm(true)}
          >
            + New Draft
          </button>
        )}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Create Form */}
      {showCreateForm && (
        <form onSubmit={handleCreate} style={styles.createForm}>
          <h4 style={styles.formTitle}>Create New RDMP Draft</h4>
          <div style={styles.formGroup}>
            <label style={styles.label}>Title</label>
            <input
              type="text"
              style={styles.input}
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="e.g., Project Data Management Plan v2"
              required
            />
          </div>
          <div style={styles.formGroup}>
            <label style={styles.label}>Content (JSON)</label>
            <textarea
              style={styles.textarea}
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              rows={8}
              placeholder='{"fields": [], "roles": []}'
            />
          </div>
          <div style={styles.formActions}>
            <button
              type="button"
              style={styles.cancelButton}
              onClick={() => {
                setShowCreateForm(false);
                setNewTitle('');
                setNewContent('{}');
              }}
              disabled={creating}
            >
              Cancel
            </button>
            <button
              type="submit"
              style={styles.submitButton}
              disabled={creating || !newTitle.trim()}
            >
              {creating ? 'Creating...' : 'Create Draft'}
            </button>
          </div>
        </form>
      )}

      {/* Confirmation Dialog */}
      <ConfirmDialog
        open={confirmActivate !== null}
        title="Activate RDMP"
        message={`Are you sure you want to activate "${confirmActivate?.title}"?`}
        consequences={
          hasActiveRDMP
            ? [
                'The current active RDMP will be superseded',
                'This project will use the new RDMP for all future operations',
                'This action cannot be undone',
              ]
            : [
                'This project will become operational',
                'Data ingestion will be enabled',
                'This action cannot be undone',
              ]
        }
        confirmLabel="Activate RDMP"
        variant="warning"
        onConfirm={handleActivateConfirm}
        onCancel={() => setConfirmActivate(null)}
        loading={activatingId !== null}
      />

      {/* RDMP List */}
      {rdmps.length === 0 ? (
        <div style={styles.empty}>
          <div style={styles.emptyIcon}>&#128203;</div>
          <p style={styles.emptyTitle}>No RDMP Found</p>
          <p style={styles.emptyText}>
            This project needs an RDMP (Research Data Management Plan) to become operational.
            Create a draft and have a PI activate it to enable data ingestion.
          </p>
          {!showCreateForm && (
            <button
              style={styles.emptyButton}
              onClick={() => setShowCreateForm(true)}
            >
              Create RDMP Draft
            </button>
          )}
        </div>
      ) : (
        <div style={styles.list}>
          {rdmps.map((rdmp) => (
            <div key={rdmp.id} style={styles.rdmpCard}>
              {editingId === rdmp.id ? (
                // Edit mode
                <div style={styles.editForm}>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Title</label>
                    <input
                      type="text"
                      style={styles.input}
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                    />
                  </div>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Content (JSON)</label>
                    <textarea
                      style={styles.textarea}
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      rows={10}
                    />
                  </div>
                  <div style={styles.editActions}>
                    <button
                      style={styles.cancelButton}
                      onClick={handleCancelEdit}
                      disabled={saving}
                    >
                      Cancel
                    </button>
                    <button
                      style={styles.submitButton}
                      onClick={() => handleSaveEdit(rdmp.id)}
                      disabled={saving}
                    >
                      {saving ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                </div>
              ) : (
                // View mode
                <>
                  <div style={styles.rdmpHeader}>
                    <div style={styles.rdmpTitleRow}>
                      <span style={styles.rdmpTitle}>{rdmp.title}</span>
                      <span style={getStatusBadgeStyle(rdmp.status)}>{rdmp.status}</span>
                    </div>
                    <div style={styles.rdmpMeta}>
                      <span>Version {rdmp.version}</span>
                      <span style={styles.separator}>|</span>
                      <span>Created {formatDate(rdmp.created_at)}</span>
                    </div>
                  </div>
                  <div style={styles.rdmpContent}>
                    <pre style={styles.contentPreview}>
                      {JSON.stringify(rdmp.content, null, 2).slice(0, 300)}
                      {JSON.stringify(rdmp.content, null, 2).length > 300 ? '...' : ''}
                    </pre>
                  </div>
                  <div style={styles.rdmpActions}>
                    {rdmp.status === 'DRAFT' && (
                      <>
                        <button
                          style={styles.editButton}
                          onClick={() => handleStartEdit(rdmp)}
                        >
                          Edit
                        </button>
                        <button
                          style={{
                            ...styles.activateButton,
                            ...(canActivate ? {} : styles.disabledButton),
                          }}
                          onClick={() => handleActivateClick(rdmp)}
                          disabled={activatingId === rdmp.id || !canActivate}
                          title={canActivate ? undefined : 'Requires: PI'}
                        >
                          {activatingId === rdmp.id ? 'Activating...' : 'Activate'}
                        </button>
                        {!canActivate && <PermissionHint requiredRole="PI" inline />}
                      </>
                    )}
                    {rdmp.status === 'ACTIVE' && (
                      <span style={styles.activeNote}>Currently active</span>
                    )}
                  </div>
                </>
              )}
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
    padding: '24px',
    maxWidth: '900px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
  },
  title: {
    fontSize: '18px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  createButton: {
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
  },
  loading: {
    color: '#6b7280',
    textAlign: 'center',
    padding: '40px',
  },
  error: {
    padding: '12px',
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '6px',
    color: '#dc2626',
    fontSize: '14px',
    marginBottom: '16px',
  },
  createForm: {
    padding: '20px',
    background: '#f9fafb',
    borderRadius: '8px',
    marginBottom: '20px',
  },
  editForm: {
    padding: '16px 0',
  },
  formTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 16px 0',
  },
  formGroup: {
    marginBottom: '16px',
  },
  label: {
    display: 'block',
    fontSize: '14px',
    fontWeight: 500,
    color: '#374151',
    marginBottom: '6px',
  },
  input: {
    width: '100%',
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxSizing: 'border-box',
  },
  textarea: {
    width: '100%',
    padding: '8px 12px',
    fontSize: '13px',
    fontFamily: 'monospace',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxSizing: 'border-box',
    resize: 'vertical',
  },
  formActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
  },
  editActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    marginTop: '12px',
  },
  cancelButton: {
    padding: '8px 16px',
    fontSize: '14px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#6b7280',
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
  empty: {
    textAlign: 'center',
    padding: '48px 24px',
    background: '#f9fafb',
    borderRadius: '8px',
    border: '1px dashed #d1d5db',
  },
  emptyIcon: {
    fontSize: '48px',
    marginBottom: '16px',
  },
  emptyTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 8px 0',
  },
  emptyText: {
    fontSize: '14px',
    color: '#6b7280',
    maxWidth: '400px',
    margin: '0 auto 20px auto',
    lineHeight: 1.5,
  },
  emptyButton: {
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  rdmpCard: {
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    padding: '16px',
    background: '#fff',
  },
  rdmpHeader: {
    marginBottom: '12px',
  },
  rdmpTitleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '4px',
  },
  rdmpTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#111827',
  },
  badge: {
    padding: '2px 8px',
    fontSize: '12px',
    fontWeight: 500,
    borderRadius: '4px',
  },
  rdmpMeta: {
    fontSize: '13px',
    color: '#6b7280',
  },
  separator: {
    margin: '0 8px',
    color: '#d1d5db',
  },
  rdmpContent: {
    marginBottom: '12px',
  },
  contentPreview: {
    background: '#f9fafb',
    padding: '12px',
    borderRadius: '4px',
    fontSize: '12px',
    fontFamily: 'monospace',
    color: '#374151',
    overflow: 'auto',
    maxHeight: '150px',
    margin: 0,
  },
  rdmpActions: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  editButton: {
    padding: '6px 12px',
    fontSize: '13px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '4px',
    color: '#374151',
    cursor: 'pointer',
  },
  activateButton: {
    padding: '6px 12px',
    fontSize: '13px',
    fontWeight: 500,
    background: '#059669',
    border: 'none',
    borderRadius: '4px',
    color: '#fff',
    cursor: 'pointer',
  },
  activeNote: {
    fontSize: '13px',
    color: '#059669',
    fontWeight: 500,
  },
  disabledButton: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
};
