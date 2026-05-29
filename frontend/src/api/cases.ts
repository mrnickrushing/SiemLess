import client from './client';
import type { Case, CaseComment, CaseArtifact, CaseTimelineItem, CaseCreate, Alert, PaginatedResponse } from '../types';

export async function getCases(params: {
  page?: number;
  page_size?: number;
  status?: string;
  severity?: string;
  assigned_to?: string;
} = {}): Promise<PaginatedResponse<Case>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  if (params.status) q.set('status', params.status);
  if (params.severity) q.set('severity', params.severity);
  if (params.assigned_to) q.set('assigned_to', params.assigned_to);
  const res = await client.get<PaginatedResponse<Case>>(`/cases?${q.toString()}`);
  return res.data;
}

export async function getCase(id: string): Promise<Case> {
  const res = await client.get<Case>(`/cases/${id}`);
  return res.data;
}

export async function createCase(data: CaseCreate): Promise<Case> {
  const res = await client.post<Case>('/cases', data);
  return res.data;
}

export async function updateCase(
  id: string,
  data: Partial<CaseCreate & { status: string }>
): Promise<Case> {
  const res = await client.patch<Case>(`/cases/${id}`, data);
  return res.data;
}

export async function deleteCase(id: string): Promise<void> {
  await client.delete(`/cases/${id}`);
}

export async function getCaseTimeline(id: string): Promise<CaseTimelineItem[]> {
  const res = await client.get<CaseTimelineItem[]>(`/cases/${id}/timeline`);
  return res.data;
}

export async function getCaseComments(id: string): Promise<CaseComment[]> {
  const res = await client.get<CaseComment[]>(`/cases/${id}/comments`);
  return res.data;
}

export async function addCaseComment(id: string, body: string): Promise<CaseComment> {
  const res = await client.post<CaseComment>(`/cases/${id}/comments`, { body });
  return res.data;
}

export async function getCaseArtifacts(id: string): Promise<CaseArtifact[]> {
  const res = await client.get<CaseArtifact[]>(`/cases/${id}/artifacts`);
  return res.data;
}

export async function addCaseArtifact(
  id: string,
  data: { artifact_type: string; value: string; description?: string }
): Promise<CaseArtifact> {
  const res = await client.post<CaseArtifact>(`/cases/${id}/artifacts`, data);
  return res.data;
}

export async function getCaseLinkedAlerts(caseId: string): Promise<Alert[]> {
  const res = await client.get<Alert[]>(`/cases/${caseId}/alerts`);
  return res.data;
}

export async function linkAlertToCase(caseId: string, alertId: string): Promise<void> {
  await client.post(`/cases/${caseId}/alerts/${alertId}`);
}

export async function unlinkAlertFromCase(caseId: string, alertId: string): Promise<void> {
  await client.delete(`/cases/${caseId}/alerts/${alertId}`);
}

export async function createTicketFromCase(
  caseId: string,
  integrationId: string
): Promise<{ ticket_url: string; ticket_id: string }> {
  const res = await client.post<{ ticket_url: string; ticket_id: string }>(
    `/cases/${caseId}/ticket`,
    { integration_id: integrationId }
  );
  return res.data;
}
