import client from './client';
import type { Playbook, PlaybookRun, PlaybookStep, PaginatedResponse } from '../types';

export async function getPlaybooks(params: {
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResponse<Playbook>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  const res = await client.get<PaginatedResponse<Playbook>>(`/playbooks?${q.toString()}`);
  return res.data;
}

export async function getPlaybook(id: string): Promise<Playbook> {
  const res = await client.get<Playbook>(`/playbooks/${id}`);
  return res.data;
}

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

export async function deletePlaybook(id: string): Promise<void> {
  await client.delete(`/playbooks/${id}`);
}

export async function triggerPlaybook(id: string, alertId?: string): Promise<PlaybookRun> {
  const res = await client.post<PlaybookRun>(`/playbooks/${id}/trigger`, { alert_id: alertId });
  return res.data;
}

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
