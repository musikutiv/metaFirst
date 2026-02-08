import { useNavigate } from 'react-router-dom';
import type { RDMPStatus } from './StatusBadge';
import type { LabRole } from '../types';

interface ProjectStatusCalloutProps {
  projectId: number;
  rdmpStatus: RDMPStatus;
  /** Whether the current user can activate RDMPs (PI only) */
  canActivate?: boolean;
  /** Current user's lab role, for authority hints in action text. */
  userRole?: LabRole | null;
}

interface StatusInfo {
  type: 'success' | 'warning' | 'error';
  title: string;
  description: string;
  actionLabel: string;
  actionPath: string;
}

function getStatusInfo(rdmpStatus: RDMPStatus, projectId: number, canActivate: boolean): StatusInfo {
  switch (rdmpStatus) {
    case 'ACTIVE':
      return {
        type: 'success',
        title: 'Project Operational',
        description: 'This project has an active RDMP. Data ingestion is enabled.',
        actionLabel: 'Manage RDMPs',
        actionPath: `/rdmps?project=${projectId}`,
      };

    case 'DRAFT':
      return {
        type: 'warning',
        title: 'RDMP Draft Pending',
        description: canActivate
          ? 'Activate the RDMP draft to make this project operational and enable data ingestion.'
          : 'An RDMP draft exists. Ask a PI to activate it to enable data ingestion.',
        actionLabel: canActivate ? 'Activate RDMP' : 'View RDMP',
        actionPath: `/rdmps?project=${projectId}`,
      };

    case 'SUPERSEDED':
      return {
        type: 'error',
        title: 'All RDMPs Superseded',
        description: 'No active RDMP. Create a new RDMP draft and activate it to resume operations.',
        actionLabel: 'Create New RDMP',
        actionPath: `/rdmps?project=${projectId}`,
      };

    case 'NONE':
    default:
      return {
        type: 'error',
        title: 'RDMP Required',
        description: 'This project has no RDMP. Create and activate an RDMP to enable data ingestion.',
        actionLabel: 'Create RDMP',
        actionPath: `/rdmps?project=${projectId}`,
      };
  }
}

const typeStyles = {
  success: {
    bg: '#f0fdf4',
    border: '#bbf7d0',
    icon: '\u2713', // ✓
    iconColor: '#059669',
    titleColor: '#166534',
    textColor: '#15803d',
  },
  warning: {
    bg: '#fffbeb',
    border: '#fde68a',
    icon: '\u25B2', // ▲
    iconColor: '#f59e0b',
    titleColor: '#92400e',
    textColor: '#a16207',
  },
  error: {
    bg: '#fef2f2',
    border: '#fecaca',
    icon: '\u25CF', // ●
    iconColor: '#dc2626',
    titleColor: '#991b1b',
    textColor: '#b91c1c',
  },
};

export function ProjectStatusCallout({ projectId, rdmpStatus, canActivate = false, userRole }: ProjectStatusCalloutProps) {
  const navigate = useNavigate();
  const info = getStatusInfo(rdmpStatus, projectId, canActivate);
  const style = typeStyles[info.type];

  // Authority hint for non-operational states where activation is needed
  const showAuthorityHint =
    rdmpStatus !== 'ACTIVE' && !canActivate && userRole;

  return (
    <div
      data-testid="project-status-callout"
      data-rdmp-status={rdmpStatus}
      role="alert"
      aria-live="polite"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: style.bg,
        border: `1px solid ${style.border}`,
        borderRadius: '8px',
        marginBottom: '16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <span style={{ fontSize: '18px', color: style.iconColor, marginTop: '2px' }}>
          {style.icon}
        </span>
        <div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: style.titleColor }}>
            {info.title}
          </div>
          <div style={{ fontSize: '13px', color: style.textColor, marginTop: '2px' }}>
            {info.description}
          </div>
          {showAuthorityHint && (
            <div style={{ fontSize: '12px', color: '#b45309', marginTop: '4px' }}>
              RDMP activation requires PI. You have: {userRole}.
            </div>
          )}
        </div>
      </div>
      <button
        onClick={() => navigate(info.actionPath)}
        style={{
          padding: '8px 16px',
          fontSize: '13px',
          fontWeight: 500,
          background: info.type === 'success' ? '#f3f4f6' : style.iconColor,
          color: info.type === 'success' ? '#374151' : '#fff',
          border: info.type === 'success' ? '1px solid #d1d5db' : 'none',
          borderRadius: '6px',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        {info.actionLabel}
      </button>
    </div>
  );
}
