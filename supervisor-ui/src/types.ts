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
  supervisor_id: number;
  is_active: boolean;
  sample_id_rule_type: string | null;
  sample_id_regex: string | null;
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

export interface StorageRoot {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
  created_at: string;
}

export interface SampleIdDetectionInfo {
  rule_type: string | null;
  regex: string | null;
  example_filename: string | null;
  example_result: string | null;
  configured: boolean;
  explanation: string | null;
}

export interface PendingIngest {
  id: number;
  project_id: number;
  storage_root_id: number;
  relative_path: string;
  inferred_sample_identifier: string | null;
  file_size_bytes: number | null;
  file_hash_sha256: string | null;
  status: 'PENDING' | 'COMPLETED' | 'CANCELLED';
  created_at: string;
  created_by: number;
  completed_at: string | null;
  raw_data_item_id: number | null;
  storage_root_name?: string;
  project_name?: string;
  detected_sample_id?: string | null;
  detection_info?: SampleIdDetectionInfo | null;
}

export interface PendingIngestFinalize {
  sample_id?: number;
  sample_identifier?: string;
  field_values?: Record<string, unknown>;
}

export interface RDMPVersion {
  id: number;
  project_id: number;
  version: number;
  status: 'DRAFT' | 'ACTIVE' | 'SUPERSEDED';
  title: string;
  content: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  created_by: number | null;
  approved_by: number | null;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  sample_id_rule_type?: string | null;
  sample_id_regex?: string | null;
}

export interface RDMPCreate {
  title: string;
  content: Record<string, unknown>;
}

export interface RDMPUpdate {
  title?: string;
  content?: Record<string, unknown>;
}
