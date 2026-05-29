import client from './client';
import type { UserBehaviorProfile, UEBAAnomaly, PaginatedResponse } from '../types';

/**
 * Fetches a paginated list of user behavior profiles.
 *
 * @param params - Optional pagination parameters.
 * @param params.page - Page number to retrieve.
 * @param params.page_size - Number of items per page.
 * @returns A paginated response containing `UserBehaviorProfile` items.
 */
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

/**
 * Fetches the user behavior profile for a given username.
 *
 * @param username - The username of the profile to retrieve
 * @returns The `UserBehaviorProfile` for the specified username
 */
export async function getUEBAProfile(username: string): Promise<UserBehaviorProfile> {
  const res = await client.get<UserBehaviorProfile>(`/ueba/profiles/${encodeURIComponent(username)}`);
  return res.data;
}

/**
 * Fetches a paginated list of UEBA anomalies with optional filters.
 *
 * @param params - Optional query parameters to filter and paginate results
 * @param params.page - Page number to retrieve
 * @param params.page_size - Number of items per page
 * @param params.username - Filter anomalies by username
 * @param params.anomaly_type - Filter anomalies by anomaly type
 * @param params.acknowledged - Filter by acknowledgement state (`true` for acknowledged, `false` for unacknowledged)
 * @returns A paginated response containing `UEBAAnomaly` entries
 */
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

/**
 * Acknowledge an anomaly identified by its ID.
 *
 * @param id - The anomaly's unique identifier
 * @returns The acknowledged `UEBAAnomaly` record
 */
export async function acknowledgeAnomaly(id: string): Promise<UEBAAnomaly> {
  const res = await client.post<UEBAAnomaly>(`/ueba/anomalies/${id}/acknowledge`);
  return res.data;
}

/**
 * Triggers a server-side refresh of UEBA baselines.
 *
 * @returns An object containing a `message` string describing the result
 */
export async function refreshBaselines(): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>('/ueba/baselines/refresh');
  return res.data;
}
