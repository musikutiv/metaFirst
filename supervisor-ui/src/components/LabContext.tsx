import { useNavigate } from 'react-router-dom';
import { RoleBadge } from './RoleBadge';
import type { LabRole } from '../types';

interface LabContextProps {
  labName: string | null;
  userRole: LabRole | null;
  supervisorId: number | null;
}

/**
 * Shows the current lab context and user's role.
 * Displayed in the header when a project is selected.
 */
export function LabContext({ labName, userRole, supervisorId }: LabContextProps) {
  const navigate = useNavigate();

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
      {supervisorId && (
        <div style={{ display: 'flex', gap: '4px', marginLeft: '8px', paddingLeft: '8px', borderLeft: '1px solid #e5e7eb' }}>
          <button
            style={{
              padding: '2px 6px',
              fontSize: '11px',
              background: 'transparent',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              cursor: 'pointer',
              color: '#6b7280',
            }}
            onClick={() => navigate(`/supervisors/${supervisorId}/members`)}
          >
            Members
          </button>
          <button
            style={{
              padding: '2px 6px',
              fontSize: '11px',
              background: 'transparent',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              cursor: 'pointer',
              color: '#6b7280',
            }}
            onClick={() => navigate(`/supervisors/${supervisorId}/activity`)}
          >
            Activity
          </button>
        </div>
      )}
    </div>
  );
}
