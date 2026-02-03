import { RoleBadge } from './RoleBadge';
import type { LabRole } from '../types';

interface LabContextProps {
  labName: string | null;
  userRole: LabRole | null;
}

/**
 * Shows the current lab context and user's role.
 * Displayed in the header when a project is selected.
 */
export function LabContext({ labName, userRole }: LabContextProps) {
  if (!labName) {
    return null;
  }

  return (
    <div
      data-testid="lab-context"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 12px',
        background: '#f9fafb',
        borderRadius: '6px',
        fontSize: '13px',
      }}
    >
      <span style={{ color: '#6b7280' }}>Lab:</span>
      <span style={{ fontWeight: 500, color: '#374151' }}>{labName}</span>
      {userRole && <RoleBadge role={userRole} size="small" />}
    </div>
  );
}
