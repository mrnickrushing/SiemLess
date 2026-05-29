import client from './client';
import type { UserBehaviorProfile, UEBAAnomaly, PaginatedResponse } from '../types';

export async function getUEBAProfiles(params: {
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResponse<UserBehaviorProfile>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  const res = await client.get<PaginatedResponse<UserBehaviorProfile>>(`/ueba/profiles?${q.toString()}`);
  return res.data;
}

export async function getUEBAProfile(username: string): Promise<UserBehaviorProfile> {
  const res = await client.get<UserBehaviorProfile>(`/ueba/profiles/${encodeURIComponent(username)}`);
  return res.data;
}

export async function getUEBAAnomalies(params: {
  page?: number;
  page_size?: number;
  username?: string;
  anomaly_type?: string;
  acknowledged?: boolean;
} = {}): Promise<PaginatedResponse<UEBAAnomaly>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  if (params.username) q.set('username', params.username);
  if (params.anomaly_type) q.set('anomaly_type', params.anomaly_type);
  if (params.acknowledged !== undefined) q.set('acknowledged', String(params.acknowledged));
  const res = await client.get<PaginatedResponse<UEBAAnomaly>>(`/ueba/anomalies?${q.toString()}`);
  return res.data;
}

export async function acknowledgeAnomaly(id: string): Promise<UEBAAnomaly> {
  const res = await client.post<UEBAAnomaly>(`/ueba/anomalies/${id}/acknowledge`);
  return res.data;
}

export async function refreshBaselines(): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>('/ueba/baselines/refresh');
  return res.data;
}
