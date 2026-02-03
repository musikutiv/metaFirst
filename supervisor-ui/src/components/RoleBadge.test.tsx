import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoleBadge } from './RoleBadge';

describe('RoleBadge', () => {
  it('renders PI role with correct styling', () => {
    render(<RoleBadge role="PI" />);
    const badge = screen.getByTestId('role-badge');
    expect(badge).toHaveTextContent('PI');
    expect(badge).toHaveAttribute('data-role', 'PI');
  });

  it('renders STEWARD role with correct styling', () => {
    render(<RoleBadge role="STEWARD" />);
    const badge = screen.getByTestId('role-badge');
    expect(badge).toHaveTextContent('STEWARD');
    expect(badge).toHaveAttribute('data-role', 'STEWARD');
  });

  it('renders RESEARCHER role with correct styling', () => {
    render(<RoleBadge role="RESEARCHER" />);
    const badge = screen.getByTestId('role-badge');
    expect(badge).toHaveTextContent('RESEARCHER');
    expect(badge).toHaveAttribute('data-role', 'RESEARCHER');
  });

  it('renders null role gracefully', () => {
    render(<RoleBadge role={null} />);
    const badge = screen.queryByTestId('role-badge');
    expect(badge).toBeNull();
  });

  it('supports small size variant', () => {
    render(<RoleBadge role="PI" size="small" />);
    const badge = screen.getByTestId('role-badge');
    expect(badge).toBeInTheDocument();
  });

  it('supports medium size variant (default)', () => {
    render(<RoleBadge role="PI" size="medium" />);
    const badge = screen.getByTestId('role-badge');
    expect(badge).toBeInTheDocument();
  });
});
