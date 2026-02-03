import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { apiClient } from './api/client';
import { Login } from './components/Login';
import { Header } from './components/Header';
import { ProjectSelector } from './components/ProjectSelector';
import { MetadataTable } from './components/MetadataTable';
import { IngestInbox } from './components/IngestInbox';
import { IngestForm } from './components/IngestForm';
import { IngestPage } from './components/IngestPage';
import { SampleDetailModal } from './components/SampleDetailModal';
import { ProjectSettings } from './components/ProjectSettings';
import { RDMPManagement } from './components/RDMPManagement';
import { CreateProjectWizard } from './components/CreateProjectWizard';
import { NoActiveRDMPBanner } from './components/NoActiveRDMPBanner';
import { SupervisorMembers } from './components/SupervisorMembers';
import { ProjectsOverview } from './components/ProjectsOverview';
import { RolesAndPermissions } from './components/RolesAndPermissions';
import type { User, Project, RDMP, Sample, RawDataItem, PendingIngest, StorageRoot, RDMPVersion, LabRole } from './types';

function App() {
  const navigate = useNavigate();
  const location = useLocation();

  // Auth state
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem('token')
  );
  const [user, setUser] = useState<User | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [authChecking, setAuthChecking] = useState(true);

  // Navigation state (for non-routed views within project context)
  const [selectedPendingIngest, setSelectedPendingIngest] = useState<PendingIngest | null>(null);
  const [selectedSample, setSelectedSample] = useState<Sample | null>(null);

  // Data state
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [rdmp, setRdmp] = useState<RDMP | null>(null);
  const [activeRDMP, setActiveRDMP] = useState<RDMPVersion | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [rawData, setRawData] = useState<RawDataItem[]>([]);
  const [storageRoots, setStorageRoots] = useState<StorageRoot[]>([]);

  // Lab context state
  const [labName, setLabName] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<LabRole | null>(null);

  // UI state
  const [showCreateProjectWizard, setShowCreateProjectWizard] = useState(false);

  // Loading states
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingData, setLoadingData] = useState(false);

  // Refresh trigger - increment to force data reload for current project
  const [refreshCounter, setRefreshCounter] = useState(0);

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
    } else if (!token) {
      setAuthChecking(false);
    }
  }, [token, user]);

  const loadUserAndProjects = async () => {
    try {
      setLoadingProjects(true);
      setAuthChecking(true);
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
      setAuthChecking(false);
    }
  };

  // Load project data when selection changes
  useEffect(() => {
    if (!selectedProjectId) {
      // Clear lab context when no project
      setLabName(null);
      setUserRole(null);
      return;
    }

    // Track if this effect is still active (for race condition prevention)
    let isActive = true;
    const projectIdToLoad = selectedProjectId;

    const doLoad = async () => {
      setLoadingData(true);
      try {
        // First, get the project to get supervisor_id
        const project = projects.find(p => p.id === projectIdToLoad);
        const supervisorId = project?.supervisor_id;

        const [rdmpData, activeRdmpData, samplesResponse, rawDataData, storageRootsData, labRoleData] = await Promise.all([
          apiClient.getProjectRDMP(projectIdToLoad).catch(() => null),
          apiClient.getActiveRDMP(projectIdToLoad).catch(() => null),
          apiClient.getSamples(projectIdToLoad),
          apiClient.getRawData(projectIdToLoad),
          apiClient.getStorageRoots(projectIdToLoad),
          supervisorId ? apiClient.getMyLabRole(supervisorId).catch(() => null) : Promise.resolve(null),
        ]);

        // Only update state if this effect is still active (project hasn't changed)
        if (isActive) {
          setRdmp(rdmpData);
          setActiveRDMP(activeRdmpData);
          setSamples(samplesResponse.items);
          setRawData(rawDataData);
          setStorageRoots(storageRootsData);
          setLabName(labRoleData?.supervisor_name ?? null);
          setUserRole(labRoleData?.role ?? null);
          setLoadingData(false);
        }
      } catch (error) {
        console.error('Failed to load project data:', error);
        if (isActive) {
          setLoadingData(false);
        }
      }
    };

    doLoad();

    // Cleanup: mark this effect as inactive when project changes
    return () => {
      isActive = false;
    };
  }, [selectedProjectId, refreshCounter, projects]);

  const handleLogin = useCallback(async (username: string, password: string) => {
    try {
      setLoginError(null);
      const { access_token } = await apiClient.login(username, password);
      setToken(access_token);
      // After login, stay on the same route (deep link preserved)
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
    setStorageRoots([]);
    setSelectedPendingIngest(null);
    setSelectedSample(null);
    navigate('/');
  }, [navigate]);

  const handleProjectSelect = useCallback((projectId: number) => {
    setSelectedProjectId(projectId);
    // Set loading state FIRST to prevent banner flashing
    setLoadingData(true);
    // Clear previous project data
    setRdmp(null);
    setActiveRDMP(null);
    setSamples([]);
    setRawData([]);
    setStorageRoots([]);
    setSelectedPendingIngest(null);
    setSelectedSample(null);
  }, []);

  // Handle project creation from wizard
  const handleProjectCreated = useCallback((project: Project) => {
    // Add project to list
    setProjects(prev => [...prev, project]);
    // Set loading state FIRST to prevent stale data from showing
    setLoadingData(true);
    // Clear all project-scoped data from previous project
    setRdmp(null);
    setActiveRDMP(null);
    setSamples([]);
    setRawData([]);
    setStorageRoots([]);
    setSelectedPendingIngest(null);
    setSelectedSample(null);
    // Then set the new project ID (will trigger loadProjectData via useEffect)
    setSelectedProjectId(project.id);
  }, []);

  const handleCreateProjectWizardClose = useCallback(() => {
    setShowCreateProjectWizard(false);
    // Data is already loaded via useEffect when selectedProjectId changes
    // and activeRDMP is set via onRDMPActivated callback from wizard
  }, []);

  const handleSelectPendingIngest = useCallback((ingest: PendingIngest) => {
    setSelectedPendingIngest(ingest);
  }, []);

  const handleIngestComplete = useCallback(() => {
    setSelectedPendingIngest(null);
    // Trigger data reload to get updated samples and raw data
    setRefreshCounter(c => c + 1);
  }, []);

  const handleIngestCancel = useCallback(() => {
    setSelectedPendingIngest(null);
  }, []);

  // Callback for when IngestPage loads a project
  const handleProjectLoadedFromIngest = useCallback((projectId: number) => {
    if (projectId !== selectedProjectId) {
      setSelectedProjectId(projectId);
    }
  }, [selectedProjectId]);

  // Callback for when project settings are updated
  const handleProjectUpdated = useCallback((updatedProject: Project) => {
    setProjects(prev => prev.map(p => p.id === updatedProject.id ? updatedProject : p));
  }, []);

  // Callback for when RDMP is activated - update state immediately and reload
  const handleRDMPActivated = useCallback((activatedRDMP: RDMPVersion) => {
    // Set the active RDMP immediately to ensure UI consistency
    setActiveRDMP(activatedRDMP);
    // Trigger data reload to get any other updates
    setRefreshCounter(c => c + 1);
  }, []);

  // Show loading while checking auth
  if (authChecking) {
    return (
      <div style={styles.authLoading}>
        <p>Loading...</p>
      </div>
    );
  }

  // Show login if not authenticated (preserving the current route for deep link)
  if (!token || !user) {
    return <Login onLogin={handleLogin} error={loginError} returnPath={location.pathname} />;
  }

  const selectedProject = projects.find((p) => p.id === selectedProjectId);
  const fields = rdmp?.rdmp_json.fields || [];

  // Render project-scoped content (metadata table or inbox)
  const renderProjectContent = (view: 'metadata' | 'inbox') => {
    if (!selectedProject) {
      return (
        <div style={styles.placeholder}>
          <p>Select a project to view its metadata</p>
        </div>
      );
    }

    // If there's a selected pending ingest, show the form
    if (selectedPendingIngest && view === 'inbox') {
      return (
        <IngestForm
          ingest={selectedPendingIngest}
          fields={fields}
          samples={samples}
          storageRoots={storageRoots}
          onComplete={handleIngestComplete}
          onCancel={handleIngestCancel}
        />
      );
    }

    if (view === 'inbox') {
      return (
        <IngestInbox
          project={selectedProject}
          onSelectIngest={handleSelectPendingIngest}
          storageRoots={storageRoots}
          hasActiveRDMP={!!activeRDMP}
        />
      );
    }

    // Default: metadata view
    return (
      <MetadataTable
        samples={samples}
        fields={fields}
        rawData={rawData}
        loading={loadingData}
        storageRoots={storageRoots}
        onSelectSample={setSelectedSample}
      />
    );
  };

  // Determine current tab from route
  const getCurrentTab = () => {
    if (location.pathname === '/inbox') return 'inbox';
    if (location.pathname === '/settings') return 'settings';
    if (location.pathname === '/rdmps') return 'rdmps';
    return 'metadata';
  };
  const currentTab = getCurrentTab();

  return (
    <div style={styles.app}>
      <Header user={user} onLogout={handleLogout} labName={labName} userRole={userRole} />

      <main style={styles.main}>
        <Routes>
          {/* Projects Overview page */}
          <Route
            path="/overview"
            element={
              <ProjectsOverview
                onSelectProject={(projectId) => {
                  handleProjectSelect(projectId);
                  navigate('/');
                }}
              />
            }
          />

          {/* Supervisor Members management */}
          <Route
            path="/supervisors/:supervisorId/members"
            element={<SupervisorMembers />}
          />

          {/* Roles and Permissions documentation */}
          <Route
            path="/roles"
            element={<RolesAndPermissions />}
          />

          {/* Direct ingest page - no project selection required */}
          <Route
            path="/ingest/:pendingId"
            element={
              <IngestPage
                onProjectLoaded={handleProjectLoadedFromIngest}
                onIngestComplete={handleIngestComplete}
              />
            }
          />

          {/* Project-scoped views */}
          <Route
            path="/*"
            element={
              <>
                <div style={styles.toolbar}>
                  <ProjectSelector
                    projects={projects}
                    selectedProjectId={selectedProjectId}
                    onSelect={handleProjectSelect}
                    loading={loadingProjects}
                    onCreateProject={() => setShowCreateProjectWizard(true)}
                  />
                </div>

                {selectedProject && (
                  <div style={styles.content}>
                    <div style={styles.projectInfo}>
                      <h2 style={styles.projectName}>{selectedProject.name}</h2>
                      {selectedProject.description && (
                        <p style={styles.projectDescription}>{selectedProject.description}</p>
                      )}
                      {activeRDMP ? (
                        <p style={styles.rdmpInfo}>
                          RDMP: {activeRDMP.title} (v{activeRDMP.version}) - Active
                        </p>
                      ) : rdmp ? (
                        <p style={styles.rdmpInfo}>
                          RDMP: {rdmp.rdmp_json.name} (v{rdmp.version_int})
                        </p>
                      ) : null}
                    </div>

                    {/* No Active RDMP Warning Banner */}
                    {!loadingData && !activeRDMP && (
                      <NoActiveRDMPBanner projectId={selectedProject.id} />
                    )}

                    {/* Navigation tabs */}
                    <div style={styles.tabs}>
                      <button
                        style={{
                          ...styles.tab,
                          ...(currentTab === 'metadata' ? styles.tabActive : {}),
                        }}
                        onClick={() => navigate('/')}
                      >
                        Metadata Table
                      </button>
                      <button
                        style={{
                          ...styles.tab,
                          ...(currentTab === 'inbox' ? styles.tabActive : {}),
                        }}
                        onClick={() => {
                          setSelectedPendingIngest(null);
                          navigate('/inbox');
                        }}
                      >
                        Ingest Inbox
                      </button>
                      <button
                        style={{
                          ...styles.tab,
                          ...(currentTab === 'rdmps' ? styles.tabActive : {}),
                        }}
                        onClick={() => navigate('/rdmps')}
                      >
                        RDMPs
                      </button>
                      <button
                        style={{
                          ...styles.tab,
                          ...(currentTab === 'settings' ? styles.tabActive : {}),
                        }}
                        onClick={() => navigate('/settings')}
                      >
                        Settings
                      </button>
                    </div>
                  </div>
                )}

                <Routes>
                  <Route path="/" element={renderProjectContent('metadata')} />
                  <Route path="/inbox" element={renderProjectContent('inbox')} />
                  <Route
                    path="/settings"
                    element={
                      selectedProject ? (
                        <ProjectSettings
                          project={selectedProject}
                          onProjectUpdated={handleProjectUpdated}
                          userRole={userRole}
                        />
                      ) : (
                        <div style={styles.placeholder}>
                          <p>Select a project to view its settings</p>
                        </div>
                      )
                    }
                  />
                  <Route
                    path="/rdmps"
                    element={
                      selectedProject ? (
                        <RDMPManagement
                          project={selectedProject}
                          onRDMPActivated={handleRDMPActivated}
                          userRole={userRole}
                        />
                      ) : (
                        <div style={styles.placeholder}>
                          <p>Select a project to manage RDMPs</p>
                        </div>
                      )
                    }
                  />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </>
            }
          />
        </Routes>
      </main>

      {/* Sample Detail Modal */}
      {selectedSample && (
        <SampleDetailModal
          sample={selectedSample}
          rawData={rawData}
          fields={fields}
          storageRoots={storageRoots}
          onClose={() => setSelectedSample(null)}
        />
      )}

      {/* Create Project Wizard */}
      {showCreateProjectWizard && (
        <CreateProjectWizard
          onClose={handleCreateProjectWizardClose}
          onProjectCreated={handleProjectCreated}
          onRDMPActivated={(rdmp) => setActiveRDMP(rdmp)}
        />
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
  },
  authLoading: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    color: '#6b7280',
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
  tabs: {
    display: 'flex',
    gap: '4px',
    borderBottom: '1px solid #e5e7eb',
    marginBottom: '16px',
  },
  tab: {
    padding: '10px 16px',
    fontSize: '14px',
    fontWeight: 500,
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: '#6b7280',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  tabActive: {
    color: '#2563eb',
    borderBottomColor: '#2563eb',
  },
};

export default App;
