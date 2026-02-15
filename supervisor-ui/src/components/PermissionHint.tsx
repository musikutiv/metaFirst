import type { LabRole } from '../types';

type RequiredRole = LabRole | LabRole[];

interface PermissionHintProps {
  requiredRole: RequiredRole;
  /** Current user's role. When provided, shows full authority context. */
  userRole?: LabRole | null;
  /** Supervisor ID for "Manage members" link. */
  supervisorId?: number;
  inline?: boolean;
}

function formatRequiredRoles(requiredRole: RequiredRole): string {
  if (Array.isArray(requiredRole)) {
    if (requiredRole.length === 1) {
      return requiredRole[0];
    }
    // "Steward+" is clearer than "STEWARD or PI"
    const sorted = [...requiredRole].sort(
      (a, b) => roleLevel(a) - roleLevel(b)
    );
    return `${sorted[0]}+`;
  }
  return requiredRole;
}

function roleLevel(role: LabRole): number {
  const levels: Record<LabRole, number> = { PI: 3, STEWARD: 2, RESEARCHER: 1 };
  return levels[role];
}

/**
 * Shows authority context for an action.
 *
 * - Always shows which role is required.
 * - When the user has permission: subtle grey text.
 * - When the user lacks permission: shows their role and a suggestion.
 */
export function PermissionHint({
  requiredRole,
  userRole,
  supervisorId,
  inline = false,
}: PermissionHintProps) {
  const permitted = userRole ? hasPermission(userRole, requiredRole) : true;
  const roleLabel = formatRequiredRoles(requiredRole);

  // Subtle hint when user has permission (or userRole not provided)
  if (permitted) {
    const text = `Needs ${roleLabel} role`;
    if (inline) {
      return (
        <span
          data-testid="permission-hint"
          style={{
            fontSize: '12px',
            color: '#9ca3af',
            marginLeft: '8px',
          }}
        >
          ({text})
        </span>
      );
    }
    return (
      <div
        data-testid="permission-hint"
        style={{
          fontSize: '12px',
          color: '#9ca3af',
          marginTop: '4px',
        }}
      >
        {text}
      </div>
    );
  }

  // User lacks permission — show their role and action guidance.
  const membersPath = supervisorId
    ? `/supervisors/${supervisorId}/members`
    : null;

  if (inline) {
    return (
      <span
        data-testid="permission-hint"
        data-denied="true"
        style={{
          fontSize: '12px',
          color: '#b45309',
          marginLeft: '8px',
        }}
      >
        (Needs {roleLabel} role — you have {userRole}.{' '}
        {membersPath ? (
          <a
            href={membersPath}
            style={{ color: '#b45309', textDecoration: 'underline' }}
            onClick={(e) => {
              // Let React Router handle if available
              e.preventDefault();
              window.location.href = membersPath;
            }}
          >
            Request role change
          </a>
        ) : (
          'Request role change from PI.'
        )}
        )
      </span>
    );
  }

  return (
    <div
      data-testid="permission-hint"
      data-denied="true"
      style={{
        fontSize: '12px',
        color: '#b45309',
        marginTop: '4px',
      }}
    >
      Needs {roleLabel} role — you have {userRole}.{' '}
      {membersPath ? (
        <a
          href={membersPath}
          style={{ color: '#b45309', textDecoration: 'underline' }}
          onClick={(e) => {
            e.preventDefault();
            window.location.href = membersPath;
          }}
        >
          Request role change
        </a>
      ) : (
        'Request role change from PI.'
      )}
    </div>
  );
}

/**
 * Helper to check if a user's role meets the required role(s).
 */
export function hasPermission(userRole: LabRole | null, requiredRole: RequiredRole): boolean {
  if (!userRole) return false;

  const roleHierarchy: Record<LabRole, number> = {
    PI: 3,
    STEWARD: 2,
    RESEARCHER: 1,
  };

  const userLevel = roleHierarchy[userRole];

  if (Array.isArray(requiredRole)) {
    // User needs to have at least the level of the lowest required role
    const minRequiredLevel = Math.min(...requiredRole.map(r => roleHierarchy[r]));
    return userLevel >= minRequiredLevel;
  }

  return userLevel >= roleHierarchy[requiredRole];
}
