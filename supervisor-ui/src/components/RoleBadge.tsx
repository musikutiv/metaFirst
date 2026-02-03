import type { LabRole } from '../types';

interface RoleBadgeProps {
  role: LabRole | null;
  size?: 'small' | 'medium';
}

const roleColors: Record<LabRole, { bg: string; text: string }> = {
  PI: { bg: '#dbeafe', text: '#1e40af' },
  STEWARD: { bg: '#dcfce7', text: '#166534' },
  RESEARCHER: { bg: '#f3f4f6', text: '#374151' },
};

export function RoleBadge({ role, size = 'medium' }: RoleBadgeProps) {
  if (!role) {
    return null;
  }

  const colors = roleColors[role];
  const isSmall = size === 'small';

  return (
    <span
      data-testid="role-badge"
      data-role={role}
      style={{
        display: 'inline-block',
        padding: isSmall ? '2px 6px' : '4px 10px',
        fontSize: isSmall ? '11px' : '12px',
        fontWeight: 600,
        background: colors.bg,
        color: colors.text,
        borderRadius: '9999px',
        whiteSpace: 'nowrap',
      }}
    >
      {role}
    </span>
  );
}
