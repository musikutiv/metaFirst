import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NeedsAttentionPanel } from './NeedsAttentionPanel';
import type { NeedsAttentionItem, Project } from '../types';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('NeedsAttentionPanel', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('renders nothing when items array is empty', () => {
    renderWithRouter(<NeedsAttentionPanel items={[]} />);
    expect(screen.queryByTestId('needs-attention-panel')).not.toBeInTheDocument();
  });

  it('renders panel with items', () => {
    const items: NeedsAttentionItem[] = [
      {
        type: 'project_without_rdmp',
        severity: 'info',
        count: 2,
        entity_type: 'project',
        entity_ids: [1, 2],
        message: '2 project(s) have no RDMP.',
      },
    ];

    renderWithRouter(<NeedsAttentionPanel items={items} />);

    expect(screen.getByTestId('needs-attention-panel')).toBeInTheDocument();
    expect(screen.getByText('Needs Attention')).toBeInTheDocument();
    expect(screen.getByText('2 project(s) have no RDMP.')).toBeInTheDocument();
  });

  it('renders severity-specific styling for high severity', () => {
    const items: NeedsAttentionItem[] = [
      {
        type: 'project_operational_without_active_rdmp',
        severity: 'high',
        count: 1,
        entity_type: 'project',
        entity_ids: [1],
        message: '1 operational project(s) lack an active RDMP.',
      },
    ];

    renderWithRouter(<NeedsAttentionPanel items={items} />);

    const item = screen.getByTestId('attention-item-project_operational_without_active_rdmp');
    expect(item).toBeInTheDocument();
  });

  it('shows project name when provided in projectsById', () => {
    const items: NeedsAttentionItem[] = [
      {
        type: 'project_without_rdmp',
        severity: 'info',
        count: 1,
        entity_type: 'project',
        entity_ids: [42],
        message: '1 project(s) have no RDMP.',
      },
    ];

    const projectsById = new Map<number, Project>([
      [42, { id: 42, name: 'Test Project', description: null, created_at: '', created_by: 1, supervisor_id: 1, is_active: true, sample_id_rule_type: null, sample_id_regex: null }],
    ]);

    renderWithRouter(<NeedsAttentionPanel items={items} projectsById={projectsById} />);

    expect(screen.getByText('Project: Test Project')).toBeInTheDocument();
  });

  describe('deep links', () => {
    it('navigates to /rdmps for project_operational_without_active_rdmp', () => {
      const onSelectProject = vi.fn();
      const items: NeedsAttentionItem[] = [
        {
          type: 'project_operational_without_active_rdmp',
          severity: 'high',
          count: 1,
          entity_type: 'project',
          entity_ids: [123],
          message: 'Test message',
        },
      ];

      renderWithRouter(
        <NeedsAttentionPanel items={items} onSelectProject={onSelectProject} />
      );

      const button = screen.getByText('Go to RDMP');
      fireEvent.click(button);

      expect(onSelectProject).toHaveBeenCalledWith(123);
      expect(mockNavigate).toHaveBeenCalledWith('/rdmps');
    });

    it('navigates to /tasks for unresolved_remediation_high', () => {
      const onSelectProject = vi.fn();
      const items: NeedsAttentionItem[] = [
        {
          type: 'unresolved_remediation_high',
          severity: 'high',
          count: 3,
          entity_type: 'project',
          entity_ids: [456],
          message: '3 high-severity remediation task(s) unresolved.',
        },
      ];

      renderWithRouter(
        <NeedsAttentionPanel items={items} onSelectProject={onSelectProject} />
      );

      const button = screen.getByText('View Tasks');
      fireEvent.click(button);

      expect(onSelectProject).toHaveBeenCalledWith(456);
      expect(mockNavigate).toHaveBeenCalledWith('/tasks');
    });

    it('navigates to /rdmps for project_with_superseded_rdmp', () => {
      const items: NeedsAttentionItem[] = [
        {
          type: 'project_with_superseded_rdmp',
          severity: 'warning',
          count: 1,
          entity_type: 'project',
          entity_ids: [789],
          message: '1 project(s) have only superseded RDMPs.',
        },
      ];

      renderWithRouter(<NeedsAttentionPanel items={items} />);

      const button = screen.getByText('Go to RDMP');
      expect(button).toBeInTheDocument();
    });
  });

  it('shows count info for multiple affected items', () => {
    const items: NeedsAttentionItem[] = [
      {
        type: 'project_without_rdmp',
        severity: 'info',
        count: 5,
        entity_type: 'project',
        entity_ids: [1, 2, 3],
        message: '5 project(s) have no RDMP.',
      },
    ];

    renderWithRouter(<NeedsAttentionPanel items={items} />);

    expect(screen.getByText(/Affects 5 projects/)).toBeInTheDocument();
    expect(screen.getByText(/showing first 3/)).toBeInTheDocument();
  });
});
