import { useMemo } from 'react';
import type { Sample, RDMPField, RawDataItem } from '../types';

interface MetadataTableProps {
  samples: Sample[];
  fields: RDMPField[];
  rawData: RawDataItem[];
  loading: boolean;
}

export function MetadataTable({ samples, fields, rawData, loading }: MetadataTableProps) {
  // Build a map of sample_id -> raw data count
  const rawDataCountBySample = useMemo(() => {
    const counts: Record<number, number> = {};
    for (const item of rawData) {
      if (item.sample_id) {
        counts[item.sample_id] = (counts[item.sample_id] || 0) + 1;
      }
    }
    return counts;
  }, [rawData]);

  if (loading) {
    return <div style={styles.loading}>Loading samples...</div>;
  }

  if (samples.length === 0) {
    return (
      <div style={styles.empty}>
        <p>No samples in this project yet.</p>
      </div>
    );
  }

  if (fields.length === 0) {
    return (
      <div style={styles.empty}>
        <p>No RDMP fields defined for this project.</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Sample ID</th>
              {fields.map((field) => (
                <th key={field.key} style={styles.th}>
                  <div style={styles.headerContent}>
                    <span>{field.key}</span>
                    <span style={styles.fieldType}>
                      {field.type}
                      {field.required && <span style={styles.required}>*</span>}
                    </span>
                  </div>
                </th>
              ))}
              <th style={styles.th}>Files</th>
              <th style={styles.th}>Status</th>
            </tr>
          </thead>
          <tbody>
            {samples.map((sample) => (
              <tr key={sample.id} style={styles.row}>
                <td style={styles.td}>
                  <span style={styles.sampleId}>{sample.sample_identifier}</span>
                </td>
                {fields.map((field) => (
                  <td key={field.key} style={styles.td}>
                    {renderFieldValue(sample.fields[field.key], field)}
                  </td>
                ))}
                <td style={styles.td}>
                  <span style={styles.fileCount}>
                    {rawDataCountBySample[sample.id] || 0}
                  </span>
                </td>
                <td style={styles.td}>
                  {sample.completeness.is_complete ? (
                    <span style={styles.complete}>Complete</span>
                  ) : (
                    <span style={styles.incomplete}>
                      Missing: {sample.completeness.missing_fields.join(', ')}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={styles.legend}>
        <span style={styles.legendItem}>
          <span style={styles.required}>*</span> Required field
        </span>
        <span style={styles.legendItem}>
          {samples.length} sample{samples.length !== 1 ? 's' : ''}
        </span>
        <span style={styles.legendItem}>
          {fields.length} field{fields.length !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  );
}

function renderFieldValue(value: unknown, field: RDMPField): React.ReactNode {
  if (value === undefined || value === null) {
    return <span style={styles.empty}>-</span>;
  }

  switch (field.type) {
    case 'number':
      return <span style={styles.number}>{String(value)}</span>;
    case 'date':
      return <span style={styles.date}>{String(value)}</span>;
    case 'categorical':
      return <span style={styles.categorical}>{String(value)}</span>;
    default:
      return <span>{String(value)}</span>;
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    marginTop: '20px',
  },
  tableWrapper: {
    overflowX: 'auto',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    background: 'white',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '14px',
  },
  th: {
    padding: '12px 16px',
    textAlign: 'left',
    background: '#f9fafb',
    borderBottom: '2px solid #e5e7eb',
    fontWeight: 600,
    color: '#374151',
    whiteSpace: 'nowrap',
  },
  headerContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  fieldType: {
    fontSize: '11px',
    fontWeight: 400,
    color: '#9ca3af',
  },
  required: {
    color: '#dc2626',
    marginLeft: '2px',
  },
  row: {
    borderBottom: '1px solid #e5e7eb',
  },
  td: {
    padding: '12px 16px',
    verticalAlign: 'top',
  },
  sampleId: {
    fontWeight: 500,
    color: '#2563eb',
  },
  empty: {
    color: '#9ca3af',
    fontStyle: 'italic',
  },
  number: {
    fontFamily: 'monospace',
    color: '#059669',
  },
  date: {
    color: '#7c3aed',
  },
  categorical: {
    background: '#e0e7ff',
    color: '#3730a3',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '12px',
  },
  fileCount: {
    background: '#f3f4f6',
    color: '#4b5563',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: 500,
  },
  complete: {
    color: '#059669',
    fontWeight: 500,
  },
  incomplete: {
    color: '#dc2626',
    fontSize: '12px',
  },
  loading: {
    padding: '40px',
    textAlign: 'center',
    color: '#666',
  },
  legend: {
    marginTop: '12px',
    display: 'flex',
    gap: '20px',
    fontSize: '12px',
    color: '#6b7280',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
};
