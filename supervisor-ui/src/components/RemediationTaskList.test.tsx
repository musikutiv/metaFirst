import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RemediationTaskList } from './RemediationTaskList';
import type { RemediationTask } from '../types';

// Mock react-router-dom navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};

const createTask = (overrides: Partial<RemediationTask> = {}): RemediationTask => ({
  id: 'test-task',
  priority: 'recommended',
  title: 'Test Task',
  reason: 'Test reason',
  impact: 'Test impact',
  steps: ['Step 1', 'Step 2'],
  learnMore: 'Test learn more content',
  actionPath: '/test',
  actionLabel: 'Fix It',
  entityType: 'sample',
  ...overrides,
});

describe('RemediationTaskList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('empty state', () => {
    it('shows empty state when no tasks', () => {
      renderWithRouter(<RemediationTaskList tasks={[]} />);

      expect(screen.getByTestId('remediation-empty')).toBeInTheDocument();
      expect(screen.getByText('No remediation tasks')).toBeInTheDocument();
      expect(screen.getByText('Your project data is well-organized.')).toBeInTheDocument();
    });
  });

  describe('advisory header', () => {
    it('shows advisory header explaining non-destructive nature', () => {
      const tasks = [createTask()];
      renderWithRouter(<RemediationTaskList tasks={tasks} />);

      expect(screen.getByTestId('advisory-header')).toBeInTheDocument();
      expect(screen.getByText('Remediation Tasks (Advisory)')).toBeInTheDocument();
      expect(screen.getByText(/non-destructive/i)).toBeInTheDocument();
    });
  });

  describe('task grouping', () => {
    it('groups tasks by priority', () => {
      const tasks = [
        createTask({ id: 'urgent-1', priority: 'urgent', title: 'Urgent Task' }),
        createTask({ id: 'recommended-1', priority: 'recommended', title: 'Recommended Task' }),
        createTask({ id: 'completed-1', priority: 'completed', title: 'Completed Task' }),
      ];

      renderWithRouter(<RemediationTaskList tasks={tasks} />);

      // Check section headings are present
      expect(screen.getByText('Urgent')).toBeInTheDocument();
      expect(screen.getByText('Recommended')).toBeInTheDocument();
      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    it('shows correct count badges for each priority group', () => {
      const tasks = [
        createTask({ id: 'urgent-1', priority: 'urgent' }),
        createTask({ id: 'urgent-2', priority: 'urgent' }),
        createTask({ id: 'recommended-1', priority: 'recommended' }),
      ];

      renderWithRouter(<RemediationTaskList tasks={tasks} />);

      // The urgent section should show badge with "2"
      const urgentSection = screen.getByRole('heading', { name: /Urgent/i }).closest('section');
      expect(urgentSection).toHaveTextContent('2');

      // Summary should show total pending
      expect(screen.getByText('3 tasks pending')).toBeInTheDocument();
    });

    it('only shows sections that have tasks', () => {
      const tasks = [
        createTask({ id: 'recommended-1', priority: 'recommended' }),
      ];

      renderWithRouter(<RemediationTaskList tasks={tasks} />);

      expect(screen.getByText('Recommended')).toBeInTheDocument();
      expect(screen.queryByText('Urgent')).not.toBeInTheDocument();
      expect(screen.queryByText('Completed')).not.toBeInTheDocument();
    });
  });

  describe('task rendering', () => {
    it('renders task with title and reason', () => {
      const task = createTask({
        id: 'test-1',
        title: 'Complete metadata',
        reason: 'Some samples have missing fields',
      });

      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      expect(screen.getByTestId('remediation-task-test-1')).toBeInTheDocument();
      expect(screen.getByText('Complete metadata')).toBeInTheDocument();
      expect(screen.getByText('Some samples have missing fields')).toBeInTheDocument();
    });

    it('shows priority indicator for each task', () => {
      const task = createTask({ id: 'urgent-task', priority: 'urgent' });

      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      const taskElement = screen.getByTestId('remediation-task-urgent-task');
      expect(taskElement).toHaveAttribute('data-priority', 'urgent');
    });
  });

  describe('learn more toggle', () => {
    it('shows learn more button', () => {
      const task = createTask();
      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      expect(screen.getByRole('button', { name: 'Learn more' })).toBeInTheDocument();
    });

    it('expands to show details when clicked', () => {
      const task = createTask({
        id: 'test-1',
        impact: 'This will improve data quality',
        learnMore: 'Detailed explanation here',
        steps: ['First step', 'Second step'],
      });

      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      // Details should not be visible initially
      expect(screen.queryByTestId('task-details-test-1')).not.toBeInTheDocument();

      // Click learn more
      fireEvent.click(screen.getByRole('button', { name: 'Learn more' }));

      // Details should now be visible
      expect(screen.getByTestId('task-details-test-1')).toBeInTheDocument();
      expect(screen.getByText('This will improve data quality')).toBeInTheDocument();
      expect(screen.getByText('Detailed explanation here')).toBeInTheDocument();
      expect(screen.getByText('First step')).toBeInTheDocument();
      expect(screen.getByText('Second step')).toBeInTheDocument();
    });

    it('collapses when clicked again', () => {
      const task = createTask({ id: 'test-1' });

      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      // Expand
      fireEvent.click(screen.getByRole('button', { name: 'Learn more' }));
      expect(screen.getByTestId('task-details-test-1')).toBeInTheDocument();

      // Collapse
      fireEvent.click(screen.getByRole('button', { name: 'Hide details' }));
      expect(screen.queryByTestId('task-details-test-1')).not.toBeInTheDocument();
    });

    it('has accessible aria attributes', () => {
      const task = createTask({ id: 'test-1' });

      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      const button = screen.getByRole('button', { name: 'Learn more' });
      expect(button).toHaveAttribute('aria-expanded', 'false');
      expect(button).toHaveAttribute('aria-controls', 'task-details-test-1');

      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('navigation', () => {
    it('navigates to action path when action button is clicked', () => {
      const task = createTask({
        actionPath: '/rdmps',
        actionLabel: 'Go to RDMPs',
      });

      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      fireEvent.click(screen.getByRole('button', { name: 'Go to RDMPs' }));
      expect(mockNavigate).toHaveBeenCalledWith('/rdmps');
    });

    it('does not show action button for completed tasks', () => {
      const task = createTask({
        priority: 'completed',
        actionLabel: 'Fix It',
      });

      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      expect(screen.queryByRole('button', { name: 'Fix It' })).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('uses semantic section elements with headings', () => {
      const tasks = [
        createTask({ id: 'urgent-1', priority: 'urgent' }),
        createTask({ id: 'recommended-1', priority: 'recommended' }),
      ];

      renderWithRouter(<RemediationTaskList tasks={tasks} />);

      // Sections should have aria-labelledby pointing to headings
      const urgentSection = screen.getByRole('region', { name: /urgent/i });
      expect(urgentSection).toBeInTheDocument();
    });

    it('uses role="list" for task lists', () => {
      const tasks = [createTask()];

      renderWithRouter(<RemediationTaskList tasks={tasks} />);

      expect(screen.getByRole('list')).toBeInTheDocument();
    });

    it('provides priority label for screen readers', () => {
      const task = createTask({ priority: 'urgent' });

      renderWithRouter(<RemediationTaskList tasks={[task]} />);

      expect(screen.getByLabelText('Priority: urgent')).toBeInTheDocument();
    });
  });
});
