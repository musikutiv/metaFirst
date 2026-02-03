import type { LabRole } from '../types';

type RequiredRole = LabRole | LabRole[];

interface PermissionHintProps {
  requiredRole: RequiredRole;
  inline?: boolean;
}

function formatRequiredRoles(requiredRole: RequiredRole): string {
  if (Array.isArray(requiredRole)) {
    if (requiredRole.length === 1) {
      return requiredRole[0];
    }
    return requiredRole.join(' or ');
  }
  return requiredRole;
}

/**
 * Shows a hint about which role(s) are required for an action.
 * Use this next to buttons or in disabled states.
 */
export function PermissionHint({ requiredRole, inline = false }: PermissionHintProps) {
  const text = `Requires: ${formatRequiredRoles(requiredRole)}`;

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
