import type { StorageRoot } from './types';

/**
 * Reconstruct the full local filesystem path for a file by joining the user's
 * storage root mount path with the file's relative path.
 *
 * Returns null when no mapping exists for the current user.
 */
export function getFullLocalPath(
  storageRoot: StorageRoot,
  relativePath: string,
): string | null {
  const mountPath = storageRoot.userMapping?.local_mount_path;
  if (!mountPath) return null;

  const base = mountPath.endsWith('/') ? mountPath.slice(0, -1) : mountPath;
  const rel = relativePath.startsWith('/') ? relativePath.slice(1) : relativePath;
  return `${base}/${rel}`;
}
