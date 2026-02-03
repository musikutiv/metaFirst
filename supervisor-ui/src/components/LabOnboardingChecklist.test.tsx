import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LabOnboardingChecklist } from './LabOnboardingChecklist';
import { apiClient } from '../api/client';

// Mock the API client
vi.mock('../api/client', () => ({
  apiClient: {
    getSupervisorMembers: vi.fn(),
    getProjects: vi.fn(),
    listRDMPVersions: vi.fn(),
    getStorageRoots: vi.fn(),
  },
}));

// Mock react-router-dom navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};

// Helper to create valid mock data
const createMember = (overrides: { role: 'PI' | 'STEWARD' | 'RESEARCHER' }) => ({
  user_id: 1,
  username: 'testuser',
  display_name: 'Test User',
  role: overrides.role,
});

const createProject = (overrides: { id: number; name: string; supervisor_id: number }) => ({
  id: overrides.id,
  name: overrides.name,
  supervisor_id: overrides.supervisor_id,
  description: null,
  created_at: '2024-01-01T00:00:00Z',
  created_by: 1,
  is_active: true,
  sample_id_rule_type: null,
  sample_id_regex: null,
});

const createRDMP = (overrides: { id: number; project_id: number; status: 'DRAFT' | 'ACTIVE' | 'SUPERSEDED' }) => ({
  id: overrides.id,
  project_id: overrides.project_id,
  title: 'Test RDMP',
  status: overrides.status,
  version: 1,
  content: {},
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  created_by: 1,
  approved_by: null,
});

const createStorageRoot = (overrides: { id: number; project_id: number }) => ({
  id: overrides.id,
  project_id: overrides.project_id,
  name: 'Main Storage',
  description: null,
  created_at: '2024-01-01T00:00:00Z',
});

describe('LabOnboardingChecklist', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
  });

  afterEach(() => {
    localStorageMock.clear();
  });

  describe('visibility based on role', () => {
    it('renders for PI role', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lab-onboarding-checklist')).toBeInTheDocument();
      });
    });

    it('renders for STEWARD role', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'STEWARD' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="STEWARD"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lab-onboarding-checklist')).toBeInTheDocument();
      });
    });

    it('does not render for RESEARCHER role', async () => {
      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="RESEARCHER"
        />
      );

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByTestId('lab-onboarding-checklist')).not.toBeInTheDocument();
      });
    });

    it('does not render for null role', async () => {
      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole={null}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('lab-onboarding-checklist')).not.toBeInTheDocument();
      });
    });
  });

  describe('checklist state derivation', () => {
    it('shows all items incomplete when lab is empty', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-pi-steward')).toHaveAttribute('data-done', 'false');
        expect(screen.getByTestId('checklist-item-project')).toHaveAttribute('data-done', 'false');
        expect(screen.getByTestId('checklist-item-rdmp')).toHaveAttribute('data-done', 'false');
        expect(screen.getByTestId('checklist-item-ingestor')).toHaveAttribute('data-done', 'false');
      });

      expect(screen.getByText('0 of 4 complete')).toBeInTheDocument();
    });

    it('marks PI/Steward as complete when lab has PI', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-pi-steward')).toHaveAttribute('data-done', 'true');
      });

      expect(screen.getByText('1 of 4 complete')).toBeInTheDocument();
    });

    it('marks PI/Steward as complete when lab has STEWARD', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'STEWARD' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="STEWARD"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-pi-steward')).toHaveAttribute('data-done', 'true');
      });
    });

    it('marks project as complete when lab has a project', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([
        createProject({ id: 1, name: 'Project A', supervisor_id: 1 }),
      ]);
      vi.mocked(apiClient.listRDMPVersions).mockResolvedValue([]);
      vi.mocked(apiClient.getStorageRoots).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-project')).toHaveAttribute('data-done', 'true');
      });

      expect(screen.getByText('2 of 4 complete')).toBeInTheDocument();
    });

    it('marks RDMP as complete when project has DRAFT RDMP', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([
        createProject({ id: 1, name: 'Project A', supervisor_id: 1 }),
      ]);
      vi.mocked(apiClient.listRDMPVersions).mockResolvedValue([
        createRDMP({ id: 1, project_id: 1, status: 'DRAFT' }),
      ]);
      vi.mocked(apiClient.getStorageRoots).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-rdmp')).toHaveAttribute('data-done', 'true');
      });

      expect(screen.getByText('3 of 4 complete')).toBeInTheDocument();
    });

    it('marks RDMP as complete when project has ACTIVE RDMP', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([
        createProject({ id: 1, name: 'Project A', supervisor_id: 1 }),
      ]);
      vi.mocked(apiClient.listRDMPVersions).mockResolvedValue([
        createRDMP({ id: 1, project_id: 1, status: 'ACTIVE' }),
      ]);
      vi.mocked(apiClient.getStorageRoots).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-rdmp')).toHaveAttribute('data-done', 'true');
      });
    });

    it('does not mark RDMP complete when only SUPERSEDED', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([
        createProject({ id: 1, name: 'Project A', supervisor_id: 1 }),
      ]);
      vi.mocked(apiClient.listRDMPVersions).mockResolvedValue([
        createRDMP({ id: 1, project_id: 1, status: 'SUPERSEDED' }),
      ]);
      vi.mocked(apiClient.getStorageRoots).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-rdmp')).toHaveAttribute('data-done', 'false');
      });
    });

    it('marks ingestor as complete when project has storage root', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([
        createProject({ id: 1, name: 'Project A', supervisor_id: 1 }),
      ]);
      vi.mocked(apiClient.listRDMPVersions).mockResolvedValue([
        createRDMP({ id: 1, project_id: 1, status: 'ACTIVE' }),
      ]);
      vi.mocked(apiClient.getStorageRoots).mockResolvedValue([
        createStorageRoot({ id: 1, project_id: 1 }),
      ]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-ingestor')).toHaveAttribute('data-done', 'true');
      });

      expect(screen.getByText('4 of 4 complete')).toBeInTheDocument();
    });
  });

  describe('action button navigation', () => {
    it('navigates to members page when clicking Manage Members', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={42}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('checklist-item-pi-steward')).toBeInTheDocument();
      });

      const manageButton = screen.getByRole('button', { name: 'Manage Members' });
      fireEvent.click(manageButton);

      expect(mockNavigate).toHaveBeenCalledWith('/supervisors/42/members');
    });

    it('navigates to roles page when clicking help link', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByText('What is required to get started?')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('What is required to get started?'));
      expect(mockNavigate).toHaveBeenCalledWith('/roles');
    });
  });

  describe('dismissal behavior', () => {
    it('shows dismiss button when all items are complete', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([
        createProject({ id: 1, name: 'Project A', supervisor_id: 1 }),
      ]);
      vi.mocked(apiClient.listRDMPVersions).mockResolvedValue([
        createRDMP({ id: 1, project_id: 1, status: 'ACTIVE' }),
      ]);
      vi.mocked(apiClient.getStorageRoots).mockResolvedValue([
        createStorageRoot({ id: 1, project_id: 1 }),
      ]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Dismiss checklist' })).toBeInTheDocument();
      });
    });

    it('does not show dismiss button when items are incomplete', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('lab-onboarding-checklist')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: 'Dismiss checklist' })).not.toBeInTheDocument();
    });

    it('hides checklist when dismiss is clicked', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([
        createProject({ id: 1, name: 'Project A', supervisor_id: 1 }),
      ]);
      vi.mocked(apiClient.listRDMPVersions).mockResolvedValue([
        createRDMP({ id: 1, project_id: 1, status: 'ACTIVE' }),
      ]);
      vi.mocked(apiClient.getStorageRoots).mockResolvedValue([
        createStorageRoot({ id: 1, project_id: 1 }),
      ]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Dismiss checklist' })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: 'Dismiss checklist' }));

      await waitFor(() => {
        expect(screen.queryByTestId('lab-onboarding-checklist')).not.toBeInTheDocument();
      });
    });

    it('persists dismissal in localStorage', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([
        createMember({ role: 'PI' }),
      ]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([
        createProject({ id: 1, name: 'Project A', supervisor_id: 1 }),
      ]);
      vi.mocked(apiClient.listRDMPVersions).mockResolvedValue([
        createRDMP({ id: 1, project_id: 1, status: 'ACTIVE' }),
      ]);
      vi.mocked(apiClient.getStorageRoots).mockResolvedValue([
        createStorageRoot({ id: 1, project_id: 1 }),
      ]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Test Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Dismiss checklist' })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: 'Dismiss checklist' }));

      expect(localStorage.getItem('lab-onboarding-dismissed-1')).toBe('true');
    });
  });

  describe('title displays lab name', () => {
    it('shows lab name in title', async () => {
      vi.mocked(apiClient.getSupervisorMembers).mockResolvedValue([]);
      vi.mocked(apiClient.getProjects).mockResolvedValue([]);

      renderWithRouter(
        <LabOnboardingChecklist
          supervisorId={1}
          supervisorName="Genomics Research Lab"
          userRole="PI"
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Get Started with Genomics Research Lab')).toBeInTheDocument();
      });
    });
  });
});
