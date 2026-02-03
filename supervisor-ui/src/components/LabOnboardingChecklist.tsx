import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { LabRole } from '../types';
import { getRDMPStatus } from './StatusBadge';

interface LabOnboardingChecklistProps {
  supervisorId: number;
  supervisorName: string;
  userRole: LabRole | null;
}

interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  done: boolean;
  actionLabel: string;
  actionPath: string;
}

interface LabOnboardingState {
  hasPIOrSteward: boolean;
  hasProject: boolean;
  hasRDMP: boolean;
  hasIngestor: boolean;
}

const DISMISSAL_KEY_PREFIX = 'lab-onboarding-dismissed-';

function getDismissalKey(supervisorId: number): string {
  return `${DISMISSAL_KEY_PREFIX}${supervisorId}`;
}

function isDismissed(supervisorId: number): boolean {
  try {
    return localStorage.getItem(getDismissalKey(supervisorId)) === 'true';
  } catch {
    return false;
  }
}

function setDismissed(supervisorId: number, dismissed: boolean): void {
  try {
    if (dismissed) {
      localStorage.setItem(getDismissalKey(supervisorId), 'true');
    } else {
      localStorage.removeItem(getDismissalKey(supervisorId));
    }
  } catch {
    // localStorage not available
  }
}

export function LabOnboardingChecklist({
  supervisorId,
  supervisorName,
  userRole,
}: LabOnboardingChecklistProps) {
  const navigate = useNavigate();
  const [state, setState] = useState<LabOnboardingState | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissedState] = useState(() => isDismissed(supervisorId));
  const [error, setError] = useState<string | null>(null);

  // Only show to PI and STEWARD
  const canView = userRole === 'PI' || userRole === 'STEWARD';

  const loadOnboardingState = useCallback(async () => {
    if (!canView) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Load members and projects for this lab
      const [members, projects] = await Promise.all([
        apiClient.getSupervisorMembers(supervisorId),
        apiClient.getProjects(),
      ]);

      // Filter projects for this lab
      const labProjects = projects.filter(p => p.supervisor_id === supervisorId);

      // Check if lab has PI or Steward
      const hasPIOrSteward = members.some(
        m => m.role === 'PI' || m.role === 'STEWARD'
      );

      // Check if lab has at least one project
      const hasProject = labProjects.length > 0;

      // Check if any project has RDMP in Draft or Active state
      let hasRDMP = false;
      let hasIngestor = false;

      if (hasProject) {
        // Check RDMPs and storage roots for each project
        const projectChecks = await Promise.all(
          labProjects.map(async (project) => {
            try {
              const [rdmps, storageRoots] = await Promise.all([
                apiClient.listRDMPVersions(project.id),
                apiClient.getStorageRoots(project.id),
              ]);

              const rdmpStatus = getRDMPStatus(rdmps);
              const projectHasRDMP = rdmpStatus === 'DRAFT' || rdmpStatus === 'ACTIVE';
              const projectHasIngestor = storageRoots.length > 0;

              return { projectHasRDMP, projectHasIngestor };
            } catch {
              return { projectHasRDMP: false, projectHasIngestor: false };
            }
          })
        );

        hasRDMP = projectChecks.some(p => p.projectHasRDMP);
        hasIngestor = projectChecks.some(p => p.projectHasIngestor);
      }

      setState({ hasPIOrSteward, hasProject, hasRDMP, hasIngestor });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load onboarding state');
    } finally {
      setLoading(false);
    }
  }, [supervisorId, canView]);

  useEffect(() => {
    loadOnboardingState();
  }, [loadOnboardingState]);

  // Reset dismissal when checklist becomes incomplete after being complete
  useEffect(() => {
    if (state) {
      const allComplete = state.hasPIOrSteward && state.hasProject && state.hasRDMP && state.hasIngestor;
      if (!allComplete && dismissed) {
        // Checklist is incomplete, show it again
        setDismissedState(false);
        setDismissed(supervisorId, false);
      }
    }
  }, [state, dismissed, supervisorId]);

  // Don't render for Researchers
  if (!canView) {
    return null;
  }

  // Don't render while loading
  if (loading) {
    return null;
  }

  // Don't render on error
  if (error || !state) {
    return null;
  }

  const allComplete = state.hasPIOrSteward && state.hasProject && state.hasRDMP && state.hasIngestor;

  // If all complete and dismissed, don't show
  if (allComplete && dismissed) {
    return null;
  }

  // If dismissed but not complete, show anyway
  if (dismissed && !allComplete) {
    // Reset dismissal since items are incomplete
  }

  const items: ChecklistItem[] = [
    {
      id: 'pi-steward',
      label: 'Add a PI or Steward',
      description: state.hasPIOrSteward
        ? 'Your lab has at least one PI or Steward.'
        : 'Add a PI or Steward to manage the lab.',
      done: state.hasPIOrSteward,
      actionLabel: 'Manage Members',
      actionPath: `/supervisors/${supervisorId}/members`,
    },
    {
      id: 'project',
      label: 'Create a project',
      description: state.hasProject
        ? 'Your lab has at least one project.'
        : 'Create a project to organize your research data.',
      done: state.hasProject,
      actionLabel: 'Create Project',
      actionPath: '/', // Will trigger create project wizard
    },
    {
      id: 'rdmp',
      label: 'Set up an RDMP',
      description: state.hasRDMP
        ? 'At least one project has an RDMP (Draft or Active).'
        : 'Create and activate an RDMP to enable data ingestion.',
      done: state.hasRDMP,
      actionLabel: 'Manage RDMPs',
      actionPath: '/rdmps',
    },
    {
      id: 'ingestor',
      label: 'Configure an ingestor',
      description: state.hasIngestor
        ? 'At least one project has a storage root configured.'
        : 'Set up a storage root to start ingesting data.',
      done: state.hasIngestor,
      actionLabel: 'View Projects',
      actionPath: '/',
    },
  ];

  const completedCount = items.filter(i => i.done).length;
  const progress = (completedCount / items.length) * 100;

  const handleDismiss = () => {
    setDismissedState(true);
    setDismissed(supervisorId, true);
  };

  return (
    <div
      data-testid="lab-onboarding-checklist"
      data-supervisor-id={supervisorId}
      style={styles.container}
    >
      <div style={styles.header}>
        <div>
          <h3 style={styles.title}>Get Started with {supervisorName}</h3>
          <p style={styles.subtitle}>
            Complete these steps to make your lab operational.
          </p>
        </div>
        {allComplete && (
          <button
            style={styles.dismissButton}
            onClick={handleDismiss}
            aria-label="Dismiss checklist"
          >
            Dismiss
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div style={styles.progressContainer}>
        <div style={styles.progressBar}>
          <div
            style={{
              ...styles.progressFill,
              width: `${progress}%`,
            }}
          />
        </div>
        <span style={styles.progressText}>
          {completedCount} of {items.length} complete
        </span>
      </div>

      {/* Checklist items */}
      <div style={styles.items}>
        {items.map((item) => (
          <div
            key={item.id}
            data-testid={`checklist-item-${item.id}`}
            data-done={item.done}
            style={{
              ...styles.item,
              ...(item.done ? styles.itemDone : {}),
            }}
          >
            <div style={styles.itemIcon}>
              {item.done ? (
                <span style={styles.checkIcon}>&#10003;</span>
              ) : (
                <span style={styles.emptyIcon}>&#9675;</span>
              )}
            </div>
            <div style={styles.itemContent}>
              <div style={styles.itemLabel}>{item.label}</div>
              <div style={styles.itemDescription}>{item.description}</div>
            </div>
            {!item.done && (
              <button
                style={styles.actionButton}
                onClick={() => navigate(item.actionPath)}
              >
                {item.actionLabel}
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Documentation link */}
      <div style={styles.footer}>
        <button
          style={styles.helpLink}
          onClick={() => navigate('/roles')}
        >
          What is required to get started?
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '12px',
    padding: '20px',
    marginBottom: '24px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '16px',
  },
  title: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  subtitle: {
    fontSize: '13px',
    color: '#6b7280',
    margin: '4px 0 0 0',
  },
  dismissButton: {
    padding: '6px 12px',
    fontSize: '13px',
    background: '#f3f4f6',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#374151',
    cursor: 'pointer',
  },
  progressContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '16px',
  },
  progressBar: {
    flex: 1,
    height: '6px',
    background: '#e5e7eb',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    background: '#059669',
    borderRadius: '3px',
    transition: 'width 0.3s ease',
  },
  progressText: {
    fontSize: '12px',
    color: '#6b7280',
    whiteSpace: 'nowrap',
  },
  items: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px',
    background: '#f9fafb',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
  },
  itemDone: {
    background: '#f0fdf4',
    borderColor: '#bbf7d0',
  },
  itemIcon: {
    width: '24px',
    height: '24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  checkIcon: {
    fontSize: '16px',
    color: '#059669',
    fontWeight: 'bold',
  },
  emptyIcon: {
    fontSize: '16px',
    color: '#9ca3af',
  },
  itemContent: {
    flex: 1,
    minWidth: 0,
  },
  itemLabel: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#111827',
  },
  itemDescription: {
    fontSize: '12px',
    color: '#6b7280',
    marginTop: '2px',
  },
  actionButton: {
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: 500,
    background: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  footer: {
    marginTop: '16px',
    paddingTop: '12px',
    borderTop: '1px solid #e5e7eb',
  },
  helpLink: {
    fontSize: '13px',
    color: '#2563eb',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    textDecoration: 'underline',
    padding: 0,
  },
};
