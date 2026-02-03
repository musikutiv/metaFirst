import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { Project, Supervisor, RDMPVersion } from '../types';

interface CreateProjectWizardProps {
  onClose: () => void;
  onProjectCreated: (project: Project) => void;
  onRDMPActivated?: (rdmp: RDMPVersion) => void;
}

type WizardStep = 'project' | 'rdmp' | 'activate';

export function CreateProjectWizard({ onClose, onProjectCreated, onRDMPActivated }: CreateProjectWizardProps) {
  const navigate = useNavigate();

  // Wizard state
  const [step, setStep] = useState<WizardStep>('project');
  const [createdProject, setCreatedProject] = useState<Project | null>(null);
  const [createdRDMP, setCreatedRDMP] = useState<RDMPVersion | null>(null);

  // Step 1: Project form state
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [loadingSupervisors, setLoadingSupervisors] = useState(true);
  const [projectName, setProjectName] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [supervisorId, setSupervisorId] = useState<number | null>(null);

  // Step 2: RDMP form state
  const [rdmpTitle, setRdmpTitle] = useState('');
  const [rdmpContent, setRdmpContent] = useState('{\n  "fields": [],\n  "roles": []\n}');

  // Common state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activationError, setActivationError] = useState<string | null>(null);
  const [cannotActivate, setCannotActivate] = useState(false);

  // Load supervisors on mount
  useEffect(() => {
    loadSupervisors();
  }, []);

  // Set default RDMP title when project is created
  useEffect(() => {
    if (createdProject && !rdmpTitle) {
      setRdmpTitle(`RDMP ${createdProject.name} v1`);
    }
  }, [createdProject]);

  const loadSupervisors = async () => {
    try {
      const data = await apiClient.getSupervisors();
      setSupervisors(data.filter(s => s.is_active));
      if (data.length === 1) {
        setSupervisorId(data[0].id);
      }
    } catch (e) {
      setError('Failed to load labs');
    } finally {
      setLoadingSupervisors(false);
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supervisorId) {
      setError('Please select a lab');
      return;
    }

    setError(null);
    setSubmitting(true);

    try {
      const project = await apiClient.createProject({
        name: projectName,
        description: projectDescription || undefined,
        supervisor_id: supervisorId,
      });
      setCreatedProject(project);
      onProjectCreated(project);
      setStep('rdmp');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateRDMP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createdProject) return;

    setError(null);
    setSubmitting(true);

    try {
      // Validate JSON
      let contentObj: Record<string, unknown>;
      try {
        contentObj = JSON.parse(rdmpContent);
      } catch {
        throw new Error('Invalid JSON in content field');
      }

      const rdmp = await apiClient.createRDMPDraft(createdProject.id, {
        title: rdmpTitle,
        content: contentObj,
      });
      setCreatedRDMP(rdmp);
      setStep('activate');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create RDMP');
    } finally {
      setSubmitting(false);
    }
  };

  const handleActivate = async () => {
    if (!createdRDMP || !createdProject) return;

    setActivationError(null);
    setSubmitting(true);

    try {
      const activatedRDMP = await apiClient.activateRDMP(createdRDMP.id);
      // Notify parent about the activated RDMP immediately
      onRDMPActivated?.(activatedRDMP);
      // Success - close wizard and navigate to project
      onClose();
      navigate(`/?project=${createdProject.id}`);
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to activate RDMP';
      // Check if it's a permission error (403)
      if (message.includes('403') || message.toLowerCase().includes('permission') || message.toLowerCase().includes('pi')) {
        setCannotActivate(true);
        setActivationError('Only PI can activate RDMPs. Please ask a PI to activate this RDMP.');
      } else {
        setActivationError(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinishWithoutActivation = () => {
    if (!createdProject) return;
    onClose();
    navigate(`/rdmps?project=${createdProject.id}`);
  };

  const renderStepIndicator = () => (
    <div style={styles.stepIndicator}>
      <div style={{ ...styles.step, ...(step === 'project' ? styles.stepActive : styles.stepComplete) }}>
        <span style={styles.stepNumber}>1</span>
        <span style={styles.stepLabel}>Project</span>
      </div>
      <div style={styles.stepDivider} />
      <div style={{
        ...styles.step,
        ...(step === 'rdmp' ? styles.stepActive : step === 'activate' ? styles.stepComplete : {})
      }}>
        <span style={styles.stepNumber}>2</span>
        <span style={styles.stepLabel}>RDMP</span>
      </div>
      <div style={styles.stepDivider} />
      <div style={{ ...styles.step, ...(step === 'activate' ? styles.stepActive : {}) }}>
        <span style={styles.stepNumber}>3</span>
        <span style={styles.stepLabel}>Activate</span>
      </div>
    </div>
  );

  const renderProjectStep = () => (
    <form onSubmit={handleCreateProject}>
      <h3 style={styles.stepTitle}>Create New Project</h3>
      <p style={styles.stepDescription}>
        Enter the basic information for your new project.
      </p>

      {loadingSupervisors ? (
        <div style={styles.loading}>Loading labs...</div>
      ) : (
        <>
          <div style={styles.formGroup}>
            <label style={styles.label}>Lab *</label>
            <select
              style={styles.select}
              value={supervisorId || ''}
              onChange={(e) => setSupervisorId(e.target.value ? Number(e.target.value) : null)}
              required
            >
              <option value="">-- Select Lab --</option>
              {supervisors.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Project Name *</label>
            <input
              type="text"
              style={styles.input}
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="e.g., Cancer Genomics Study 2024"
              required
              maxLength={255}
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Description</label>
            <textarea
              style={styles.textarea}
              value={projectDescription}
              onChange={(e) => setProjectDescription(e.target.value)}
              placeholder="Optional project description..."
              rows={3}
            />
          </div>
        </>
      )}

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.actions}>
        <button type="button" style={styles.cancelButton} onClick={onClose} disabled={submitting}>
          Cancel
        </button>
        <button
          type="submit"
          style={styles.primaryButton}
          disabled={submitting || loadingSupervisors || !projectName.trim() || !supervisorId}
        >
          {submitting ? 'Creating...' : 'Create Project'}
        </button>
      </div>
    </form>
  );

  const renderRDMPStep = () => (
    <form onSubmit={handleCreateRDMP}>
      <h3 style={styles.stepTitle}>Create RDMP Draft</h3>
      <p style={styles.stepDescription}>
        Every project needs an active RDMP before data can be ingested.
        Create a draft now - you can edit it later.
      </p>

      <div style={styles.formGroup}>
        <label style={styles.label}>RDMP Title *</label>
        <input
          type="text"
          style={styles.input}
          value={rdmpTitle}
          onChange={(e) => setRdmpTitle(e.target.value)}
          required
          maxLength={255}
        />
      </div>

      <div style={styles.formGroup}>
        <label style={styles.label}>Content (JSON)</label>
        <textarea
          style={styles.codeTextarea}
          value={rdmpContent}
          onChange={(e) => setRdmpContent(e.target.value)}
          rows={10}
        />
        <p style={styles.hint}>
          Define fields, roles, and other RDMP configuration. You can edit this later.
        </p>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.actions}>
        <button type="button" style={styles.cancelButton} onClick={onClose} disabled={submitting}>
          Cancel
        </button>
        <button
          type="submit"
          style={styles.primaryButton}
          disabled={submitting || !rdmpTitle.trim()}
        >
          {submitting ? 'Creating...' : 'Create RDMP Draft'}
        </button>
      </div>
    </form>
  );

  const renderActivateStep = () => (
    <div>
      <h3 style={styles.stepTitle}>Activate RDMP</h3>

      {!cannotActivate ? (
        <>
          <p style={styles.stepDescription}>
            Your project and RDMP draft have been created. Activate the RDMP to make
            the project operational and allow data ingestion.
          </p>

          <div style={styles.successBox}>
            <div style={styles.successItem}>
              <span style={styles.checkmark}>&#10003;</span>
              <span>Project "{createdProject?.name}" created</span>
            </div>
            <div style={styles.successItem}>
              <span style={styles.checkmark}>&#10003;</span>
              <span>RDMP Draft "{createdRDMP?.title}" created</span>
            </div>
          </div>

          {activationError && <div style={styles.error}>{activationError}</div>}

          <div style={styles.actions}>
            <button
              type="button"
              style={styles.secondaryButton}
              onClick={handleFinishWithoutActivation}
              disabled={submitting}
            >
              Finish Later
            </button>
            <button
              type="button"
              style={styles.primaryButton}
              onClick={handleActivate}
              disabled={submitting}
            >
              {submitting ? 'Activating...' : 'Activate RDMP'}
            </button>
          </div>
        </>
      ) : (
        <>
          <div style={styles.warningBox}>
            <p style={styles.warningTitle}>PI Approval Required</p>
            <p style={styles.warningText}>
              The RDMP draft has been created, but only a PI can activate it.
              Please ask a PI to review and activate the RDMP before data can be ingested.
            </p>
          </div>

          <div style={styles.successBox}>
            <div style={styles.successItem}>
              <span style={styles.checkmark}>&#10003;</span>
              <span>Project "{createdProject?.name}" created</span>
            </div>
            <div style={styles.successItem}>
              <span style={styles.checkmark}>&#10003;</span>
              <span>RDMP Draft "{createdRDMP?.title}" created (pending activation)</span>
            </div>
          </div>

          <div style={styles.actions}>
            <button
              type="button"
              style={styles.primaryButton}
              onClick={handleFinishWithoutActivation}
            >
              Go to RDMP Management
            </button>
          </div>
        </>
      )}
    </div>
  );

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h2 style={styles.title}>New Project Setup</h2>
          <button style={styles.closeButton} onClick={onClose}>&times;</button>
        </div>

        {renderStepIndicator()}

        <div style={styles.content}>
          {step === 'project' && renderProjectStep()}
          {step === 'rdmp' && renderRDMPStep()}
          {step === 'activate' && renderActivateStep()}
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
    borderRadius: '12px',
    width: '100%',
    maxWidth: '560px',
    maxHeight: '90vh',
    overflow: 'auto',
    boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px 24px',
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
  stepIndicator: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '20px 24px',
    background: '#f9fafb',
    borderBottom: '1px solid #e5e7eb',
  },
  step: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    color: '#9ca3af',
  },
  stepActive: {
    color: '#2563eb',
  },
  stepComplete: {
    color: '#059669',
  },
  stepNumber: {
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    background: 'currentColor',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '12px',
    fontWeight: 600,
  },
  stepLabel: {
    fontSize: '14px',
    fontWeight: 500,
  },
  stepDivider: {
    width: '40px',
    height: '2px',
    background: '#e5e7eb',
    margin: '0 12px',
  },
  content: {
    padding: '24px',
  },
  stepTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#111827',
    margin: '0 0 8px 0',
  },
  stepDescription: {
    fontSize: '14px',
    color: '#6b7280',
    marginBottom: '20px',
    lineHeight: 1.5,
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
    padding: '10px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxSizing: 'border-box',
  },
  select: {
    width: '100%',
    padding: '10px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    background: '#fff',
  },
  textarea: {
    width: '100%',
    padding: '10px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxSizing: 'border-box',
    resize: 'vertical',
  },
  codeTextarea: {
    width: '100%',
    padding: '10px 12px',
    fontSize: '13px',
    fontFamily: 'monospace',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxSizing: 'border-box',
    resize: 'vertical',
  },
  hint: {
    fontSize: '12px',
    color: '#6b7280',
    marginTop: '6px',
  },
  loading: {
    padding: '20px',
    textAlign: 'center',
    color: '#6b7280',
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
  successBox: {
    padding: '16px',
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    borderRadius: '8px',
    marginBottom: '20px',
  },
  successItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '14px',
    color: '#166534',
    marginBottom: '8px',
  },
  checkmark: {
    color: '#059669',
    fontWeight: 'bold',
  },
  warningBox: {
    padding: '16px',
    background: '#fffbeb',
    border: '1px solid #fde68a',
    borderRadius: '8px',
    marginBottom: '20px',
  },
  warningTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#92400e',
    margin: '0 0 8px 0',
  },
  warningText: {
    fontSize: '14px',
    color: '#78350f',
    margin: 0,
    lineHeight: 1.5,
  },
  actions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    marginTop: '24px',
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
  secondaryButton: {
    padding: '10px 16px',
    fontSize: '14px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#374151',
    cursor: 'pointer',
  },
  primaryButton: {
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
  },
};
