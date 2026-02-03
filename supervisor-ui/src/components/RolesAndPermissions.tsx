/**
 * Roles and Permissions documentation page.
 * Provides clear guidance on lab roles and what actions each role can perform.
 */
export function RolesAndPermissions() {
  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Roles and Permissions</h2>
      <p style={styles.intro}>
        Each lab member has a role that determines what actions they can perform.
        There are three roles, organized in a hierarchy where higher roles include
        all permissions of lower roles.
      </p>

      <div style={styles.rolesSection}>
        <div style={styles.roleCard}>
          <div style={styles.roleHeader}>
            <span style={{ ...styles.roleBadge, ...styles.piRole }}>PI</span>
            <span style={styles.roleTitle}>Principal Investigator</span>
          </div>
          <p style={styles.roleDescription}>
            Full administrative control over the lab and its projects.
          </p>
          <h4 style={styles.permissionsTitle}>Permissions</h4>
          <ul style={styles.permissionsList}>
            <li>All STEWARD permissions</li>
            <li>Activate and supersede RDMPs</li>
            <li>Change member roles</li>
            <li>Remove members from the lab</li>
          </ul>
        </div>

        <div style={styles.roleCard}>
          <div style={styles.roleHeader}>
            <span style={{ ...styles.roleBadge, ...styles.stewardRole }}>STEWARD</span>
            <span style={styles.roleTitle}>Data Steward</span>
          </div>
          <p style={styles.roleDescription}>
            Manages data, projects, and can add new lab members.
          </p>
          <h4 style={styles.permissionsTitle}>Permissions</h4>
          <ul style={styles.permissionsList}>
            <li>All RESEARCHER permissions</li>
            <li>Create new projects</li>
            <li>Modify project settings</li>
            <li>Create and edit RDMP drafts</li>
            <li>Add new members to the lab</li>
            <li>Ingest data into projects</li>
          </ul>
        </div>

        <div style={styles.roleCard}>
          <div style={styles.roleHeader}>
            <span style={{ ...styles.roleBadge, ...styles.researcherRole }}>RESEARCHER</span>
            <span style={styles.roleTitle}>Researcher</span>
          </div>
          <p style={styles.roleDescription}>
            Can view and work with project data.
          </p>
          <h4 style={styles.permissionsTitle}>Permissions</h4>
          <ul style={styles.permissionsList}>
            <li>View projects and samples</li>
            <li>View project metadata</li>
            <li>View RDMP content</li>
            <li>View lab members</li>
          </ul>
        </div>
      </div>

      <div style={styles.notesSection}>
        <h3 style={styles.notesTitle}>Additional Notes</h3>
        <ul style={styles.notesList}>
          <li>
            <strong>Role inheritance:</strong> Higher roles automatically include all
            permissions of lower roles. A PI can do everything a STEWARD can do, and
            a STEWARD can do everything a RESEARCHER can do.
          </li>
          <li>
            <strong>RDMP activation:</strong> Only a PI can activate an RDMP, which
            makes the project operational for data ingestion. This ensures proper
            oversight of research data management plans.
          </li>
          <li>
            <strong>Member management:</strong> STEWARDs can add new members, but only
            PIs can change roles or remove members. This provides flexibility while
            maintaining control.
          </li>
        </ul>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: '800px',
    margin: '0 auto',
    padding: '24px',
  },
  title: {
    fontSize: '24px',
    fontWeight: 600,
    color: '#111827',
    marginBottom: '16px',
  },
  intro: {
    fontSize: '15px',
    color: '#4b5563',
    lineHeight: 1.6,
    marginBottom: '32px',
  },
  rolesSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    marginBottom: '32px',
  },
  roleCard: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    padding: '20px',
  },
  roleHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '12px',
  },
  roleBadge: {
    padding: '4px 12px',
    fontSize: '13px',
    fontWeight: 600,
    borderRadius: '4px',
  },
  piRole: {
    background: '#dbeafe',
    color: '#1e40af',
  },
  stewardRole: {
    background: '#dcfce7',
    color: '#166534',
  },
  researcherRole: {
    background: '#f3f4f6',
    color: '#374151',
  },
  roleTitle: {
    fontSize: '18px',
    fontWeight: 600,
    color: '#111827',
  },
  roleDescription: {
    fontSize: '14px',
    color: '#6b7280',
    marginBottom: '16px',
  },
  permissionsTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#374151',
    marginBottom: '8px',
  },
  permissionsList: {
    margin: 0,
    paddingLeft: '20px',
    fontSize: '14px',
    color: '#4b5563',
    lineHeight: 1.8,
  },
  notesSection: {
    background: '#f9fafb',
    borderRadius: '8px',
    padding: '20px',
  },
  notesTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#374151',
    marginTop: 0,
    marginBottom: '12px',
  },
  notesList: {
    margin: 0,
    paddingLeft: '20px',
    fontSize: '14px',
    color: '#4b5563',
    lineHeight: 1.8,
  },
};
