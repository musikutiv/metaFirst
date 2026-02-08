import type { Project, RDMP, Sample, RawDataItem, User, StorageRoot, PendingIngest, PendingIngestFinalize, RDMPVersion, ProjectUpdate, RDMPCreate, RDMPUpdate, Supervisor, ProjectCreate, SupervisorMember, SampleListResponse, LabRoleInfo, ActivityLogListResponse, EventTypeOption } from '../types';

const API_BASE = '/api';

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Auth
  async login(username: string, password: string): Promise<{ access_token: string }> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Invalid credentials');
    }

    return response.json();
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  // Projects
  async getProjects(): Promise<Project[]> {
    return this.request<Project[]>('/projects/');
  }

  async getProject(projectId: number): Promise<Project> {
    return this.request<Project>(`/projects/${projectId}`);
  }

  async createProject(data: ProjectCreate): Promise<Project> {
    return this.request<Project>('/projects/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Supervisors
  async getSupervisors(): Promise<Supervisor[]> {
    return this.request<Supervisor[]>('/supervisors/');
  }

  async getSupervisor(supervisorId: number): Promise<Supervisor> {
    return this.request<Supervisor>(`/supervisors/${supervisorId}`);
  }

  // Supervisor Members
  async getSupervisorMembers(supervisorId: number): Promise<SupervisorMember[]> {
    return this.request<SupervisorMember[]>(`/supervisors/${supervisorId}/members`);
  }

  async getMyLabRole(supervisorId: number): Promise<LabRoleInfo> {
    return this.request<LabRoleInfo>(`/supervisors/${supervisorId}/my-role`);
  }

  async addSupervisorMember(supervisorId: number, username: string, role: string): Promise<SupervisorMember> {
    return this.request<SupervisorMember>(`/supervisors/${supervisorId}/members`, {
      method: 'POST',
      body: JSON.stringify({ username, role }),
    });
  }

  async updateSupervisorMember(supervisorId: number, userId: number, role: string, reason: string): Promise<SupervisorMember> {
    return this.request<SupervisorMember>(`/supervisors/${supervisorId}/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role, reason }),
    });
  }

  async removeSupervisorMember(supervisorId: number, userId: number): Promise<void> {
    await this.request<void>(`/supervisors/${supervisorId}/members/${userId}`, {
      method: 'DELETE',
    });
  }

  // RDMP
  async getProjectRDMP(projectId: number): Promise<RDMP> {
    return this.request<RDMP>(`/rdmp/projects/${projectId}/rdmp`);
  }

  async getActiveRDMP(projectId: number): Promise<RDMPVersion | null> {
    const response = await fetch(`${API_BASE}/projects/${projectId}/rdmps/active`, {
      headers: {
        'Content-Type': 'application/json',
        ...(this.token ? { 'Authorization': `Bearer ${this.token}` } : {}),
      },
    });
    if (!response.ok) {
      if (response.status === 404) return null;
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    const data = await response.json();
    return data || null;
  }

  // Samples
  async getSamples(projectId: number, limit: number = 50, offset: number = 0): Promise<SampleListResponse> {
    return this.request<SampleListResponse>(`/projects/${projectId}/samples?limit=${limit}&offset=${offset}`);
  }

  async getSample(sampleId: number): Promise<Sample> {
    return this.request<Sample>(`/samples/${sampleId}`);
  }

  // Raw Data
  async getRawData(projectId: number, sampleId?: number): Promise<RawDataItem[]> {
    const params = sampleId ? `?sample_id=${sampleId}` : '';
    return this.request<RawDataItem[]>(`/projects/${projectId}/raw-data${params}`);
  }

  // Storage Roots
  async getStorageRoots(projectId: number): Promise<StorageRoot[]> {
    return this.request<StorageRoot[]>(`/projects/${projectId}/storage-roots`);
  }

  // Pending Ingests
  async getPendingIngests(projectId: number, status?: string): Promise<PendingIngest[]> {
    const params = status ? `?status_filter=${status}` : '';
    return this.request<PendingIngest[]>(`/projects/${projectId}/pending-ingests${params}`);
  }

  async getPendingIngest(pendingIngestId: number): Promise<PendingIngest> {
    return this.request<PendingIngest>(`/pending-ingests/${pendingIngestId}`);
  }

  async finalizePendingIngest(
    pendingIngestId: number,
    data: PendingIngestFinalize
  ): Promise<RawDataItem> {
    return this.request<RawDataItem>(`/pending-ingests/${pendingIngestId}/finalize`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async cancelPendingIngest(pendingIngestId: number): Promise<PendingIngest> {
    return this.request<PendingIngest>(`/pending-ingests/${pendingIngestId}`, {
      method: 'DELETE',
    });
  }

  async createSample(projectId: number, sampleIdentifier: string): Promise<Sample> {
    return this.request<Sample>(`/projects/${projectId}/samples`, {
      method: 'POST',
      body: JSON.stringify({ sample_identifier: sampleIdentifier }),
    });
  }

  async setSampleField(sampleId: number, fieldKey: string, value: unknown): Promise<void> {
    await this.request<void>(`/samples/${sampleId}/fields/${fieldKey}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    });
  }

  // Project Settings
  async updateProject(projectId: number, data: ProjectUpdate): Promise<Project> {
    return this.request<Project>(`/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  // RDMP Management
  async listRDMPVersions(projectId: number): Promise<RDMPVersion[]> {
    return this.request<RDMPVersion[]>(`/projects/${projectId}/rdmps`);
  }

  async createRDMPDraft(projectId: number, data: RDMPCreate): Promise<RDMPVersion> {
    return this.request<RDMPVersion>(`/projects/${projectId}/rdmps`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getRDMPVersion(rdmpId: number): Promise<RDMPVersion> {
    return this.request<RDMPVersion>(`/rdmps/${rdmpId}`);
  }

  async updateRDMPDraft(rdmpId: number, data: RDMPUpdate): Promise<RDMPVersion> {
    return this.request<RDMPVersion>(`/rdmps/${rdmpId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async activateRDMP(rdmpId: number, reason: string): Promise<RDMPVersion> {
    return this.request<RDMPVersion>(`/rdmps/${rdmpId}/activate`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  // Lab Activity
  async getLabActivity(
    supervisorId: number,
    options?: { eventTypes?: string; search?: string; limit?: number; offset?: number }
  ): Promise<ActivityLogListResponse> {
    const params = new URLSearchParams();
    if (options?.eventTypes) params.append('event_types', options.eventTypes);
    if (options?.search) params.append('search', options.search);
    if (options?.limit) params.append('limit', options.limit.toString());
    if (options?.offset) params.append('offset', options.offset.toString());
    const query = params.toString();
    return this.request<ActivityLogListResponse>(
      `/supervisors/${supervisorId}/activity${query ? `?${query}` : ''}`
    );
  }

  async getLabActivityEventTypes(supervisorId: number): Promise<EventTypeOption[]> {
    return this.request<EventTypeOption[]>(`/supervisors/${supervisorId}/activity/event-types`);
  }
}

export const apiClient = new ApiClient();
