import type { Project, RDMP, Sample, RawDataItem, User } from '../types';

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
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
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

  // RDMP
  async getProjectRDMP(projectId: number): Promise<RDMP> {
    return this.request<RDMP>(`/rdmp/projects/${projectId}/rdmp`);
  }

  // Samples
  async getSamples(projectId: number): Promise<Sample[]> {
    return this.request<Sample[]>(`/projects/${projectId}/samples`);
  }

  async getSample(sampleId: number): Promise<Sample> {
    return this.request<Sample>(`/samples/${sampleId}`);
  }

  // Raw Data
  async getRawData(projectId: number, sampleId?: number): Promise<RawDataItem[]> {
    const params = sampleId ? `?sample_id=${sampleId}` : '';
    return this.request<RawDataItem[]>(`/projects/${projectId}/raw-data${params}`);
  }
}

export const apiClient = new ApiClient();
