import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { Project, Supervisor } from '../types';
import { StatusBadge, getRDMPStatus, type RDMPStatus } from './StatusBadge';

interface ProjectWithDetails extends Project {
  supervisorName?: string;
  activeRdmpTitle?: string | null;
  rdmpStatus: RDMPStatus;
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

      // For each project, get RDMP status and enrich with supervisor info
      const enrichedProjects: ProjectWithDetails[] = await Promise.all(
        projectsData.map(async (project) => {
          const supervisor = supervisorMap.get(project.supervisor_id);

          // Get all RDMPs for this project to determine status
          let activeRdmpTitle: string | null = null;
          let rdmpStatus: RDMPStatus = 'NONE';
          try {
            const rdmps = await apiClient.listRDMPVersions(project.id);
            rdmpStatus = getRDMPStatus(rdmps);
            const activeRdmp = rdmps.find(r => r.status === 'ACTIVE');
            activeRdmpTitle = activeRdmp?.title || null;
          } catch {
            // Ignore errors - project might not have any RDMPs
          }

          // Get user's role from supervisor members (if available)
          let userRole: string | undefined;
          if (supervisor) {
            try {
              const roleInfo = await apiClient.getMyLabRole(supervisor.id);
              userRole = roleInfo.role ?? undefined;
            } catch {
              // Ignore - user might not have access
            }
          }

          return {
            ...project,
            supervisorName: supervisor?.name,
            activeRdmpTitle,
            rdmpStatus,
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
                <StatusBadge type="rdmp" status={project.rdmpStatus} />
              </div>

              {project.description && (
                <p style={styles.description}>{project.description}</p>
              )}

              <div style={styles.cardDetails}>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>Lab:</span>
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
                {project.activeRdmpTitle && (
                  <div style={styles.detailRow}>
                    <span style={styles.detailLabel}>Active RDMP:</span>
                    <span style={styles.detailValue}>
                      {project.activeRdmpTitle}
                    </span>
                  </div>
                )}
              </div>

              <div style={styles.cardButtons}>
                <button
                  style={styles.openButton}
                  onClick={() => onSelectProject(project.id)}
                >
                  Open Project
                </button>
                <button
                  style={styles.tasksLink}
                  onClick={() => {
                    onSelectProject(project.id);
                    navigate('/tasks');
                  }}
                >
                  View Tasks
                </button>
              </div>
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
  cardButtons: {
    display: 'flex',
    gap: '8px',
    marginTop: 'auto',
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
    flex: 1,
  },
  tasksLink: {
    padding: '10px 12px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#fff',
    color: '#374151',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
    cursor: 'pointer',
  },
};
