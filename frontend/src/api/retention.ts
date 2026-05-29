import client from './client';
import type { RetentionPolicy, PaginatedResponse } from '../types';

export async function getRetentionPolicies(params: {
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResponse<RetentionPolicy>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  const res = await client.get<PaginatedResponse<RetentionPolicy>>(`/retention/policies?${q.toString()}`);
  return res.data;
}

export async function getRetentionPolicy(id: string): Promise<RetentionPolicy> {
  const res = await client.get<RetentionPolicy>(`/retention/policies/${id}`);
  return res.data;
}

export async function createRetentionPolicy(data: {
  name: string;
  hot_days: number;
  cold_days?: number;
  delete_after_cold?: boolean;
  enabled?: boolean;
}): Promise<RetentionPolicy> {
  const res = await client.post<RetentionPolicy>('/retention/policies', data);
  return res.data;
}

export async function updateRetentionPolicy(
  id: string,
  data: Partial<{
    name: string;
    hot_days: number;
    cold_days: number;
    delete_after_cold: boolean;
    enabled: boolean;
  }>
): Promise<RetentionPolicy> {
  const res = await client.patch<RetentionPolicy>(`/retention/policies/${id}`, data);
  return res.data;
}

export async function deleteRetentionPolicy(id: string): Promise<void> {
  await client.delete(`/retention/policies/${id}`);
}

export async function getRetentionStats(): Promise<{
  hot_events: number;
  cold_events: number;
  total_events: number;
}> {
  const res = await client.get('/retention/stats');
  return res.data;
}

export async function runRetentionNow(): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>('/retention/run');
  return res.data;
}
