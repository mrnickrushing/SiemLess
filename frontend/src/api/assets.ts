import client from './client';
import type { Asset, AssetSoftware, AssetVulnerability, SecurityEvent, PaginatedResponse } from '../types';

/**
 * Fetches a paginated list of assets with optional pagination and filter parameters.
 *
 * @param params - Query options for listing assets. Supported fields:
 *   - `page`: Page number to retrieve.
 *   - `page_size`: Number of items per page.
 *   - `search`: Full-text search string to filter assets.
 *   - `criticality`: Filter by asset criticality.
 *   - `asset_type`: Filter by asset type.
 * @returns A paginated response containing matching `Asset` objects and pagination metadata.
 */
export async function getAssets(params: {
  page?: number;
  page_size?: number;
  search?: string;
  criticality?: string;
  asset_type?: string;
} = {}): Promise<PaginatedResponse<Asset>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  if (params.search) q.set('search', params.search);
  if (params.criticality) q.set('criticality', params.criticality);
  if (params.asset_type) q.set('asset_type', params.asset_type);
  const res = await client.get<PaginatedResponse<Asset>>(`/assets?${q.toString()}`);
  return res.data;
}

/**
 * Fetches an asset by its identifier.
 *
 * @param id - The asset's unique identifier.
 * @returns The asset corresponding to `id`.
 */
export async function getAsset(id: string): Promise<Asset> {
  const res = await client.get<Asset>(`/assets/${id}`);
  return res.data;
}

/**
 * Update one or more fields of an asset identified by `id`.
 *
 * @param id - The asset's unique identifier
 * @param data - Partial update payload. Supported fields: `tags`, `criticality`, and `asset_type`
 * @returns The updated `Asset`
 */
export async function updateAsset(
  id: string,
  data: Partial<{ tags: string[]; criticality: string; asset_type: string }>
): Promise<Asset> {
  const res = await client.patch<Asset>(`/assets/${id}`, data);
  return res.data;
}

/**
 * Delete the asset with the given ID.
 *
 * @param id - The asset's unique identifier
 */
export async function deleteAsset(id: string): Promise<void> {
  await client.delete(`/assets/${id}`);
}

/**
 * Retrieves the software installed on a specific asset.
 *
 * @param id - The asset identifier
 * @returns A list of `AssetSoftware` objects associated with the asset
 */
export async function getAssetSoftware(id: string): Promise<AssetSoftware[]> {
  const res = await client.get<AssetSoftware[]>(`/assets/${id}/software`);
  return res.data;
}

/**
 * Fetches vulnerabilities associated with a specific asset.
 *
 * @param id - The asset identifier
 * @returns An array of `AssetVulnerability` objects for the specified asset
 */
export async function getAssetVulnerabilities(id: string): Promise<AssetVulnerability[]> {
  const res = await client.get<AssetVulnerability[]>(`/assets/${id}/vulnerabilities`);
  return res.data;
}

/**
 * Fetches paginated security events for the specified asset.
 *
 * @param params - Optional pagination parameters:
 *   - `page`: Page number to retrieve.
 *   - `page_size`: Number of items per page.
 * @returns A paginated response containing `SecurityEvent` items for the asset.
 */
export async function getAssetEvents(
  id: string,
  params: { page?: number; page_size?: number } = {}
): Promise<PaginatedResponse<SecurityEvent>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  const res = await client.get<PaginatedResponse<SecurityEvent>>(`/assets/${id}/events?${q.toString()}`);
  return res.data;
}

/**
 * Trigger a CVE scan for the specified asset.
 *
 * @param id - The asset identifier
 * @returns An object with `message` (status message) and `cve_count` (number of CVEs discovered or queued)
 */
export async function scanAssetCVEs(id: string): Promise<{ message: string; cve_count: number }> {
  const res = await client.post<{ message: string; cve_count: number }>(`/assets/${id}/scan-cves`);
  return res.data;
}
