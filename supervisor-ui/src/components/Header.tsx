import type { User } from '../types';

interface HeaderProps {
  user: User;
  onLogout: () => void;
}

export function Header({ user, onLogout }: HeaderProps) {
  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <h1 style={styles.title}>metaFirst</h1>
        <span style={styles.subtitle}>Metadata Viewer</span>
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
    alignItems: 'baseline',
    gap: '12px',
  },
  title: {
    fontSize: '20px',
    fontWeight: 600,
    color: '#2563eb',
    margin: 0,
  },
  subtitle: {
    fontSize: '14px',
    color: '#6b7280',
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
