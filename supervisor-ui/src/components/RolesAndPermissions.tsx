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

      {/* Getting Started Section */}
      <div style={styles.gettingStartedSection}>
        <h2 style={styles.sectionTitle}>Getting Started</h2>
        <p style={styles.intro}>
          Follow these steps to make your lab operational and ready for data management.
        </p>

        <div style={styles.stepsContainer}>
          <div style={styles.step}>
            <div style={styles.stepNumber}>1</div>
            <div style={styles.stepContent}>
              <h4 style={styles.stepTitle}>Assign a PI or Steward</h4>
              <p style={styles.stepDescription}>
                Every lab needs at least one PI or Data Steward to manage projects
                and RDMPs. Navigate to <strong>Manage Members</strong> to add team
                members and assign roles.
              </p>
            </div>
          </div>

          <div style={styles.step}>
            <div style={styles.stepNumber}>2</div>
            <div style={styles.stepContent}>
              <h4 style={styles.stepTitle}>Create a Project</h4>
              <p style={styles.stepDescription}>
                Projects organize your research data. Create a project from the
                main dashboard to get started. Give it a descriptive name that
                helps team members identify its purpose.
              </p>
            </div>
          </div>

          <div style={styles.step}>
            <div style={styles.stepNumber}>3</div>
            <div style={styles.stepContent}>
              <h4 style={styles.stepTitle}>Set Up an RDMP</h4>
              <p style={styles.stepDescription}>
                A Research Data Management Plan (RDMP) defines how data is handled
                in your project. Create a draft RDMP from the project view, then
                have a PI activate it to enable data operations.
              </p>
            </div>
          </div>

          <div style={styles.step}>
            <div style={styles.stepNumber}>4</div>
            <div style={styles.stepContent}>
              <h4 style={styles.stepTitle}>Configure an Ingestor</h4>
              <p style={styles.stepDescription}>
                Set up a storage root to enable data ingestion. This tells the
                system where to look for new data files. Once configured, data
                can be ingested into your project.
              </p>
            </div>
          </div>
        </div>

        <div style={styles.readyBox}>
          <span style={styles.readyIcon}>&#10003;</span>
          <div>
            <strong>Ready to go!</strong>
            <p style={styles.readyText}>
              Once all four steps are complete, your lab is fully operational.
              You can ingest data, create samples, and manage your research outputs.
            </p>
          </div>
        </div>
      </div>

      {/* Project State & RDMP Lifecycle Section */}
      <div style={styles.lifecycleSection}>
        <h2 style={styles.sectionTitle}>Project State & RDMP Lifecycle</h2>
        <p style={styles.intro}>
          Every project requires an active RDMP (Research Data Management Plan) to be
          operational. The RDMP defines how data is managed, who can access it, and
          what metadata is required.
        </p>

        <h3 style={styles.subsectionTitle}>RDMP States</h3>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>State</th>
              <th style={styles.th}>Meaning</th>
              <th style={styles.th}>What You Can Do</th>
              <th style={styles.th}>Next Action</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={styles.td}>
                <span style={{ ...styles.statusBadge, background: '#fef2f2', color: '#991b1b' }}>
                  No RDMP
                </span>
              </td>
              <td style={styles.td}>Project has no RDMP created</td>
              <td style={styles.td}>View project metadata (read-only)</td>
              <td style={styles.td}>Create an RDMP draft</td>
            </tr>
            <tr>
              <td style={styles.td}>
                <span style={{ ...styles.statusBadge, background: '#fef3c7', color: '#92400e' }}>
                  Draft
                </span>
              </td>
              <td style={styles.td}>RDMP created but not yet activated</td>
              <td style={styles.td}>Edit the draft, view project</td>
              <td style={styles.td}>Have a PI activate the RDMP</td>
            </tr>
            <tr>
              <td style={styles.td}>
                <span style={{ ...styles.statusBadge, background: '#d1fae5', color: '#065f46' }}>
                  Active
                </span>
              </td>
              <td style={styles.td}>Project is operational</td>
              <td style={styles.td}>Ingest data, manage samples, full operations</td>
              <td style={styles.td}>Continue working or create new draft for updates</td>
            </tr>
            <tr>
              <td style={styles.td}>
                <span style={{ ...styles.statusBadge, background: '#f3f4f6', color: '#6b7280' }}>
                  Superseded
                </span>
              </td>
              <td style={styles.td}>Replaced by a newer RDMP version</td>
              <td style={styles.td}>View historical data</td>
              <td style={styles.td}>Work with the active RDMP</td>
            </tr>
          </tbody>
        </table>

        <h3 style={styles.subsectionTitle}>State Transitions</h3>
        <div style={styles.transitionFlow}>
          <div style={styles.flowItem}>
            <span style={styles.flowState}>No RDMP</span>
            <span style={styles.flowArrow}>→</span>
            <span style={styles.flowAction}>Create Draft</span>
            <span style={styles.flowArrow}>→</span>
            <span style={styles.flowState}>Draft</span>
            <span style={styles.flowArrow}>→</span>
            <span style={styles.flowAction}>Activate (PI)</span>
            <span style={styles.flowArrow}>→</span>
            <span style={styles.flowState}>Active</span>
          </div>
          <p style={styles.flowNote}>
            When a new RDMP is activated, the previous active RDMP becomes Superseded.
          </p>
        </div>

        <h3 style={styles.subsectionTitle}>Blocked Operations</h3>
        <p style={styles.blockNote}>
          Without an active RDMP, the following operations are blocked:
        </p>
        <ul style={styles.blockedList}>
          <li>Data ingestion (adding new files to the project)</li>
          <li>Sample creation</li>
          <li>Metadata modifications</li>
        </ul>
        <p style={styles.blockNote}>
          The UI will show clear guidance on what action is needed to unblock operations.
        </p>
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
  lifecycleSection: {
    marginTop: '40px',
    paddingTop: '32px',
    borderTop: '1px solid #e5e7eb',
  },
  sectionTitle: {
    fontSize: '24px',
    fontWeight: 600,
    color: '#111827',
    marginBottom: '16px',
  },
  subsectionTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#374151',
    marginTop: '24px',
    marginBottom: '12px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '14px',
  },
  th: {
    textAlign: 'left',
    padding: '12px',
    borderBottom: '2px solid #e5e7eb',
    fontWeight: 600,
    color: '#374151',
    background: '#f9fafb',
  },
  td: {
    padding: '12px',
    borderBottom: '1px solid #e5e7eb',
    color: '#4b5563',
    verticalAlign: 'top',
  },
  statusBadge: {
    display: 'inline-block',
    padding: '2px 8px',
    fontSize: '12px',
    fontWeight: 500,
    borderRadius: '4px',
  },
  transitionFlow: {
    background: '#f9fafb',
    borderRadius: '8px',
    padding: '20px',
    marginTop: '12px',
  },
  flowItem: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '8px',
    fontSize: '14px',
  },
  flowState: {
    padding: '4px 12px',
    background: '#e5e7eb',
    borderRadius: '4px',
    fontWeight: 500,
    color: '#374151',
  },
  flowAction: {
    color: '#2563eb',
    fontStyle: 'italic',
  },
  flowArrow: {
    color: '#9ca3af',
    fontSize: '16px',
  },
  flowNote: {
    fontSize: '13px',
    color: '#6b7280',
    marginTop: '12px',
    marginBottom: 0,
  },
  blockNote: {
    fontSize: '14px',
    color: '#4b5563',
    marginBottom: '8px',
  },
  blockedList: {
    margin: '0 0 12px 0',
    paddingLeft: '20px',
    fontSize: '14px',
    color: '#4b5563',
    lineHeight: 1.8,
  },
  gettingStartedSection: {
    marginTop: '40px',
    paddingTop: '32px',
    borderTop: '1px solid #e5e7eb',
  },
  stepsContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    marginTop: '20px',
  },
  step: {
    display: 'flex',
    gap: '16px',
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    padding: '16px',
  },
  stepNumber: {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    background: '#2563eb',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 600,
    fontSize: '14px',
    flexShrink: 0,
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: '#111827',
    margin: '0 0 4px 0',
  },
  stepDescription: {
    fontSize: '14px',
    color: '#4b5563',
    margin: 0,
    lineHeight: 1.5,
  },
  readyBox: {
    marginTop: '20px',
    display: 'flex',
    gap: '12px',
    background: '#d1fae5',
    border: '1px solid #a7f3d0',
    borderRadius: '8px',
    padding: '16px',
  },
  readyIcon: {
    fontSize: '20px',
    color: '#059669',
    fontWeight: 'bold',
  },
  readyText: {
    fontSize: '14px',
    color: '#065f46',
    margin: '4px 0 0 0',
  },
};
