import type { Project } from '../types';

interface ProjectSelectorProps {
  projects: Project[];
  selectedProjectId: number | null;
  onSelect: (projectId: number) => void;
  loading: boolean;
}

export function ProjectSelector({
  projects,
  selectedProjectId,
  onSelect,
  loading,
}: ProjectSelectorProps) {
  if (loading) {
    return <div style={styles.loading}>Loading projects...</div>;
  }

  if (projects.length === 0) {
    return <div style={styles.empty}>No projects available</div>;
  }

  return (
    <div style={styles.container}>
      <label style={styles.label}>Select Project:</label>
      <select
        value={selectedProjectId ?? ''}
        onChange={(e) => onSelect(Number(e.target.value))}
        style={styles.select}
      >
        <option value="" disabled>
          Choose a project...
        </option>
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.name}
          </option>
        ))}
      </select>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  label: {
    fontWeight: 500,
    color: '#374151',
  },
  select: {
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #ddd',
    borderRadius: '6px',
    background: 'white',
    minWidth: '250px',
    cursor: 'pointer',
  },
  loading: {
    color: '#666',
    fontStyle: 'italic',
  },
  empty: {
    color: '#999',
  },
};
