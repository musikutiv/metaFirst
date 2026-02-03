import { useMemo } from 'react';
import type { RemediationTask, Sample, RawDataItem, RDMPVersion, PendingIngest, StorageRoot } from '../types';

interface UseRemediationTasksParams {
  projectId: number | null;
  samples: Sample[];
  rawData: RawDataItem[];
  activeRDMP: RDMPVersion | null;
  pendingIngests: PendingIngest[];
  storageRoots: StorageRoot[];
  hasDraftRDMP: boolean;
}

export function useRemediationTasks({
  projectId,
  samples,
  rawData,
  activeRDMP,
  pendingIngests,
  storageRoots,
  hasDraftRDMP,
}: UseRemediationTasksParams): RemediationTask[] {
  return useMemo(() => {
    if (!projectId) return [];

    const tasks: RemediationTask[] = [];

    // 1. No active RDMP - URGENT
    if (!activeRDMP) {
      if (hasDraftRDMP) {
        tasks.push({
          id: 'rdmp-draft',
          priority: 'urgent',
          title: 'Activate your RDMP draft',
          reason: 'A draft RDMP exists but has not been activated.',
          impact: 'Data ingestion and sample creation are blocked until an RDMP is active.',
          steps: [
            'Go to the RDMPs tab',
            'Review your draft RDMP content',
            'Click "Activate" to make it the active RDMP (requires PI role)',
          ],
          learnMore: 'Activating an RDMP enables all project operations including data ingestion, sample creation, and metadata editing. This action requires PI approval and will set the data management policies for your project.',
          actionPath: '/rdmps',
          actionLabel: 'Go to RDMPs',
          entityType: 'rdmp',
        });
      } else {
        tasks.push({
          id: 'rdmp-missing',
          priority: 'urgent',
          title: 'Create an RDMP for this project',
          reason: 'No Research Data Management Plan exists for this project.',
          impact: 'Data ingestion and sample creation are blocked until an RDMP is created and activated.',
          steps: [
            'Go to the RDMPs tab',
            'Click "Create RDMP"',
            'Define your metadata fields and policies',
            'Have a PI activate the RDMP',
          ],
          learnMore: 'An RDMP (Research Data Management Plan) defines how data is organized in your project, including required metadata fields, access policies, and file naming conventions. You need an active RDMP before you can ingest data.',
          actionPath: '/rdmps',
          actionLabel: 'Create RDMP',
          entityType: 'rdmp',
        });
      }
    }

    // 2. No storage roots configured - URGENT (if RDMP is active)
    if (activeRDMP && storageRoots.length === 0) {
      tasks.push({
        id: 'storage-missing',
        priority: 'urgent',
        title: 'Configure a storage root',
        reason: 'No storage location is configured for data ingestion.',
        impact: 'You cannot ingest data files until a storage root is set up.',
        steps: [
          'Go to Settings',
          'Add a storage root pointing to your data location',
          'Verify the path is accessible',
        ],
        learnMore: 'A storage root tells the system where to look for new data files. Once configured, files placed in this location can be ingested into your project and linked to samples.',
        actionPath: '/settings',
        actionLabel: 'Go to Settings',
        entityType: 'project',
        entityId: projectId,
      });
    }

    // 3. Pending ingests waiting for review - RECOMMENDED
    const pendingCount = pendingIngests.filter(i => i.status === 'PENDING').length;
    if (pendingCount > 0) {
      tasks.push({
        id: 'pending-ingests',
        priority: 'recommended',
        title: `Review ${pendingCount} pending ingest${pendingCount > 1 ? 's' : ''}`,
        reason: `${pendingCount} file${pendingCount > 1 ? 's are' : ' is'} waiting to be linked to samples.`,
        impact: 'Data files remain in the inbox until reviewed and assigned to samples.',
        steps: [
          'Go to the Ingest Inbox',
          'Review each pending file',
          'Assign to an existing sample or create a new one',
          'Complete the ingestion to link the file',
        ],
        learnMore: 'Pending ingests are data files that have been detected but not yet linked to samples. Review each file to ensure it is correctly associated with the right sample and has proper metadata.',
        actionPath: '/inbox',
        actionLabel: 'Open Inbox',
        entityType: 'ingest',
      });
    }

    // 4. Incomplete sample metadata - RECOMMENDED
    const incompleteSamples = samples.filter(s => !s.completeness.is_complete);
    if (incompleteSamples.length > 0) {
      // Group by number of missing fields for priority
      const highPriority = incompleteSamples.filter(s => s.completeness.missing_fields.length >= 3);
      const lowPriority = incompleteSamples.filter(s => s.completeness.missing_fields.length < 3);

      if (highPriority.length > 0) {
        tasks.push({
          id: 'metadata-incomplete-high',
          priority: 'recommended',
          title: `Complete metadata for ${highPriority.length} sample${highPriority.length > 1 ? 's' : ''}`,
          reason: `${highPriority.length} sample${highPriority.length > 1 ? 's have' : ' has'} 3 or more missing required fields.`,
          impact: 'Incomplete metadata may affect data discoverability and compliance.',
          steps: [
            'Go to the Metadata Table',
            'Click on a sample to view details',
            'Fill in the missing required fields',
            'Save your changes',
          ],
          learnMore: 'Required metadata fields help ensure your data is properly documented and can be found by collaborators. The specific fields required are defined in your project RDMP.',
          actionPath: '/',
          actionLabel: 'View Samples',
          entityType: 'sample',
        });
      }

      if (lowPriority.length > 0 && highPriority.length === 0) {
        tasks.push({
          id: 'metadata-incomplete-low',
          priority: 'recommended',
          title: `Complete metadata for ${lowPriority.length} sample${lowPriority.length > 1 ? 's' : ''}`,
          reason: `${lowPriority.length} sample${lowPriority.length > 1 ? 's have' : ' has'} missing required fields.`,
          impact: 'Completing metadata improves data organization.',
          steps: [
            'Go to the Metadata Table',
            'Click on a sample to view details',
            'Fill in the missing fields',
          ],
          learnMore: 'Required metadata fields help ensure your data is properly documented. The specific fields required are defined in your project RDMP.',
          actionPath: '/',
          actionLabel: 'View Samples',
          entityType: 'sample',
        });
      }
    }

    // 5. Orphaned raw data (not linked to samples) - RECOMMENDED
    const orphanedData = rawData.filter(r => r.sample_id === null);
    if (orphanedData.length > 0) {
      tasks.push({
        id: 'orphaned-data',
        priority: 'recommended',
        title: `Link ${orphanedData.length} orphaned file${orphanedData.length > 1 ? 's' : ''} to samples`,
        reason: `${orphanedData.length} data file${orphanedData.length > 1 ? 's are' : ' is'} not linked to any sample.`,
        impact: 'Orphaned files are harder to find and may lack proper context.',
        steps: [
          'Review the orphaned files in the data view',
          'Identify which sample each file belongs to',
          'Update the file association',
        ],
        learnMore: 'Data files that are not linked to samples may be difficult to find later and lack the metadata context that helps with organization. Linking files to samples ensures they are properly catalogued.',
        actionPath: '/',
        actionLabel: 'View Data',
        entityType: 'data',
      });
    }

    return tasks;
  }, [projectId, samples, rawData, activeRDMP, pendingIngests, storageRoots, hasDraftRDMP]);
}
