import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { Supervisor, SupervisorMember } from '../types';

export function SupervisorMembers() {
  const { supervisorId } = useParams<{ supervisorId: string }>();
  const navigate = useNavigate();

  const [supervisor, setSupervisor] = useState<Supervisor | null>(null);
  const [members, setMembers] = useState<SupervisorMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add member form
  const [newUsername, setNewUsername] = useState('');
  const [newRole, setNewRole] = useState<'RESEARCHER' | 'STEWARD' | 'PI'>('RESEARCHER');
  const [adding, setAdding] = useState(false);

  // Edit state
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [editRole, setEditRole] = useState<string>('');

  const loadData = useCallback(async () => {
    if (!supervisorId) return;

    setLoading(true);
    setError(null);
    try {
      const [supervisorData, membersData] = await Promise.all([
        apiClient.getSupervisor(parseInt(supervisorId)),
        apiClient.getSupervisorMembers(parseInt(supervisorId)),
      ]);
      setSupervisor(supervisorData);
      setMembers(membersData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [supervisorId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supervisorId || !newUsername.trim()) return;

    setAdding(true);
    setError(null);
    try {
      await apiClient.addSupervisorMember(parseInt(supervisorId), newUsername.trim(), newRole);
      setNewUsername('');
      setNewRole('RESEARCHER');
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add member');
    } finally {
      setAdding(false);
    }
  };

  const handleUpdateRole = async (userId: number) => {
    if (!supervisorId) return;

    setError(null);
    try {
      await apiClient.updateSupervisorMember(parseInt(supervisorId), userId, editRole);
      setEditingUserId(null);
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update role');
    }
  };

  const handleRemoveMember = async (userId: number, username: string) => {
    if (!supervisorId) return;
    if (!confirm(`Remove ${username} from this supervisor?`)) return;

    setError(null);
    try {
      await apiClient.removeSupervisorMember(parseInt(supervisorId), userId);
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to remove member');
    }
  };

  const startEdit = (member: SupervisorMember) => {
    setEditingUserId(member.user_id);
    setEditRole(member.role);
  };

  const cancelEdit = () => {
    setEditingUserId(null);
    setEditRole('');
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <p style={styles.loading}>Loading...</p>
      </div>
    );
  }

  if (!supervisor) {
    return (
      <div style={styles.container}>
        <p style={styles.error}>Supervisor not found</p>
        <button style={styles.backButton} onClick={() => navigate('/')}>
          Back to Projects
        </button>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <button style={styles.backButton} onClick={() => navigate('/')}>
          &larr; Back
        </button>
        <div>
          <h2 style={styles.title}>{supervisor.name}</h2>
          <p style={styles.subtitle}>Manage supervisor members</p>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Add Member Form */}
      <div style={styles.addForm}>
        <h3 style={styles.sectionTitle}>Add Member</h3>
        <form onSubmit={handleAddMember} style={styles.form}>
          <input
            type="text"
            placeholder="Username"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            style={styles.input}
            disabled={adding}
          />
          <select
            value={newRole}
            onChange={(e) => setNewRole(e.target.value as 'RESEARCHER' | 'STEWARD' | 'PI')}
            style={styles.select}
            disabled={adding}
          >
            <option value="RESEARCHER">RESEARCHER</option>
            <option value="STEWARD">STEWARD</option>
            <option value="PI">PI</option>
          </select>
          <button type="submit" style={styles.addButton} disabled={adding || !newUsername.trim()}>
            {adding ? 'Adding...' : 'Add Member'}
          </button>
        </form>
      </div>

      {/* Members Table */}
      <div style={styles.membersSection}>
        <h3 style={styles.sectionTitle}>Members ({members.length})</h3>
        {members.length === 0 ? (
          <p style={styles.noMembers}>No members yet</p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Username</th>
                <th style={styles.th}>Display Name</th>
                <th style={styles.th}>Role</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.user_id}>
                  <td style={styles.td}>{member.username}</td>
                  <td style={styles.td}>{member.display_name || '-'}</td>
                  <td style={styles.td}>
                    {editingUserId === member.user_id ? (
                      <select
                        value={editRole}
                        onChange={(e) => setEditRole(e.target.value)}
                        style={styles.selectSmall}
                      >
                        <option value="RESEARCHER">RESEARCHER</option>
                        <option value="STEWARD">STEWARD</option>
                        <option value="PI">PI</option>
                      </select>
                    ) : (
                      <span style={styles.roleBadge} data-role={member.role}>
                        {member.role}
                      </span>
                    )}
                  </td>
                  <td style={styles.td}>
                    {editingUserId === member.user_id ? (
                      <>
                        <button
                          style={styles.saveButton}
                          onClick={() => handleUpdateRole(member.user_id)}
                        >
                          Save
                        </button>
                        <button style={styles.cancelButton} onClick={cancelEdit}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button style={styles.editButton} onClick={() => startEdit(member)}>
                          Edit
                        </button>
                        <button
                          style={styles.removeButton}
                          onClick={() => handleRemoveMember(member.user_id, member.username)}
                        >
                          Remove
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: '900px',
    margin: '0 auto',
    padding: '24px',
  },
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '16px',
    marginBottom: '24px',
  },
  backButton: {
    padding: '8px 16px',
    fontSize: '14px',
    background: '#f3f4f6',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    cursor: 'pointer',
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
  addForm: {
    background: '#f9fafb',
    padding: '20px',
    borderRadius: '8px',
    marginBottom: '24px',
  },
  sectionTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 12px 0',
  },
  form: {
    display: 'flex',
    gap: '12px',
    alignItems: 'center',
  },
  input: {
    flex: 1,
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
  },
  select: {
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    minWidth: '140px',
  },
  selectSmall: {
    padding: '4px 8px',
    fontSize: '13px',
    border: '1px solid #d1d5db',
    borderRadius: '4px',
  },
  addButton: {
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
  },
  membersSection: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    padding: '20px',
  },
  noMembers: {
    textAlign: 'center',
    color: '#6b7280',
    padding: '20px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    textAlign: 'left',
    padding: '12px',
    borderBottom: '2px solid #e5e7eb',
    fontSize: '14px',
    fontWeight: 600,
    color: '#374151',
  },
  td: {
    padding: '12px',
    borderBottom: '1px solid #e5e7eb',
    fontSize: '14px',
    color: '#111827',
  },
  roleBadge: {
    display: 'inline-block',
    padding: '2px 8px',
    fontSize: '12px',
    fontWeight: 500,
    borderRadius: '4px',
    background: '#e5e7eb',
    color: '#374151',
  },
  editButton: {
    padding: '4px 8px',
    fontSize: '12px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '4px',
    cursor: 'pointer',
    marginRight: '8px',
  },
  saveButton: {
    padding: '4px 8px',
    fontSize: '12px',
    background: '#059669',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    marginRight: '8px',
  },
  cancelButton: {
    padding: '4px 8px',
    fontSize: '12px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  removeButton: {
    padding: '4px 8px',
    fontSize: '12px',
    background: '#fff',
    border: '1px solid #fecaca',
    borderRadius: '4px',
    color: '#dc2626',
    cursor: 'pointer',
  },
};
