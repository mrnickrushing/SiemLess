import client from './client';
import type { RetentionPolicy, PaginatedResponse } from '../types';

/**
 * Retrieve a paginated list of retention policies.
 *
 * @param params - Optional pagination parameters
 * @param params.page - Page number to return
 * @param params.page_size - Number of items per page
 * @returns A paginated response containing `RetentionPolicy` items
 */
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

/**
 * Fetches a retention policy by its identifier.
 *
 * @param id - The retention policy identifier
 * @returns The requested `RetentionPolicy`
 */
export async function getRetentionPolicy(id: string): Promise<RetentionPolicy> {
  const res = await client.get<RetentionPolicy>(`/retention/policies/${id}`);
  return res.data;
}

/**
 * Create a new retention policy.
 *
 * @param data - Policy attributes:
 *   - `name`: Display name for the policy
 *   - `hot_days`: Number of days to keep events in the hot tier
 *   - `cold_days` (optional): Number of days to keep events in the cold tier
 *   - `delete_after_cold` (optional): Whether events should be deleted after the cold tier
 *   - `enabled` (optional): Whether the policy is active
 * @returns The created `RetentionPolicy`
 */
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

/**
 * Updates fields of an existing retention policy.
 *
 * @param id - The identifier of the retention policy to update.
 * @param data - Partial set of policy fields to modify; may include `name`, `hot_days`, `cold_days`, `delete_after_cold`, and `enabled`.
 * @returns The updated `RetentionPolicy`.
 */
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

/**
 * Delete a retention policy by its identifier.
 *
 * @param id - The identifier of the retention policy to delete
 */
export async function deleteRetentionPolicy(id: string): Promise<void> {
  await client.delete(`/retention/policies/${id}`);
}

/**
 * Retrieve aggregated retention event counts.
 *
 * @returns An object containing `hot_events`, `cold_events`, and `total_events` counts.
 */
export async function getRetentionStats(): Promise<{
  hot_events: number;
  cold_events: number;
  total_events: number;
}> {
  const res = await client.get('/retention/stats');
  return res.data;
}

/**
 * Triggers an immediate retention run on the server.
 *
 * @returns The response object containing a `message` string describing the result
 */
export async function runRetentionNow(): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>('/retention/run');
  return res.data;
}
