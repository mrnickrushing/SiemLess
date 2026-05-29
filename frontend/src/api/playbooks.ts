import client from './client';
import type { Playbook, PlaybookRun, PlaybookStep, PaginatedResponse } from '../types';

/**
 * Fetches a paginated list of playbooks.
 *
 * @param params - Optional pagination parameters.
 * @param params.page - Page number to retrieve.
 * @param params.page_size - Number of items per page.
 * @returns A `PaginatedResponse<Playbook>` containing playbooks for the requested page.
 */
export async function getPlaybooks(params: {
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResponse<Playbook>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  const res = await client.get(`/playbooks?${q.toString()}`);
  const raw = res.data;
  if (Array.isArray(raw)) {
    return { items: raw, total: raw.length, page: 1, page_size: raw.length, pages: 1 };
  }
  return raw as PaginatedResponse<Playbook>;
}

/**
 * Retrieve a playbook by its identifier.
 *
 * @param id - The playbook's unique identifier
 * @returns The requested Playbook
 */
export async function getPlaybook(id: string): Promise<Playbook> {
  const res = await client.get<Playbook>(`/playbooks/${id}`);
  return res.data;
}

/**
 * Create a new playbook.
 *
 * @param data - Playbook creation payload
 * @param data.name - Human-readable playbook name
 * @param data.description - Optional long-form description
 * @param data.trigger_on - Event or condition that triggers the playbook
 * @param data.conditions - Optional structured conditions evaluated before triggering
 * @param data.steps - Ordered list of steps that compose the playbook
 * @param data.enabled - Whether the playbook is enabled after creation
 * @returns The created `Playbook`
 */
export async function createPlaybook(data: {
  name: string;
  description?: string;
  trigger_on: string;
  conditions?: Record<string, unknown>;
  steps: PlaybookStep[];
  enabled?: boolean;
}): Promise<Playbook> {
  const res = await client.post<Playbook>('/playbooks', data);
  return res.data;
}

/**
 * Updates fields of a playbook identified by `id`.
 *
 * @param id - The playbook's unique identifier.
 * @param data - Partial set of playbook fields to update; may include `name`, `description`, `trigger_on`, `conditions`, `steps`, or `enabled`.
 * @returns The updated `Playbook`.
 */
export async function updatePlaybook(
  id: string,
  data: Partial<{
    name: string;
    description: string;
    trigger_on: string;
    conditions: Record<string, unknown>;
    steps: PlaybookStep[];
    enabled: boolean;
  }>
): Promise<Playbook> {
  const res = await client.patch<Playbook>(`/playbooks/${id}`, data);
  return res.data;
}

/**
 * Deletes the playbook identified by `id`.
 *
 * @param id - The ID of the playbook to delete
 */
export async function deletePlaybook(id: string): Promise<void> {
  await client.delete(`/playbooks/${id}`);
}

/**
 * Triggers a playbook run for the playbook identified by `id`.
 *
 * @param id - The playbook's unique identifier
 * @param alertId - Optional alert identifier to associate the run with a specific alert
 * @returns The created `PlaybookRun` representing the triggered execution
 */
export async function triggerPlaybook(id: string, alertId?: string): Promise<PlaybookRun> {
  const res = await client.post<PlaybookRun>(`/playbooks/${id}/trigger`, { alert_id: alertId });
  return res.data;
}

/**
 * Fetches paginated runs for a playbook.
 *
 * @param id - The playbook identifier to list runs for
 * @param params - Pagination options
 * @param params.page - Page number to retrieve
 * @param params.page_size - Number of items per page
 * @returns A paginated response containing `PlaybookRun` items
 */
export async function getPlaybookRuns(
  id: string,
  params: { page?: number; page_size?: number } = {}
): Promise<PaginatedResponse<PlaybookRun>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  const res = await client.get<PaginatedResponse<PlaybookRun>>(`/playbooks/${id}/runs?${q.toString()}`);
  return res.data;
}
