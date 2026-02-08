import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { Supervisor, ActivityLogEntry, EventTypeOption, LabRole } from '../types';
import { RoleBadge } from './RoleBadge';

export function LabActivity() {
  const { supervisorId } = useParams<{ supervisorId: string }>();
  const navigate = useNavigate();

  const [supervisor, setSupervisor] = useState<Supervisor | null>(null);
  const [activities, setActivities] = useState<ActivityLogEntry[]>([]);
  const [eventTypes, setEventTypes] = useState<EventTypeOption[]>([]);
  const [currentUserRole, setCurrentUserRole] = useState<LabRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 25;

  // Filters
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);
  const [searchText, setSearchText] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const loadData = useCallback(async () => {
    if (!supervisorId) return;

    setLoading(true);
    setError(null);
    try {
      const [supervisorData, myRoleData, eventTypesData, activityData] = await Promise.all([
        apiClient.getSupervisor(parseInt(supervisorId)),
        apiClient.getMyLabRole(parseInt(supervisorId)),
        apiClient.getLabActivityEventTypes(parseInt(supervisorId)),
        apiClient.getLabActivity(parseInt(supervisorId), {
          eventTypes: selectedEventTypes.length > 0 ? selectedEventTypes.join(',') : undefined,
          search: searchText || undefined,
          limit,
          offset,
        }),
      ]);
      setSupervisor(supervisorData);
      setCurrentUserRole(myRoleData.role);
      setEventTypes(eventTypesData);
      setActivities(activityData.items);
      setTotal(activityData.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [supervisorId, selectedEventTypes, searchText, offset]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSearch = () => {
    setSearchText(searchInput);
    setOffset(0);
  };

  const handleEventTypeToggle = (value: string) => {
    setSelectedEventTypes(prev => {
      if (prev.includes(value)) {
        return prev.filter(t => t !== value);
      } else {
        return [...prev, value];
      }
    });
    setOffset(0);
  };

  const handleClearFilters = () => {
    setSelectedEventTypes([]);
    setSearchText('');
    setSearchInput('');
    setOffset(0);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const getEventTypeLabel = (eventType: string) => {
    const option = eventTypes.find(o => o.value === eventType);
    return option?.label || eventType;
  };

  const getEventTypeColor = (eventType: string): { bg: string; text: string } => {
    if (eventType.includes('MEMBER')) {
      return { bg: '#dbeafe', text: '#1e40af' };
    }
    if (eventType.includes('RDMP')) {
      return { bg: '#fef3c7', text: '#92400e' };
    }
    if (eventType.includes('PROJECT')) {
      return { bg: '#d1fae5', text: '#065f46' };
    }
    if (eventType.includes('STORAGE')) {
      return { bg: '#fce7f3', text: '#9d174d' };
    }
    if (eventType.includes('VISIBILITY')) {
      return { bg: '#e0e7ff', text: '#3730a3' };
    }
    return { bg: '#e5e7eb', text: '#374151' };
  };

  if (loading && activities.length === 0) {
    return (
      <div style={styles.container}>
        <p style={styles.loading}>Loading...</p>
      </div>
    );
  }

  if (!supervisor) {
    return (
      <div style={styles.container}>
        <p style={styles.error}>Lab not found</p>
        <button style={styles.backButton} onClick={() => navigate('/')}>
          Back to Projects
        </button>
      </div>
    );
  }

  const hasFilters = selectedEventTypes.length > 0 || searchText;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <button style={styles.backButton} onClick={() => navigate('/')}>
          &larr; Back
        </button>
        <div>
          <h2 style={styles.title}>{supervisor.name}</h2>
          <p style={styles.subtitle}>
            Lab Activity Log
            {currentUserRole && (
              <span style={{ marginLeft: '8px' }}>
                (Your role: <RoleBadge role={currentUserRole} size="small" />)
              </span>
            )}
          </p>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Filters */}
      <div style={styles.filters}>
        <div style={styles.filterSection}>
          <label style={styles.filterLabel}>Event Type:</label>
          <div style={styles.eventTypeFilters}>
            {eventTypes.map(et => (
              <button
                key={et.value}
                style={{
                  ...styles.filterChip,
                  ...(selectedEventTypes.includes(et.value) ? styles.filterChipActive : {}),
                }}
                onClick={() => handleEventTypeToggle(et.value)}
              >
                {et.label}
              </button>
            ))}
          </div>
        </div>
        <div style={styles.filterSection}>
          <label style={styles.filterLabel}>Search:</label>
          <div style={styles.searchBox}>
            <input
              type="text"
              style={styles.searchInput}
              placeholder="Search in summary and reason..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            <button style={styles.searchButton} onClick={handleSearch}>
              Search
            </button>
          </div>
        </div>
        {hasFilters && (
          <button style={styles.clearButton} onClick={handleClearFilters}>
            Clear filters
          </button>
        )}
      </div>

      {/* Activity List */}
      <div style={styles.activityList}>
        <div style={styles.listHeader}>
          <span style={styles.totalCount}>
            {total} {total === 1 ? 'event' : 'events'}
            {hasFilters && ' (filtered)'}
          </span>
        </div>

        {activities.length === 0 ? (
          <div style={styles.empty}>
            <p style={styles.emptyText}>
              {hasFilters
                ? 'No activity matches your filters.'
                : 'No activity recorded yet.'}
            </p>
          </div>
        ) : (
          <div style={styles.timeline}>
            {activities.map(activity => {
              const colors = getEventTypeColor(activity.event_type);
              return (
                <div key={activity.id} style={styles.activityCard}>
                  <div style={styles.activityHeader}>
                    <span
                      style={{
                        ...styles.eventTypeBadge,
                        background: colors.bg,
                        color: colors.text,
                      }}
                    >
                      {getEventTypeLabel(activity.event_type)}
                    </span>
                    <span style={styles.activityDate}>
                      {formatDate(activity.created_at)}
                    </span>
                  </div>
                  <p style={styles.activitySummary}>{activity.summary_text}</p>
                  <p style={styles.activityActor}>
                    by {activity.actor_display_name || `User ${activity.actor_user_id}`}
                  </p>
                  {activity.reason_text && (
                    <div style={styles.reasonBlock}>
                      <span style={styles.reasonLabel}>Reason:</span>
                      <span style={styles.reasonText}>{activity.reason_text}</span>
                    </div>
                  )}
                  {(activity.before_json || activity.after_json) && (
                    <details style={styles.details}>
                      <summary style={styles.detailsSummary}>Show changes</summary>
                      <div style={styles.changeDetails}>
                        {activity.before_json && (
                          <div style={styles.changeBlock}>
                            <span style={styles.changeLabel}>Before:</span>
                            <pre style={styles.changeJson}>
                              {JSON.stringify(activity.before_json, null, 2)}
                            </pre>
                          </div>
                        )}
                        {activity.after_json && (
                          <div style={styles.changeBlock}>
                            <span style={styles.changeLabel}>After:</span>
                            <pre style={styles.changeJson}>
                              {JSON.stringify(activity.after_json, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {total > limit && (
          <div style={styles.pagination}>
            <button
              style={{
                ...styles.pageButton,
                ...(offset === 0 ? styles.pageButtonDisabled : {}),
              }}
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
            >
              Previous
            </button>
            <span style={styles.pageInfo}>
              {offset + 1} - {Math.min(offset + limit, total)} of {total}
            </span>
            <button
              style={{
                ...styles.pageButton,
                ...(offset + limit >= total ? styles.pageButtonDisabled : {}),
              }}
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
            >
              Next
            </button>
          </div>
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
  filters: {
    background: '#f9fafb',
    padding: '16px',
    borderRadius: '8px',
    marginBottom: '24px',
  },
  filterSection: {
    marginBottom: '12px',
  },
  filterLabel: {
    display: 'block',
    fontSize: '13px',
    fontWeight: 500,
    color: '#374151',
    marginBottom: '8px',
  },
  eventTypeFilters: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
  },
  filterChip: {
    padding: '4px 10px',
    fontSize: '12px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '16px',
    cursor: 'pointer',
    color: '#6b7280',
  },
  filterChipActive: {
    background: '#2563eb',
    borderColor: '#2563eb',
    color: '#fff',
  },
  searchBox: {
    display: 'flex',
    gap: '8px',
  },
  searchInput: {
    flex: 1,
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
  },
  searchButton: {
    padding: '8px 16px',
    fontSize: '14px',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
  },
  clearButton: {
    padding: '4px 8px',
    fontSize: '12px',
    background: 'transparent',
    border: 'none',
    color: '#2563eb',
    cursor: 'pointer',
    textDecoration: 'underline',
  },
  activityList: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    padding: '16px',
  },
  listHeader: {
    marginBottom: '16px',
    paddingBottom: '12px',
    borderBottom: '1px solid #e5e7eb',
  },
  totalCount: {
    fontSize: '14px',
    color: '#6b7280',
  },
  empty: {
    textAlign: 'center',
    padding: '40px 20px',
  },
  emptyText: {
    color: '#6b7280',
    fontSize: '14px',
  },
  timeline: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  activityCard: {
    padding: '16px',
    background: '#f9fafb',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
  },
  activityHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  eventTypeBadge: {
    padding: '2px 8px',
    fontSize: '11px',
    fontWeight: 500,
    borderRadius: '4px',
  },
  activityDate: {
    fontSize: '12px',
    color: '#6b7280',
  },
  activitySummary: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#111827',
    margin: '0 0 4px 0',
  },
  activityActor: {
    fontSize: '12px',
    color: '#6b7280',
    margin: 0,
  },
  reasonBlock: {
    marginTop: '8px',
    padding: '8px 10px',
    background: '#fef3c7',
    borderRadius: '4px',
    fontSize: '13px',
  },
  reasonLabel: {
    fontWeight: 500,
    color: '#92400e',
    marginRight: '6px',
  },
  reasonText: {
    color: '#78350f',
  },
  details: {
    marginTop: '12px',
  },
  detailsSummary: {
    fontSize: '12px',
    color: '#2563eb',
    cursor: 'pointer',
    marginBottom: '8px',
  },
  changeDetails: {
    display: 'flex',
    gap: '12px',
  },
  changeBlock: {
    flex: 1,
  },
  changeLabel: {
    display: 'block',
    fontSize: '11px',
    fontWeight: 500,
    color: '#6b7280',
    marginBottom: '4px',
  },
  changeJson: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: '4px',
    padding: '8px',
    fontSize: '11px',
    fontFamily: 'monospace',
    overflow: 'auto',
    maxHeight: '100px',
    margin: 0,
  },
  pagination: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: '16px',
    marginTop: '20px',
    paddingTop: '16px',
    borderTop: '1px solid #e5e7eb',
  },
  pageButton: {
    padding: '6px 12px',
    fontSize: '13px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '4px',
    cursor: 'pointer',
    color: '#374151',
  },
  pageButtonDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  pageInfo: {
    fontSize: '13px',
    color: '#6b7280',
  },
};
