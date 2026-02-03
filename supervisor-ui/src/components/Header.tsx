import { useNavigate, useLocation } from 'react-router-dom';
import type { User, LabRole } from '../types';
import { LabContext } from './LabContext';

interface HeaderProps {
  user: User;
  onLogout: () => void;
  labName?: string | null;
  userRole?: LabRole | null;
}

export function Header({ user, onLogout, labName, userRole }: HeaderProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const isOverview = location.pathname === '/overview';
  const isRoles = location.pathname === '/roles';

  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <h1 style={styles.title} onClick={() => navigate('/')} role="button">
          metaFirst
        </h1>
        <span style={styles.subtitle}>Metadata Viewer</span>
        <nav style={styles.nav}>
          <button
            style={{
              ...styles.navLink,
              ...(isOverview ? styles.navLinkActive : {}),
            }}
            onClick={() => navigate('/overview')}
          >
            All Projects
          </button>
          <button
            style={{
              ...styles.navLink,
              ...(isRoles ? styles.navLinkActive : {}),
            }}
            onClick={() => navigate('/roles')}
          >
            Roles
          </button>
        </nav>
        {labName && <LabContext labName={labName} userRole={userRole ?? null} />}
      </div>
      <div style={styles.right}>
        <span style={styles.user}>{user.display_name}</span>
        <button onClick={onLogout} style={styles.logout}>
          Logout
        </button>
      </div>
    </header>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    background: 'white',
    borderBottom: '1px solid #e5e7eb',
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  title: {
    fontSize: '20px',
    fontWeight: 600,
    color: '#2563eb',
    margin: 0,
    cursor: 'pointer',
  },
  subtitle: {
    fontSize: '14px',
    color: '#6b7280',
    marginRight: '16px',
  },
  nav: {
    display: 'flex',
    gap: '8px',
    marginLeft: '8px',
    paddingLeft: '16px',
    borderLeft: '1px solid #e5e7eb',
  },
  navLink: {
    padding: '6px 12px',
    fontSize: '14px',
    fontWeight: 500,
    background: 'transparent',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    color: '#6b7280',
  },
  navLinkActive: {
    background: '#eff6ff',
    color: '#2563eb',
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  user: {
    fontSize: '14px',
    color: '#374151',
  },
  logout: {
    padding: '6px 12px',
    fontSize: '14px',
    background: 'transparent',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    cursor: 'pointer',
    color: '#374151',
  },
};
