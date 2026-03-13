import type { FileAnnotation, Sample } from '../types';

interface MeasuredSamplesTableProps {
  annotations: FileAnnotation[];
  samples: Sample[];
}

export function MeasuredSamplesTable({ annotations, samples }: MeasuredSamplesTableProps) {
  const sampleById = new Map(samples.map((s) => [s.id, s]));

  const renderValue = (ann: FileAnnotation): string => {
    if (ann.value_text !== null && ann.value_text !== undefined) return ann.value_text;
    if (ann.value_json !== null && ann.value_json !== undefined) return JSON.stringify(ann.value_json);
    return '-';
  };

  const renderIndex = (ann: FileAnnotation): string => {
    if (ann.index === null || ann.index === undefined) return '-';
    return JSON.stringify(ann.index);
  };

  return (
    <table style={styles.table}>
      <thead>
        <tr>
          <th style={styles.th}>Sample</th>
          <th style={styles.th}>Key</th>
          <th style={styles.th}>Value</th>
          <th style={styles.th}>Index</th>
        </tr>
      </thead>
      <tbody>
        {annotations.map((ann) => {
          const sample = ann.sample_id !== null ? sampleById.get(ann.sample_id) : undefined;
          return (
            <tr key={ann.id} style={styles.row}>
              <td style={styles.td}>
                <span style={styles.sampleId}>
                  {sample?.sample_identifier ?? (ann.sample_id !== null ? `#${ann.sample_id}` : '—')}
                </span>
              </td>
              <td style={styles.td}>
                <code style={styles.code}>{ann.key}</code>
              </td>
              <td style={styles.td}>{renderValue(ann)}</td>
              <td style={styles.td}>
                <span style={styles.index}>{renderIndex(ann)}</span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

const styles: Record<string, React.CSSProperties> = {
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '13px',
  },
  th: {
    padding: '8px 10px',
    textAlign: 'left',
    fontWeight: 600,
    color: '#374151',
    background: '#f9fafb',
    borderBottom: '1px solid #e5e7eb',
    whiteSpace: 'nowrap',
  },
  row: {
    borderBottom: '1px solid #f3f4f6',
  },
  td: {
    padding: '8px 10px',
    verticalAlign: 'top',
    color: '#111827',
  },
  sampleId: {
    fontWeight: 500,
    color: '#2563eb',
  },
  code: {
    fontFamily: 'monospace',
    background: '#f3f4f6',
    padding: '1px 4px',
    borderRadius: '3px',
  },
  index: {
    fontFamily: 'monospace',
    color: '#6b7280',
    fontSize: '12px',
  },
};
