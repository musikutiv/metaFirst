import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { Project, Supervisor } from '../types';

interface ProjectWithDetails extends Project {
  supervisorName?: string;
  activeRdmpTitle?: string | null;
  userRole?: string;
}

interface ProjectsOverviewProps {
  onSelectProject: (projectId: number) => void;
}

export function ProjectsOverview({ onSelectProject }: ProjectsOverviewProps) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectWithDetails[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Load projects and supervisors
      const [projectsData, supervisorsData] = await Promise.all([
        apiClient.getProjects(),
        apiClient.getSupervisors(),
      ]);

      // Create supervisor lookup
      const supervisorMap = new Map<number, Supervisor>();
      supervisorsData.forEach((s) => supervisorMap.set(s.id, s));

      // For each project, get active RDMP and enrich with supervisor info
      const enrichedProjects: ProjectWithDetails[] = await Promise.all(
        projectsData.map(async (project) => {
          const supervisor = supervisorMap.get(project.supervisor_id);

          // Get active RDMP for this project
          let activeRdmpTitle: string | null = null;
          try {
            const activeRdmp = await apiClient.getActiveRDMP(project.id);
            activeRdmpTitle = activeRdmp?.title || null;
          } catch {
            // Ignore errors - project might not have an active RDMP
          }

          // Get user's role from supervisor members (if available)
          let userRole: string | undefined;
          if (supervisor) {
            try {
              const members = await apiClient.getSupervisorMembers(supervisor.id);
              // We don't have current user ID here, but the API returns only
              // members for supervisors the user belongs to, so any member data
              // indicates access. For role display, we'd need the user ID.
              // For now, show the first role found (supervisor-scoped)
              if (members.length > 0) {
                // Find current user's role - this is a simplification
                // In a real app, we'd pass the user ID or get it from context
                userRole = members[0]?.role;
              }
            } catch {
              // Ignore - user might not have access to list members
            }
          }

          return {
            ...project,
            supervisorName: supervisor?.name,
            activeRdmpTitle,
            userRole,
          };
        })
      );

      setProjects(enrichedProjects);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const filteredProjects = projects.filter((p) => {
    const term = searchTerm.toLowerCase();
    return (
      p.name.toLowerCase().includes(term) ||
      (p.description?.toLowerCase().includes(term)) ||
      (p.supervisorName?.toLowerCase().includes(term))
    );
  });

  const handleManageMembers = (supervisorId: number) => {
    navigate(`/supervisors/${supervisorId}/members`);
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <p style={styles.loading}>Loading projects...</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.title}>Projects Overview</h2>
        <p style={styles.subtitle}>
          All projects you have access to with their status
        </p>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.searchBar}>
        <input
          type="text"
          placeholder="Search projects..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={styles.searchInput}
        />
      </div>

      <div style={styles.projectsGrid}>
        {filteredProjects.length === 0 ? (
          <p style={styles.noProjects}>No projects found</p>
        ) : (
          filteredProjects.map((project) => (
            <div key={project.id} style={styles.projectCard}>
              <div style={styles.cardHeader}>
                <h3 style={styles.projectName}>{project.name}</h3>
                {project.activeRdmpTitle ? (
                  <span style={styles.activeBadge}>Active RDMP</span>
                ) : (
                  <span style={styles.inactiveBadge}>No Active RDMP</span>
                )}
              </div>

              {project.description && (
                <p style={styles.description}>{project.description}</p>
              )}

              <div style={styles.cardDetails}>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>Supervisor:</span>
                  <span style={styles.detailValue}>
                    {project.supervisorName || 'Unknown'}
                    <button
                      style={styles.manageLink}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleManageMembers(project.supervisor_id);
                      }}
                    >
                      Manage
                    </button>
                  </span>
                </div>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>Active RDMP:</span>
                  <span style={styles.detailValue}>
                    {project.activeRdmpTitle || '-'}
                  </span>
                </div>
              </div>

              <button
                style={styles.openButton}
                onClick={() => onSelectProject(project.id)}
              >
                Open Project
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
  },
  header: {
    marginBottom: '24px',
  },
  title: {
    fontSize: '24px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  subtitle: {
    color: '#6b7280',
    margin: '4px 0 0 0',
  },
  loading: {
    textAlign: 'center',
    color: '#6b7280',
    padding: '40px',
  },
  error: {
    padding: '12px',
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '6px',
    color: '#dc2626',
    marginBottom: '16px',
  },
  searchBar: {
    marginBottom: '24px',
  },
  searchInput: {
    width: '100%',
    maxWidth: '400px',
    padding: '10px 16px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
  },
  projectsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
    gap: '20px',
  },
  noProjects: {
    textAlign: 'center',
    color: '#6b7280',
    padding: '40px',
    gridColumn: '1 / -1',
  },
  projectCard: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: '12px',
  },
  projectName: {
    fontSize: '18px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  activeBadge: {
    padding: '4px 10px',
    fontSize: '12px',
    fontWeight: 500,
    background: '#d1fae5',
    color: '#065f46',
    borderRadius: '9999px',
    whiteSpace: 'nowrap',
  },
  inactiveBadge: {
    padding: '4px 10px',
    fontSize: '12px',
    fontWeight: 500,
    background: '#fef3c7',
    color: '#92400e',
    borderRadius: '9999px',
    whiteSpace: 'nowrap',
  },
  description: {
    fontSize: '14px',
    color: '#6b7280',
    margin: 0,
    lineHeight: 1.5,
  },
  cardDetails: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '12px 0',
    borderTop: '1px solid #f3f4f6',
    borderBottom: '1px solid #f3f4f6',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '14px',
  },
  detailLabel: {
    color: '#6b7280',
  },
  detailValue: {
    color: '#111827',
    fontWeight: 500,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  manageLink: {
    fontSize: '12px',
    color: '#2563eb',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    textDecoration: 'underline',
  },
  openButton: {
    padding: '10px 16px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    marginTop: 'auto',
  },
};
