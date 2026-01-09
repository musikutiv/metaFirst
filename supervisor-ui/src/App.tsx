import { useState, useEffect, useCallback } from 'react';
import { apiClient } from './api/client';
import { Login } from './components/Login';
import { Header } from './components/Header';
import { ProjectSelector } from './components/ProjectSelector';
import { MetadataTable } from './components/MetadataTable';
import type { User, Project, RDMP, Sample, RawDataItem } from './types';

function App() {
  // Auth state
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem('token')
  );
  const [user, setUser] = useState<User | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  // Data state
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [rdmp, setRdmp] = useState<RDMP | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [rawData, setRawData] = useState<RawDataItem[]>([]);

  // Loading states
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingData, setLoadingData] = useState(false);

  // Set token in API client when it changes
  useEffect(() => {
    apiClient.setToken(token);
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }, [token]);

  // Load user and projects on mount if we have a token
  useEffect(() => {
    if (token && !user) {
      loadUserAndProjects();
    }
  }, [token, user]);

  const loadUserAndProjects = async () => {
    try {
      setLoadingProjects(true);
      const [userData, projectsData] = await Promise.all([
        apiClient.getCurrentUser(),
        apiClient.getProjects(),
      ]);
      setUser(userData);
      setProjects(projectsData);
      setLoginError(null);
    } catch {
      // Token is invalid
      setToken(null);
      setUser(null);
    } finally {
      setLoadingProjects(false);
    }
  };

  // Load project data when selection changes
  useEffect(() => {
    if (selectedProjectId) {
      loadProjectData(selectedProjectId);
    }
  }, [selectedProjectId]);

  const loadProjectData = async (projectId: number) => {
    setLoadingData(true);
    try {
      const [rdmpData, samplesData, rawDataData] = await Promise.all([
        apiClient.getProjectRDMP(projectId).catch(() => null),
        apiClient.getSamples(projectId),
        apiClient.getRawData(projectId),
      ]);
      setRdmp(rdmpData);
      setSamples(samplesData);
      setRawData(rawDataData);
    } catch (error) {
      console.error('Failed to load project data:', error);
    } finally {
      setLoadingData(false);
    }
  };

  const handleLogin = useCallback(async (username: string, password: string) => {
    try {
      setLoginError(null);
      const { access_token } = await apiClient.login(username, password);
      setToken(access_token);
    } catch {
      setLoginError('Invalid username or password');
    }
  }, []);

  const handleLogout = useCallback(() => {
    setToken(null);
    setUser(null);
    setProjects([]);
    setSelectedProjectId(null);
    setRdmp(null);
    setSamples([]);
    setRawData([]);
  }, []);

  const handleProjectSelect = useCallback((projectId: number) => {
    setSelectedProjectId(projectId);
    // Clear previous project data
    setRdmp(null);
    setSamples([]);
    setRawData([]);
  }, []);

  // Show login if not authenticated
  if (!token || !user) {
    return <Login onLogin={handleLogin} error={loginError} />;
  }

  const selectedProject = projects.find((p) => p.id === selectedProjectId);
  const fields = rdmp?.rdmp_json.fields || [];

  return (
    <div style={styles.app}>
      <Header user={user} onLogout={handleLogout} />

      <main style={styles.main}>
        <div style={styles.toolbar}>
          <ProjectSelector
            projects={projects}
            selectedProjectId={selectedProjectId}
            onSelect={handleProjectSelect}
            loading={loadingProjects}
          />
        </div>

        {selectedProject && (
          <div style={styles.content}>
            <div style={styles.projectInfo}>
              <h2 style={styles.projectName}>{selectedProject.name}</h2>
              {selectedProject.description && (
                <p style={styles.projectDescription}>{selectedProject.description}</p>
              )}
              {rdmp && (
                <p style={styles.rdmpInfo}>
                  RDMP: {rdmp.rdmp_json.name} (v{rdmp.version_int})
                </p>
              )}
            </div>

            <MetadataTable
              samples={samples}
              fields={fields}
              rawData={rawData}
              loading={loadingData}
            />
          </div>
        )}

        {!selectedProjectId && (
          <div style={styles.placeholder}>
            <p>Select a project to view its metadata</p>
          </div>
        )}
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
  },
  main: {
    flex: 1,
    padding: '24px',
    maxWidth: '1400px',
    margin: '0 auto',
    width: '100%',
  },
  toolbar: {
    marginBottom: '24px',
  },
  content: {},
  projectInfo: {
    marginBottom: '16px',
  },
  projectName: {
    fontSize: '24px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  projectDescription: {
    color: '#6b7280',
    marginTop: '4px',
  },
  rdmpInfo: {
    fontSize: '14px',
    color: '#2563eb',
    marginTop: '8px',
  },
  placeholder: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '300px',
    color: '#9ca3af',
    fontSize: '16px',
  },
};

export default App;
