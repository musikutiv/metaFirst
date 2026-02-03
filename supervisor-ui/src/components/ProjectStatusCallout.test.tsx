import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ProjectStatusCallout } from './ProjectStatusCallout';

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
};

describe('ProjectStatusCallout', () => {
  it('shows operational message for ACTIVE status', () => {
    renderWithRouter(
      <ProjectStatusCallout projectId={1} rdmpStatus="ACTIVE" />
    );
    const callout = screen.getByTestId('project-status-callout');
    expect(callout).toHaveAttribute('data-rdmp-status', 'ACTIVE');
    expect(screen.getByText('Project Operational')).toBeInTheDocument();
    expect(screen.getByText(/Data ingestion is enabled/)).toBeInTheDocument();
  });

  it('shows draft pending message for DRAFT status', () => {
    renderWithRouter(
      <ProjectStatusCallout projectId={1} rdmpStatus="DRAFT" canActivate={true} />
    );
    const callout = screen.getByTestId('project-status-callout');
    expect(callout).toHaveAttribute('data-rdmp-status', 'DRAFT');
    expect(screen.getByText('RDMP Draft Pending')).toBeInTheDocument();
    expect(screen.getByText(/Activate the RDMP draft/)).toBeInTheDocument();
    expect(screen.getByText('Activate RDMP')).toBeInTheDocument();
  });

  it('shows PI required message for DRAFT status when canActivate is false', () => {
    renderWithRouter(
      <ProjectStatusCallout projectId={1} rdmpStatus="DRAFT" canActivate={false} />
    );
    expect(screen.getByText(/Ask a PI to activate/)).toBeInTheDocument();
    expect(screen.getByText('View RDMP')).toBeInTheDocument();
  });

  it('shows superseded message for SUPERSEDED status', () => {
    renderWithRouter(
      <ProjectStatusCallout projectId={1} rdmpStatus="SUPERSEDED" />
    );
    const callout = screen.getByTestId('project-status-callout');
    expect(callout).toHaveAttribute('data-rdmp-status', 'SUPERSEDED');
    expect(screen.getByText('All RDMPs Superseded')).toBeInTheDocument();
    expect(screen.getByText(/Create a new RDMP draft/)).toBeInTheDocument();
  });

  it('shows RDMP required message for NONE status', () => {
    renderWithRouter(
      <ProjectStatusCallout projectId={1} rdmpStatus="NONE" />
    );
    const callout = screen.getByTestId('project-status-callout');
    expect(callout).toHaveAttribute('data-rdmp-status', 'NONE');
    expect(screen.getByText('RDMP Required')).toBeInTheDocument();
    expect(screen.getByText(/has no RDMP/)).toBeInTheDocument();
    expect(screen.getByText('Create RDMP')).toBeInTheDocument();
  });

  it('renders action button with correct link', () => {
    renderWithRouter(
      <ProjectStatusCallout projectId={42} rdmpStatus="NONE" />
    );
    const button = screen.getByRole('button', { name: 'Create RDMP' });
    expect(button).toBeInTheDocument();
  });
});
