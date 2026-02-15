import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { PendingIngest, RDMPField, Sample, StorageRoot, RDMP, RDMPVersion } from '../types';

interface IngestPageProps {
  onProjectLoaded?: (projectId: number) => void;
  onIngestComplete?: () => void;
}

export function IngestPage({ onProjectLoaded, onIngestComplete }: IngestPageProps) {
  const { pendingId } = useParams<{ pendingId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ingest, setIngest] = useState<PendingIngest | null>(null);
  const [rdmp, setRdmp] = useState<RDMP | null>(null);
  const [activeRDMP, setActiveRDMP] = useState<RDMPVersion | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [storageRoots, setStorageRoots] = useState<StorageRoot[]>([]);

  // Form state
  const [sampleOption, setSampleOption] = useState<'existing' | 'new'>('new');
  const [selectedSampleId, setSelectedSampleId] = useState<number | null>(null);
  const [newSampleIdentifier, setNewSampleIdentifier] = useState('');
  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Fetch pending ingest and project data
  useEffect(() => {
    if (!pendingId) {
      setError('No pending ingest ID provided');
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch the pending ingest
        const pendingIngest = await apiClient.getPendingIngest(Number(pendingId));
        setIngest(pendingIngest);

        // Set initial form state based on detected or inferred sample identifier
        const initialId = pendingIngest.detected_sample_id || pendingIngest.inferred_sample_identifier;
        if (initialId) {
          setSampleOption('new');
          setNewSampleIdentifier(initialId);
        } else {
          setSampleOption('existing');
        }

        // Notify parent about the project for consistency
        if (onProjectLoaded) {
          onProjectLoaded(pendingIngest.project_id);
        }

        // Fetch project-scoped data
        const [rdmpData, activeRdmpData, samplesResponse, storageRootsData] = await Promise.all([
          apiClient.getProjectRDMP(pendingIngest.project_id).catch(() => null),
          apiClient.getActiveRDMP(pendingIngest.project_id).catch(() => null),
          apiClient.getSamples(pendingIngest.project_id),
          apiClient.getStorageRoots(pendingIngest.project_id),
        ]);

        setRdmp(rdmpData);
        setActiveRDMP(activeRdmpData);
        setSamples(samplesResponse.items);
        setStorageRoots(storageRootsData);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load pending ingest');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [pendingId, onProjectLoaded]);

  const fields = rdmp?.rdmp_json.fields || [];
  const storageRoot = storageRoots.find(r => r.id === ingest?.storage_root_id);

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
    if (!ingest) return;

    setSubmitError(null);
    setSubmitting(true);

    try {
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
      // Trigger project data reload before navigating
      if (onIngestComplete) {
        onIngestComplete();
      }
      navigate('/');
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Failed to finalize ingest');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelIngest = async () => {
    if (!ingest) return;
    if (!confirm('Cancel this pending ingest? The file will still exist but will no longer appear in the inbox.')) {
      return;
    }

    try {
      setSubmitting(true);
      await apiClient.cancelPendingIngest(ingest.id);
      navigate('/inbox');
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Failed to cancel ingest');
      setSubmitting(false);
    }
  };

  const handleBack = () => {
    navigate('/inbox');
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

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <p>Loading file data...</p>
      </div>
    );
  }

  if (error || !ingest) {
    return (
      <div style={styles.errorContainer}>
        <h2 style={styles.errorTitle}>Error</h2>
        <p>{error || 'Pending ingest not found'}</p>
        <button onClick={handleBack} style={styles.backButton}>
          Back to Inbox
        </button>
      </div>
    );
  }

  // Check if already completed/cancelled
  if (ingest.status !== 'PENDING') {
    return (
      <div style={styles.errorContainer}>
        <h2 style={styles.errorTitle}>File {ingest.status.toLowerCase()}</h2>
        <p>This file has already been {ingest.status.toLowerCase()}.</p>
        <button onClick={handleBack} style={styles.backButton}>
          Back to Inbox
        </button>
      </div>
    );
  }

  // Check if project has an active RDMP
  if (!activeRDMP) {
    return (
      <div style={styles.pageContainer}>
        <div style={styles.blockedContainer}>
          <div style={styles.blockedIcon}>&#9888;</div>
          <h2 style={styles.blockedTitle}>Add data not available</h2>
          <p style={styles.blockedText}>
            Activate an RDMP to add data to this project.
          </p>
          {ingest.project_name && (
            <p style={styles.blockedProject}>Project: {ingest.project_name}</p>
          )}
          <div style={styles.blockedActions}>
            <button onClick={handleBack} style={styles.cancelButton}>
              Back to Inbox
            </button>
            <button onClick={() => navigate('/rdmps')} style={styles.submitButton}>
              Go to RDMPs
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.pageContainer}>
      <div style={styles.container}>
        <div style={styles.header}>
          <h2 style={styles.title}>Add Data</h2>
          <button onClick={handleBack} style={styles.closeButton}>
            &times;
          </button>
        </div>

        {/* Project Info */}
        {ingest.project_name && (
          <div style={styles.projectBanner}>
            Project: {ingest.project_name}
          </div>
        )}

        {/* File Info Section */}
        <div style={styles.fileInfo}>
          <div style={styles.fileInfoRow}>
            <span style={styles.fileInfoLabel}>File:</span>
            <span style={styles.filePath}>{ingest.relative_path}</span>
          </div>
          <div style={styles.fileInfoRow}>
            <span style={styles.fileInfoLabel}>Storage Root:</span>
            <span>{storageRoot?.name || ingest.storage_root_name || `ID ${ingest.storage_root_id}`}</span>
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

        {/* Sample ID Detection Panel */}
        <div style={styles.detectionPanel}>
          <h4 style={styles.detectionTitle}>Detected Identifiers</h4>
          <div style={styles.detectionContent}>
            <div style={styles.detectionRow}>
              <span style={styles.detectionLabel}>Detected Sample ID:</span>
              <span style={ingest.detected_sample_id ? styles.detectedId : styles.noDetection}>
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

        <form onSubmit={handleSubmit}>
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
              <h3 style={styles.sectionTitle}>Core Metadata Fields</h3>
              <p style={styles.hint}>
                Fill in core fields for the new sample. You can also complete these later.
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

          {submitError && <div style={styles.error}>{submitError}</div>}

          <div style={styles.actions}>
            <button
              type="button"
              onClick={handleCancelIngest}
              style={styles.cancelButton}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              style={styles.submitButton}
              disabled={submitting}
            >
              {submitting ? 'Processing...' : 'Add Data'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  pageContainer: {
    padding: '24px',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  loadingContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '300px',
    color: '#6b7280',
  },
  errorContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '300px',
    color: '#6b7280',
    gap: '16px',
  },
  errorTitle: {
    fontSize: '20px',
    fontWeight: 600,
    color: '#dc2626',
    margin: 0,
  },
  backButton: {
    padding: '10px 20px',
    fontSize: '14px',
    background: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
  },
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
  projectBanner: {
    padding: '8px 16px',
    background: '#eff6ff',
    borderBottom: '1px solid #e5e7eb',
    fontSize: '14px',
    color: '#2563eb',
    fontWeight: 500,
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
  blockedContainer: {
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid #fecaca',
    maxWidth: '500px',
    margin: '0 auto',
    padding: '40px',
    textAlign: 'center',
  },
  blockedIcon: {
    fontSize: '48px',
    color: '#dc2626',
    marginBottom: '16px',
  },
  blockedTitle: {
    fontSize: '20px',
    fontWeight: 600,
    color: '#991b1b',
    margin: '0 0 12px 0',
  },
  blockedText: {
    fontSize: '14px',
    color: '#6b7280',
    marginBottom: '16px',
    lineHeight: 1.5,
  },
  blockedProject: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#374151',
    marginBottom: '24px',
  },
  blockedActions: {
    display: 'flex',
    justifyContent: 'center',
    gap: '12px',
  },
};
