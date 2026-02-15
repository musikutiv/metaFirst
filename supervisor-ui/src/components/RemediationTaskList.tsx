import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { RemediationTask, RemediationPriority } from '../types';

interface RemediationTaskListProps {
  tasks: RemediationTask[];
}

interface TaskItemProps {
  task: RemediationTask;
  onNavigate: (path: string) => void;
}

function TaskItem({ task, onNavigate }: TaskItemProps) {
  const [expanded, setExpanded] = useState(false);

  const priorityStyles = {
    urgent: { bg: '#fef2f2', border: '#fecaca', icon: '!' },
    recommended: { bg: '#fffbeb', border: '#fde68a', icon: '?' },
    completed: { bg: '#f0fdf4', border: '#bbf7d0', icon: '✓' },
  };

  const style = priorityStyles[task.priority];

  return (
    <div
      data-testid={`remediation-task-${task.id}`}
      data-priority={task.priority}
      style={{
        ...styles.taskItem,
        background: style.bg,
        borderColor: style.border,
      }}
    >
      <div style={styles.taskHeader}>
        <div style={styles.taskLeft}>
          <span
            style={{
              ...styles.priorityBadge,
              background: task.priority === 'urgent' ? '#dc2626' :
                          task.priority === 'recommended' ? '#d97706' : '#059669',
            }}
            aria-label={`Priority: ${task.priority}`}
          >
            {style.icon}
          </span>
          <div style={styles.taskInfo}>
            <h4 style={styles.taskTitle}>{task.title}</h4>
            <p style={styles.taskReason}>{task.reason}</p>
          </div>
        </div>
        <div style={styles.taskActions}>
          <button
            style={styles.learnMoreButton}
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-controls={`task-details-${task.id}`}
          >
            {expanded ? 'Hide details' : 'Learn more'}
          </button>
          {task.priority !== 'completed' && (
            <button
              style={styles.actionButton}
              onClick={() => onNavigate(task.actionPath)}
            >
              {task.actionLabel}
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div
          id={`task-details-${task.id}`}
          style={styles.taskDetails}
          data-testid={`task-details-${task.id}`}
        >
          <div style={styles.detailSection}>
            <span style={styles.detailLabel}>Impact:</span>
            <span style={styles.detailText}>{task.impact}</span>
          </div>
          <div style={styles.detailSection}>
            <span style={styles.detailLabel}>What will this affect?</span>
            <p style={styles.learnMoreText}>{task.learnMore}</p>
          </div>
          <div style={styles.detailSection}>
            <span style={styles.detailLabel}>Steps to resolve:</span>
            <ol style={styles.stepsList}>
              {task.steps.map((step, idx) => (
                <li key={idx} style={styles.stepItem}>{step}</li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}

export function RemediationTaskList({ tasks }: RemediationTaskListProps) {
  const navigate = useNavigate();

  const groupedTasks = useMemo(() => {
    const groups: Record<RemediationPriority, RemediationTask[]> = {
      urgent: [],
      recommended: [],
      completed: [],
    };

    tasks.forEach((task) => {
      groups[task.priority].push(task);
    });

    return groups;
  }, [tasks]);

  const totalPending = groupedTasks.urgent.length + groupedTasks.recommended.length;

  if (tasks.length === 0) {
    return (
      <div data-testid="remediation-empty" style={styles.emptyState}>
        <span style={styles.emptyIcon}>✓</span>
        <p style={styles.emptyText}>No suggested clean-up items</p>
        <p style={styles.emptySubtext}>Your project data is well-organized.</p>
      </div>
    );
  }

  return (
    <div data-testid="remediation-task-list" style={styles.container}>
      {/* Advisory header */}
      <div style={styles.advisoryHeader} data-testid="advisory-header">
        <div style={styles.advisoryIcon}>ℹ</div>
        <div>
          <h3 style={styles.advisoryTitle}>Suggested clean-up</h3>
          <p style={styles.advisoryText}>
            These tasks are suggestions to improve your data organization.
            They are non-destructive and will not modify or delete any data automatically.
            Review each task and take action when ready.
          </p>
        </div>
      </div>

      {/* Summary */}
      <div style={styles.summary}>
        <span style={styles.summaryCount}>{totalPending} task{totalPending !== 1 ? 's' : ''} pending</span>
        {groupedTasks.completed.length > 0 && (
          <span style={styles.completedCount}>
            {groupedTasks.completed.length} completed
          </span>
        )}
      </div>

      {/* Urgent tasks */}
      {groupedTasks.urgent.length > 0 && (
        <section aria-labelledby="urgent-heading" style={styles.section}>
          <h3 id="urgent-heading" style={styles.sectionTitle}>
            <span style={{ ...styles.sectionBadge, background: '#dc2626' }}>
              {groupedTasks.urgent.length}
            </span>
            Urgent
          </h3>
          <p style={styles.sectionDescription}>
            These tasks should be addressed soon to ensure project functionality.
          </p>
          <div style={styles.taskList} role="list">
            {groupedTasks.urgent.map((task) => (
              <TaskItem
                key={task.id}
                task={task}
                onNavigate={navigate}
              />
            ))}
          </div>
        </section>
      )}

      {/* Recommended tasks */}
      {groupedTasks.recommended.length > 0 && (
        <section aria-labelledby="recommended-heading" style={styles.section}>
          <h3 id="recommended-heading" style={styles.sectionTitle}>
            <span style={{ ...styles.sectionBadge, background: '#d97706' }}>
              {groupedTasks.recommended.length}
            </span>
            Recommended
          </h3>
          <p style={styles.sectionDescription}>
            Address these tasks to improve data completeness and organization.
          </p>
          <div style={styles.taskList} role="list">
            {groupedTasks.recommended.map((task) => (
              <TaskItem
                key={task.id}
                task={task}
                onNavigate={navigate}
              />
            ))}
          </div>
        </section>
      )}

      {/* Completed tasks */}
      {groupedTasks.completed.length > 0 && (
        <section aria-labelledby="completed-heading" style={styles.section}>
          <h3 id="completed-heading" style={styles.sectionTitle}>
            <span style={{ ...styles.sectionBadge, background: '#059669' }}>
              {groupedTasks.completed.length}
            </span>
            Completed
          </h3>
          <div style={styles.taskList} role="list">
            {groupedTasks.completed.map((task) => (
              <TaskItem
                key={task.id}
                task={task}
                onNavigate={navigate}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: '900px',
  },
  advisoryHeader: {
    display: 'flex',
    gap: '12px',
    padding: '16px',
    background: '#eff6ff',
    border: '1px solid #bfdbfe',
    borderRadius: '8px',
    marginBottom: '20px',
  },
  advisoryIcon: {
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    background: '#3b82f6',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  advisoryTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: '#1e40af',
    margin: '0 0 4px 0',
  },
  advisoryText: {
    fontSize: '13px',
    color: '#1e40af',
    margin: 0,
    lineHeight: 1.5,
  },
  summary: {
    display: 'flex',
    gap: '16px',
    marginBottom: '20px',
    fontSize: '14px',
  },
  summaryCount: {
    fontWeight: 600,
    color: '#374151',
  },
  completedCount: {
    color: '#059669',
  },
  section: {
    marginBottom: '24px',
  },
  sectionTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '16px',
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 4px 0',
  },
  sectionBadge: {
    minWidth: '20px',
    height: '20px',
    borderRadius: '10px',
    color: '#fff',
    fontSize: '12px',
    fontWeight: 600,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '0 6px',
  },
  sectionDescription: {
    fontSize: '13px',
    color: '#6b7280',
    margin: '0 0 12px 0',
  },
  taskList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  taskItem: {
    border: '1px solid',
    borderRadius: '8px',
    padding: '12px 16px',
  },
  taskHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: '12px',
  },
  taskLeft: {
    display: 'flex',
    gap: '12px',
    flex: 1,
    minWidth: 0,
  },
  priorityBadge: {
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  taskInfo: {
    flex: 1,
    minWidth: 0,
  },
  taskTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  taskReason: {
    fontSize: '13px',
    color: '#6b7280',
    margin: '2px 0 0 0',
  },
  taskActions: {
    display: 'flex',
    gap: '8px',
    flexShrink: 0,
  },
  learnMoreButton: {
    padding: '6px 10px',
    fontSize: '12px',
    background: 'transparent',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#374151',
    cursor: 'pointer',
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
  },
  taskDetails: {
    marginTop: '12px',
    paddingTop: '12px',
    borderTop: '1px solid rgba(0,0,0,0.1)',
  },
  detailSection: {
    marginBottom: '10px',
  },
  detailLabel: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#374151',
    display: 'block',
    marginBottom: '4px',
  },
  detailText: {
    fontSize: '13px',
    color: '#4b5563',
  },
  learnMoreText: {
    fontSize: '13px',
    color: '#4b5563',
    margin: 0,
    lineHeight: 1.5,
  },
  stepsList: {
    margin: '4px 0 0 0',
    paddingLeft: '20px',
    fontSize: '13px',
    color: '#4b5563',
  },
  stepItem: {
    marginBottom: '4px',
    lineHeight: 1.4,
  },
  emptyState: {
    textAlign: 'center',
    padding: '48px 24px',
    background: '#f9fafb',
    borderRadius: '12px',
    border: '1px solid #e5e7eb',
  },
  emptyIcon: {
    width: '48px',
    height: '48px',
    borderRadius: '50%',
    background: '#d1fae5',
    color: '#059669',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '24px',
    marginBottom: '12px',
  },
  emptyText: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#111827',
    margin: '0 0 4px 0',
  },
  emptySubtext: {
    fontSize: '14px',
    color: '#6b7280',
    margin: 0,
  },
};
