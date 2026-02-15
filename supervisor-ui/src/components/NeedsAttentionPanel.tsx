import { useNavigate } from 'react-router-dom';
import type { NeedsAttentionItem, Project } from '../types';

interface NeedsAttentionPanelProps {
  items: NeedsAttentionItem[];
  /** Map of project ID to project details for deep link labels. */
  projectsById?: Map<number, Project>;
  /** Callback when a project is selected (for switching context). */
  onSelectProject?: (projectId: number) => void;
}

/**
 * Compact panel showing needs-attention items with deep links.
 * Designed for Lab overview contexts where Steward/PI can act.
 */
export function NeedsAttentionPanel({
  items,
  projectsById,
  onSelectProject,
}: NeedsAttentionPanelProps) {
  const navigate = useNavigate();

  if (items.length === 0) {
    return null;
  }

  const severityColors = {
    high: { bg: '#fef2f2', border: '#fecaca', text: '#991b1b', icon: '#dc2626' },
    warning: { bg: '#fffbeb', border: '#fde68a', text: '#92400e', icon: '#f59e0b' },
    info: { bg: '#eff6ff', border: '#bfdbfe', text: '#1e40af', icon: '#3b82f6' },
  };

  /**
   * Resolve a deep link for the given needs-attention type.
   * Uses existing routes only — no new filtering features.
   */
  function getDeepLink(item: NeedsAttentionItem): {
    path: string;
    label: string;
    projectId?: number;
  } | null {
    const firstProjectId = item.entity_ids[0];

    switch (item.type) {
      case 'project_operational_without_active_rdmp':
      case 'project_with_superseded_rdmp':
      case 'project_without_rdmp':
        // Link to the first affected project's RDMP page
        if (firstProjectId) {
          return {
            path: '/rdmps',
            label: 'Go to RDMP',
            projectId: firstProjectId,
          };
        }
        return null;

      case 'unresolved_remediation_high':
      case 'unresolved_remediation_warning':
        // Link to tasks tab (remediation list)
        if (firstProjectId) {
          return {
            path: '/tasks',
            label: 'View Tasks',
            projectId: firstProjectId,
          };
        }
        return null;

      default:
        return null;
    }
  }

  function handleAction(item: NeedsAttentionItem) {
    const link = getDeepLink(item);
    if (!link) return;

    // If we need to switch project context, call the callback first
    if (link.projectId && onSelectProject) {
      onSelectProject(link.projectId);
    }
    navigate(link.path);
  }

  return (
    <div
      data-testid="needs-attention-panel"
      style={{
        background: '#fff',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        padding: '16px',
        marginBottom: '24px',
      }}
    >
      <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#374151', margin: '0 0 12px 0' }}>
        Needs Attention
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {items.map((item, idx) => {
          const colors = severityColors[item.severity] || severityColors.info;
          const link = getDeepLink(item);
          const projectName =
            item.entity_ids[0] && projectsById?.get(item.entity_ids[0])?.name;

          return (
            <div
              key={`${item.type}-${idx}`}
              data-testid={`attention-item-${item.type}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 12px',
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', flex: 1 }}>
                <span style={{ fontSize: '14px', color: colors.icon }}>
                  {item.severity === 'high' ? '\u25CF' : item.severity === 'warning' ? '\u25B2' : '\u2139'}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '13px', fontWeight: 500, color: colors.text }}>
                    {item.message}
                  </div>
                  {projectName && item.count === 1 && (
                    <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                      Project: {projectName}
                    </div>
                  )}
                  {item.count > 1 && (
                    <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                      Affects {item.count} {item.entity_type === 'project' ? 'projects' : 'items'}
                      {item.entity_ids.length < item.count && ` (showing first ${item.entity_ids.length})`}
                    </div>
                  )}
                </div>
              </div>
              {link && (
                <button
                  onClick={() => handleAction(item)}
                  style={{
                    padding: '6px 12px',
                    fontSize: '12px',
                    fontWeight: 500,
                    background: '#fff',
                    border: `1px solid ${colors.border}`,
                    borderRadius: '4px',
                    color: colors.text,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {link.label}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
