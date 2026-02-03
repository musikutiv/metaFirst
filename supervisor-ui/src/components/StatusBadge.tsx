/**
 * StatusBadge - Consistent badges for project and RDMP status.
 * Uses text + icon, not color alone, for accessibility.
 */

export type RDMPStatus = 'NONE' | 'DRAFT' | 'ACTIVE' | 'SUPERSEDED';

interface StatusBadgeProps {
  type: 'rdmp';
  status: RDMPStatus;
  size?: 'small' | 'medium';
}

const rdmpConfig: Record<RDMPStatus, { label: string; icon: string; bg: string; color: string; border: string }> = {
  NONE: {
    label: 'No RDMP',
    icon: '\u25CB', // ○ empty circle
    bg: '#fef2f2',
    color: '#991b1b',
    border: '#fecaca',
  },
  DRAFT: {
    label: 'Draft',
    icon: '\u270E', // ✎ pencil
    bg: '#fef3c7',
    color: '#92400e',
    border: '#fde68a',
  },
  ACTIVE: {
    label: 'Active',
    icon: '\u2713', // ✓ checkmark
    bg: '#d1fae5',
    color: '#065f46',
    border: '#a7f3d0',
  },
  SUPERSEDED: {
    label: 'Superseded',
    icon: '\u21B6', // ↶ archive
    bg: '#f3f4f6',
    color: '#6b7280',
    border: '#e5e7eb',
  },
};

export function StatusBadge({ type, status, size = 'medium' }: StatusBadgeProps) {
  const config = rdmpConfig[status];
  const isSmall = size === 'small';

  return (
    <span
      data-testid="status-badge"
      data-type={type}
      data-status={status}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: isSmall ? '3px' : '4px',
        padding: isSmall ? '2px 6px' : '3px 8px',
        fontSize: isSmall ? '11px' : '12px',
        fontWeight: 500,
        background: config.bg,
        color: config.color,
        border: `1px solid ${config.border}`,
        borderRadius: '4px',
        whiteSpace: 'nowrap',
      }}
    >
      <span style={{ fontSize: isSmall ? '10px' : '11px' }}>{config.icon}</span>
      {config.label}
    </span>
  );
}

/**
 * Helper to determine RDMP status from list of RDMPVersions.
 */
export function getRDMPStatus(rdmps: Array<{ status: 'DRAFT' | 'ACTIVE' | 'SUPERSEDED' }> | null | undefined): RDMPStatus {
  if (!rdmps || rdmps.length === 0) return 'NONE';

  // Check for active first
  if (rdmps.some(r => r.status === 'ACTIVE')) return 'ACTIVE';

  // Check for drafts
  if (rdmps.some(r => r.status === 'DRAFT')) return 'DRAFT';

  // All superseded
  return 'SUPERSEDED';
}

/**
 * Helper to determine RDMP status from a single active RDMP or null.
 */
export function getRDMPStatusFromActive(activeRdmp: { status: string } | null | undefined, hasDraft?: boolean): RDMPStatus {
  if (activeRdmp?.status === 'ACTIVE') return 'ACTIVE';
  if (hasDraft) return 'DRAFT';
  if (activeRdmp?.status === 'SUPERSEDED') return 'SUPERSEDED';
  return 'NONE';
}
