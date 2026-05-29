import client from './client';
import type { Asset, AssetSoftware, AssetVulnerability, SecurityEvent, PaginatedResponse } from '../types';

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

export async function getAsset(id: string): Promise<Asset> {
  const res = await client.get<Asset>(`/assets/${id}`);
  return res.data;
}

export async function updateAsset(
  id: string,
  data: Partial<{ tags: string[]; criticality: string; asset_type: string }>
): Promise<Asset> {
  const res = await client.patch<Asset>(`/assets/${id}`, data);
  return res.data;
}

export async function deleteAsset(id: string): Promise<void> {
  await client.delete(`/assets/${id}`);
}

export async function getAssetSoftware(id: string): Promise<AssetSoftware[]> {
  const res = await client.get<AssetSoftware[]>(`/assets/${id}/software`);
  return res.data;
}

export async function getAssetVulnerabilities(id: string): Promise<AssetVulnerability[]> {
  const res = await client.get<AssetVulnerability[]>(`/assets/${id}/vulnerabilities`);
  return res.data;
}

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

export async function scanAssetCVEs(id: string): Promise<{ message: string; cve_count: number }> {
  const res = await client.post<{ message: string; cve_count: number }>(`/assets/${id}/scan-cves`);
  return res.data;
}
