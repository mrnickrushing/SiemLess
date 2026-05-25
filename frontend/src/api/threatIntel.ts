import client from './client';
import type { ThreatIndicator, ThreatCheckResult, ThreatIndicatorFormData, PaginatedResponse } from '../types';

export interface ThreatIntelStats {
  total: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  active: number;
}

export async function getThreatIndicators(
  page = 1,
  pageSize = 50,
  type?: string
): Promise<PaginatedResponse<ThreatIndicator>> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (type) params.set('type', type);
  const response = await client.get<PaginatedResponse<ThreatIndicator>>(`/threat-intel?${params.toString()}`);
  return response.data;
}

export async function getThreatIntelStats(): Promise<ThreatIntelStats> {
  const response = await client.get<ThreatIntelStats>('/threat-intel/stats');
  return response.data;
}

export async function checkThreatIndicator(value: string): Promise<ThreatCheckResult> {
  const response = await client.get<ThreatCheckResult>(`/threat-intel/check?value=${encodeURIComponent(value)}`);
  return response.data;
}

export async function createThreatIndicator(data: ThreatIndicatorFormData): Promise<ThreatIndicator> {
  const response = await client.post<ThreatIndicator>('/threat-intel', data);
  return response.data;
}

export async function deleteThreatIndicator(id: string): Promise<void> {
  await client.delete(`/threat-intel/${id}`);
}
