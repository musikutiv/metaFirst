export interface User {
  id: number;
  username: string;
  display_name: string;
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  created_by: number;
  is_active: boolean;
}

export interface RDMPField {
  key: string;
  type: 'string' | 'number' | 'date' | 'categorical';
  required: boolean;
  visibility: 'private' | 'collaborators' | 'public_index';
  allowed_values?: string[];
  description?: string;
}

export interface RDMPRole {
  name: string;
  permissions: {
    can_edit_metadata: boolean;
    can_edit_paths: boolean;
    can_create_release: boolean;
    can_manage_rdmp: boolean;
  };
}

export interface RDMP {
  id: number;
  project_id: number;
  version_int: number;
  rdmp_json: {
    name: string;
    description?: string;
    roles: RDMPRole[];
    fields: RDMPField[];
    file_patterns?: string[];
  };
  created_at: string;
}

export interface SampleCompleteness {
  is_complete: boolean;
  missing_fields: string[];
  total_required: number;
  total_filled: number;
}

export interface Sample {
  id: number;
  project_id: number;
  sample_identifier: string;
  created_at: string;
  created_by: number;
  fields: Record<string, unknown>;
  completeness: SampleCompleteness;
}

export interface RawDataItem {
  id: number;
  project_id: number;
  sample_id: number | null;
  storage_root_id: number;
  relative_path: string;
  storage_owner_user_id: number;
  file_size_bytes: number | null;
  created_at: string;
  storage_root_name?: string;
  sample_identifier?: string;
}

export interface AuthState {
  token: string | null;
  user: User | null;
}
