import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PermissionHint, hasPermission } from './PermissionHint';

describe('PermissionHint', () => {
  it('renders single role requirement', () => {
    render(<PermissionHint requiredRole="PI" />);
    const hint = screen.getByTestId('permission-hint');
    expect(hint).toHaveTextContent('Requires PI');
  });

  it('renders multiple role requirements as "Role+"', () => {
    render(<PermissionHint requiredRole={['STEWARD', 'PI']} />);
    const hint = screen.getByTestId('permission-hint');
    expect(hint).toHaveTextContent('Requires STEWARD+');
  });

  it('renders single role from array without "+"', () => {
    render(<PermissionHint requiredRole={['PI']} />);
    const hint = screen.getByTestId('permission-hint');
    expect(hint).toHaveTextContent('Requires PI');
  });

  it('renders in inline mode with parentheses', () => {
    render(<PermissionHint requiredRole="PI" inline />);
    const hint = screen.getByTestId('permission-hint');
    expect(hint).toHaveTextContent('(Requires PI)');
  });

  it('renders in block mode without parentheses', () => {
    render(<PermissionHint requiredRole="PI" inline={false} />);
    const hint = screen.getByTestId('permission-hint');
    expect(hint).toHaveTextContent('Requires PI');
    expect(hint.textContent).not.toContain('(');
  });

  describe('with userRole', () => {
    it('shows subtle hint when user has permission', () => {
      render(<PermissionHint requiredRole="PI" userRole="PI" />);
      const hint = screen.getByTestId('permission-hint');
      expect(hint).toHaveTextContent('Requires PI');
      expect(hint).not.toHaveAttribute('data-denied');
    });

    it('shows denied state when user lacks permission', () => {
      render(<PermissionHint requiredRole="PI" userRole="RESEARCHER" />);
      const hint = screen.getByTestId('permission-hint');
      expect(hint).toHaveTextContent('Requires PI');
      expect(hint).toHaveTextContent('you have RESEARCHER');
      expect(hint).toHaveAttribute('data-denied', 'true');
    });

    it('shows denied state for Steward when PI required', () => {
      render(<PermissionHint requiredRole="PI" userRole="STEWARD" />);
      const hint = screen.getByTestId('permission-hint');
      expect(hint).toHaveTextContent('you have STEWARD');
      expect(hint).toHaveAttribute('data-denied', 'true');
    });

    it('shows "Request role change" link when supervisorId provided', () => {
      render(
        <PermissionHint requiredRole="PI" userRole="RESEARCHER" supervisorId={42} />
      );
      const hint = screen.getByTestId('permission-hint');
      const link = hint.querySelector('a');
      expect(link).toHaveAttribute('href', '/supervisors/42/members');
      expect(link).toHaveTextContent('Request role change');
    });

    it('shows fallback text when supervisorId not provided', () => {
      render(<PermissionHint requiredRole="PI" userRole="RESEARCHER" />);
      const hint = screen.getByTestId('permission-hint');
      expect(hint).toHaveTextContent('Request role change from PI.');
    });
  });
});

describe('hasPermission', () => {
  it('returns false when userRole is null', () => {
    expect(hasPermission(null, 'PI')).toBe(false);
    expect(hasPermission(null, 'STEWARD')).toBe(false);
    expect(hasPermission(null, 'RESEARCHER')).toBe(false);
  });

  it('PI has permission for all roles', () => {
    expect(hasPermission('PI', 'PI')).toBe(true);
    expect(hasPermission('PI', 'STEWARD')).toBe(true);
    expect(hasPermission('PI', 'RESEARCHER')).toBe(true);
  });

  it('STEWARD has permission for STEWARD and RESEARCHER', () => {
    expect(hasPermission('STEWARD', 'PI')).toBe(false);
    expect(hasPermission('STEWARD', 'STEWARD')).toBe(true);
    expect(hasPermission('STEWARD', 'RESEARCHER')).toBe(true);
  });

  it('RESEARCHER only has permission for RESEARCHER', () => {
    expect(hasPermission('RESEARCHER', 'PI')).toBe(false);
    expect(hasPermission('RESEARCHER', 'STEWARD')).toBe(false);
    expect(hasPermission('RESEARCHER', 'RESEARCHER')).toBe(true);
  });

  it('handles array of required roles (user needs at least lowest level)', () => {
    // PI can access actions requiring STEWARD or PI
    expect(hasPermission('PI', ['STEWARD', 'PI'])).toBe(true);
    // STEWARD can access actions requiring STEWARD or PI (has STEWARD level)
    expect(hasPermission('STEWARD', ['STEWARD', 'PI'])).toBe(true);
    // RESEARCHER cannot access actions requiring STEWARD or PI
    expect(hasPermission('RESEARCHER', ['STEWARD', 'PI'])).toBe(false);
  });

  it('handles single role in array', () => {
    expect(hasPermission('PI', ['PI'])).toBe(true);
    expect(hasPermission('STEWARD', ['PI'])).toBe(false);
  });
});
