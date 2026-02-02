import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import type { Project } from '../types';

interface ProjectSettingsProps {
  project: Project;
  onProjectUpdated: (project: Project) => void;
}

export function ProjectSettings({ project, onProjectUpdated }: ProjectSettingsProps) {
  const [ruleType, setRuleType] = useState<string>(project.sample_id_rule_type || '');
  const [regex, setRegex] = useState<string>(project.sample_id_regex || '');
  const [testFilename, setTestFilename] = useState<string>('');
  const [testResult, setTestResult] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Reset form when project changes
  useEffect(() => {
    setRuleType(project.sample_id_rule_type || '');
    setRegex(project.sample_id_regex || '');
    setError(null);
    setSuccess(null);
  }, [project.id]);

  const testRegex = () => {
    if (!regex || !testFilename) {
      setTestResult(null);
      return;
    }

    try {
      const re = new RegExp(regex);
      const match = testFilename.match(re);

      if (!match) {
        setTestResult('No match');
        return;
      }

      // Check for named group 'sample_id' or fallback to group 1
      const groups = match.groups;
      if (groups && groups.sample_id) {
        setTestResult(`Match: "${groups.sample_id}"`);
      } else if (match[1]) {
        setTestResult(`Match (group 1): "${match[1]}"`);
      } else {
        setTestResult('Regex matches but no capture group found');
      }
    } catch (e) {
      setTestResult(`Invalid regex: ${e instanceof Error ? e.message : 'unknown error'}`);
    }
  };

  const handleSave = async () => {
    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      // Validate regex if provided
      if (regex) {
        try {
          new RegExp(regex);
        } catch (e) {
          throw new Error(`Invalid regex: ${e instanceof Error ? e.message : 'unknown error'}`);
        }
      }

      const updated = await apiClient.updateProject(project.id, {
        sample_id_rule_type: ruleType || null,
        sample_id_regex: regex || null,
      });

      onProjectUpdated(updated);
      setSuccess('Settings saved successfully');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      const updated = await apiClient.updateProject(project.id, {
        sample_id_rule_type: null,
        sample_id_regex: null,
      });

      setRuleType('');
      setRegex('');
      onProjectUpdated(updated);
      setSuccess('Sample ID rule cleared');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to clear settings');
    } finally {
      setSaving(false);
    }
  };

  const hasChanges =
    (ruleType || '') !== (project.sample_id_rule_type || '') ||
    (regex || '') !== (project.sample_id_regex || '');

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>Project Settings</h3>

      <div style={styles.section}>
        <h4 style={styles.sectionTitle}>Sample ID Extraction Rule</h4>
        <p style={styles.description}>
          Configure how sample IDs are automatically detected from filenames during ingest.
          The regex should include a named capture group <code>(?P&lt;sample_id&gt;...)</code> or
          a numbered capture group.
        </p>

        <div style={styles.formGroup}>
          <label style={styles.label}>Rule Type</label>
          <select
            style={styles.select}
            value={ruleType}
            onChange={(e) => setRuleType(e.target.value)}
          >
            <option value="">No automatic detection</option>
            <option value="filename_regex">Filename Regex</option>
          </select>
        </div>

        {ruleType === 'filename_regex' && (
          <>
            <div style={styles.formGroup}>
              <label style={styles.label}>Regex Pattern</label>
              <input
                type="text"
                style={styles.input}
                value={regex}
                onChange={(e) => setRegex(e.target.value)}
                placeholder="e.g., (?P<sample_id>SAMPLE-\d+)"
              />
              <p style={styles.hint}>
                Example patterns:
                <br />
                <code>(?P&lt;sample_id&gt;SAMPLE-\d+)</code> - matches "SAMPLE-001"
                <br />
                <code>^([A-Z]+\d+)_</code> - matches "ABC123" from "ABC123_data.txt"
              </p>
            </div>

            <div style={styles.testSection}>
              <label style={styles.label}>Test Your Regex</label>
              <div style={styles.testRow}>
                <input
                  type="text"
                  style={styles.testInput}
                  value={testFilename}
                  onChange={(e) => {
                    setTestFilename(e.target.value);
                    setTestResult(null);
                  }}
                  placeholder="Enter a test filename..."
                />
                <button
                  type="button"
                  style={styles.testButton}
                  onClick={testRegex}
                  disabled={!regex || !testFilename}
                >
                  Test
                </button>
              </div>
              {testResult && (
                <div
                  style={{
                    ...styles.testResult,
                    ...(testResult.startsWith('Match') ? styles.testSuccess : styles.testError),
                  }}
                >
                  {testResult}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {success && <div style={styles.success}>{success}</div>}

      <div style={styles.actions}>
        {(project.sample_id_rule_type || project.sample_id_regex) && (
          <button
            type="button"
            style={styles.clearButton}
            onClick={handleClear}
            disabled={saving}
          >
            Clear Rule
          </button>
        )}
        <button
          type="button"
          style={{
            ...styles.saveButton,
            ...(hasChanges ? {} : styles.saveButtonDisabled),
          }}
          onClick={handleSave}
          disabled={saving || !hasChanges}
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    padding: '24px',
    maxWidth: '700px',
  },
  title: {
    fontSize: '18px',
    fontWeight: 600,
    color: '#111827',
    margin: '0 0 24px 0',
  },
  section: {
    marginBottom: '24px',
  },
  sectionTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: '#374151',
    margin: '0 0 8px 0',
  },
  description: {
    fontSize: '14px',
    color: '#6b7280',
    marginBottom: '16px',
    lineHeight: 1.5,
  },
  formGroup: {
    marginBottom: '16px',
  },
  label: {
    display: 'block',
    fontSize: '14px',
    fontWeight: 500,
    color: '#374151',
    marginBottom: '6px',
  },
  select: {
    width: '100%',
    padding: '8px 12px',
    fontSize: '14px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    background: '#fff',
  },
  input: {
    width: '100%',
    padding: '8px 12px',
    fontSize: '14px',
    fontFamily: 'monospace',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    boxSizing: 'border-box',
  },
  hint: {
    fontSize: '12px',
    color: '#6b7280',
    marginTop: '8px',
    lineHeight: 1.6,
  },
  testSection: {
    marginTop: '16px',
    padding: '16px',
    background: '#f9fafb',
    borderRadius: '6px',
  },
  testRow: {
    display: 'flex',
    gap: '8px',
    marginTop: '8px',
  },
  testInput: {
    flex: 1,
    padding: '8px 12px',
    fontSize: '14px',
    fontFamily: 'monospace',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
  },
  testButton: {
    padding: '8px 16px',
    fontSize: '14px',
    background: '#f3f4f6',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    cursor: 'pointer',
  },
  testResult: {
    marginTop: '12px',
    padding: '8px 12px',
    borderRadius: '4px',
    fontSize: '13px',
    fontFamily: 'monospace',
  },
  testSuccess: {
    background: '#d1fae5',
    color: '#065f46',
  },
  testError: {
    background: '#fee2e2',
    color: '#991b1b',
  },
  error: {
    padding: '12px',
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '6px',
    color: '#dc2626',
    fontSize: '14px',
    marginBottom: '16px',
  },
  success: {
    padding: '12px',
    background: '#d1fae5',
    border: '1px solid #a7f3d0',
    borderRadius: '6px',
    color: '#065f46',
    fontSize: '14px',
    marginBottom: '16px',
  },
  actions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
  },
  clearButton: {
    padding: '10px 16px',
    fontSize: '14px',
    background: '#fff',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    color: '#6b7280',
    cursor: 'pointer',
  },
  saveButton: {
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: 500,
    background: '#2563eb',
    border: 'none',
    borderRadius: '6px',
    color: '#fff',
    cursor: 'pointer',
  },
  saveButtonDisabled: {
    background: '#9ca3af',
    cursor: 'not-allowed',
  },
};
