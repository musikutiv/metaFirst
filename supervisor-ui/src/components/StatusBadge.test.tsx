import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge, getRDMPStatus, getRDMPStatusFromActive } from './StatusBadge';

describe('StatusBadge', () => {
  describe('rendering', () => {
    it('renders NONE status with correct label and icon', () => {
      render(<StatusBadge type="rdmp" status="NONE" />);
      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent('No RDMP');
      expect(badge).toHaveAttribute('data-status', 'NONE');
    });

    it('renders DRAFT status with correct label and icon', () => {
      render(<StatusBadge type="rdmp" status="DRAFT" />);
      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent('Draft');
      expect(badge).toHaveAttribute('data-status', 'DRAFT');
    });

    it('renders ACTIVE status with correct label and icon', () => {
      render(<StatusBadge type="rdmp" status="ACTIVE" />);
      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent('Active');
      expect(badge).toHaveAttribute('data-status', 'ACTIVE');
    });

    it('renders SUPERSEDED status with correct label and icon', () => {
      render(<StatusBadge type="rdmp" status="SUPERSEDED" />);
      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent('Superseded');
      expect(badge).toHaveAttribute('data-status', 'SUPERSEDED');
    });

    it('supports small size variant', () => {
      render(<StatusBadge type="rdmp" status="ACTIVE" size="small" />);
      const badge = screen.getByTestId('status-badge');
      expect(badge).toBeInTheDocument();
    });
  });
});

describe('getRDMPStatus', () => {
  it('returns NONE for null or undefined', () => {
    expect(getRDMPStatus(null)).toBe('NONE');
    expect(getRDMPStatus(undefined)).toBe('NONE');
  });

  it('returns NONE for empty array', () => {
    expect(getRDMPStatus([])).toBe('NONE');
  });

  it('returns ACTIVE when there is an active RDMP', () => {
    const rdmps = [
      { status: 'DRAFT' as const },
      { status: 'ACTIVE' as const },
    ];
    expect(getRDMPStatus(rdmps)).toBe('ACTIVE');
  });

  it('returns DRAFT when there are only drafts', () => {
    const rdmps = [
      { status: 'DRAFT' as const },
      { status: 'DRAFT' as const },
    ];
    expect(getRDMPStatus(rdmps)).toBe('DRAFT');
  });

  it('returns SUPERSEDED when all RDMPs are superseded', () => {
    const rdmps = [
      { status: 'SUPERSEDED' as const },
      { status: 'SUPERSEDED' as const },
    ];
    expect(getRDMPStatus(rdmps)).toBe('SUPERSEDED');
  });

  it('returns DRAFT when there are drafts and superseded', () => {
    const rdmps = [
      { status: 'SUPERSEDED' as const },
      { status: 'DRAFT' as const },
    ];
    expect(getRDMPStatus(rdmps)).toBe('DRAFT');
  });
});

describe('getRDMPStatusFromActive', () => {
  it('returns NONE when no active RDMP and no draft', () => {
    expect(getRDMPStatusFromActive(null)).toBe('NONE');
    expect(getRDMPStatusFromActive(undefined)).toBe('NONE');
  });

  it('returns ACTIVE when active RDMP exists', () => {
    expect(getRDMPStatusFromActive({ status: 'ACTIVE' })).toBe('ACTIVE');
  });

  it('returns DRAFT when hasDraft is true', () => {
    expect(getRDMPStatusFromActive(null, true)).toBe('DRAFT');
  });

  it('returns SUPERSEDED when RDMP is superseded', () => {
    expect(getRDMPStatusFromActive({ status: 'SUPERSEDED' })).toBe('SUPERSEDED');
  });
});
