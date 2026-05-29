import client from './client';
import type { Case, CaseComment, CaseArtifact, CaseTimelineItem, CaseCreate, Alert, PaginatedResponse } from '../types';

/**
 * Fetches a paginated list of cases, optionally filtered by status, severity, or assignee.
 *
 * @param params - Optional query parameters for pagination and filtering.
 * @param params.page - Page number to retrieve (1-based).
 * @param params.page_size - Number of items per page.
 * @param params.status - Case status to filter by.
 * @param params.severity - Case severity to filter by.
 * @param params.assigned_to - User identifier to filter cases assigned to that user.
 * @returns A `PaginatedResponse` containing `Case` items and pagination metadata.
 */
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

/**
 * Fetches a case by its ID.
 *
 * @param id - The case identifier
 * @returns The case identified by `id`
 */
export async function getCase(id: string): Promise<Case> {
  const res = await client.get<Case>(`/cases/${id}`);
  return res.data;
}

/**
 * Creates a new case record.
 *
 * @param data - The case properties used to create the case
 * @returns The created Case object
 */
export async function createCase(data: CaseCreate): Promise<Case> {
  const res = await client.post<Case>('/cases', data);
  return res.data;
}

/**
 * Updates an existing case with the provided fields.
 *
 * @param id - The identifier of the case to update
 * @param data - Partial case fields to apply; may include `status`
 * @returns The updated `Case` object
 */
export async function updateCase(
  id: string,
  data: Partial<CaseCreate & { status: string }>
): Promise<Case> {
  const res = await client.patch<Case>(`/cases/${id}`, data);
  return res.data;
}

/**
 * Delete a case by its identifier.
 *
 * @param id - The ID of the case to delete
 */
export async function deleteCase(id: string): Promise<void> {
  await client.delete(`/cases/${id}`);
}

/**
 * Retrieve the timeline items for a specific case.
 *
 * @param id - The case identifier
 * @returns The array of timeline items associated with the specified case
 */
export async function getCaseTimeline(id: string): Promise<CaseTimelineItem[]> {
  const res = await client.get<CaseTimelineItem[]>(`/cases/${id}/timeline`);
  return res.data;
}

/**
 * Retrieves the comments for a case.
 *
 * @param id - The case ID to fetch comments for
 * @returns An array of `CaseComment` objects associated with the specified case
 */
export async function getCaseComments(id: string): Promise<CaseComment[]> {
  const res = await client.get<CaseComment[]>(`/cases/${id}/comments`);
  return res.data;
}

/**
 * Adds a comment to the specified case.
 *
 * @param id - The ID of the case to add the comment to
 * @param body - The comment text
 * @returns The created `CaseComment`
 */
export async function addCaseComment(id: string, body: string): Promise<CaseComment> {
  const res = await client.post<CaseComment>(`/cases/${id}/comments`, { body });
  return res.data;
}

/**
 * Fetches artifacts associated with a case.
 *
 * @param id - The case ID to fetch artifacts for
 * @returns An array of `CaseArtifact` objects associated with the case
 */
export async function getCaseArtifacts(id: string): Promise<CaseArtifact[]> {
  const res = await client.get<CaseArtifact[]>(`/cases/${id}/artifacts`);
  return res.data;
}

/**
 * Adds a new artifact to a case.
 *
 * @param id - The case identifier to attach the artifact to.
 * @param data - Artifact payload.
 * @param data.artifact_type - The artifact type or category.
 * @param data.value - The artifact value.
 * @param data.description - Optional human-readable description of the artifact.
 * @returns The created `CaseArtifact`.
 */
export async function addCaseArtifact(
  id: string,
  data: { artifact_type: string; value: string; description?: string }
): Promise<CaseArtifact> {
  const res = await client.post<CaseArtifact>(`/cases/${id}/artifacts`, data);
  return res.data;
}

/**
 * Fetches alerts linked to the specified case.
 *
 * @param caseId - The unique identifier of the case whose linked alerts should be retrieved
 * @returns An array of alerts associated with the case
 */
export async function getCaseLinkedAlerts(caseId: string): Promise<Alert[]> {
  const res = await client.get<Alert[]>(`/cases/${caseId}/alerts`);
  return res.data;
}

/**
 * Link an alert to a case.
 *
 * @param caseId - The identifier of the case to link the alert to
 * @param alertId - The identifier of the alert to link
 */
export async function linkAlertToCase(caseId: string, alertId: string): Promise<void> {
  await client.post(`/cases/${caseId}/alerts/${alertId}`);
}

/**
 * Remove a linked alert from a case.
 *
 * @param caseId - The case's identifier
 * @param alertId - The alert's identifier to be unlinked from the case
 */
export async function unlinkAlertFromCase(caseId: string, alertId: string): Promise<void> {
  await client.delete(`/cases/${caseId}/alerts/${alertId}`);
}

/**
 * Creates a ticket for a case using the specified integration.
 *
 * @param caseId - ID of the case to create a ticket from
 * @param integrationId - Integration identifier used to create the ticket
 * @returns An object containing `ticket_url` and `ticket_id`
 */
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
