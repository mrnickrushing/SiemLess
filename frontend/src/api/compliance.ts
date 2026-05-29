import client from './client';
import type { ComplianceReport, ComplianceFramework, PaginatedResponse } from '../types';

/**
 * Fetches a paginated list of compliance reports, optionally filtered by framework and paginated.
 *
 * @param params - Query options for the request.
 * @param params.page - Page number to retrieve.
 * @param params.page_size - Number of items per page.
 * @param params.framework - Compliance framework to filter results by.
 * @returns A paginated response containing compliance reports.
 */
export async function getComplianceReports(params: {
  page?: number;
  page_size?: number;
  framework?: ComplianceFramework;
} = {}): Promise<PaginatedResponse<ComplianceReport>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  if (params.framework) q.set('framework', params.framework);
  const res = await client.get<PaginatedResponse<ComplianceReport>>(`/compliance/reports?${q.toString()}`);
  return res.data;
}

/**
 * Fetches a compliance report by its identifier.
 *
 * @param id - The compliance report identifier
 * @returns The requested `ComplianceReport`
 */
export async function getComplianceReport(id: string): Promise<ComplianceReport> {
  const res = await client.get<ComplianceReport>(`/compliance/reports/${id}`);
  return res.data;
}

/**
 * Requests generation of a compliance report for the given framework and optional reporting period.
 *
 * @param framework - The compliance framework to generate the report for
 * @param periodStart - ISO 8601 start date of the reporting period (inclusive), if applicable
 * @param periodEnd - ISO 8601 end date of the reporting period (inclusive), if applicable
 * @returns The newly created compliance report
 */
export async function generateComplianceReport(
  framework: ComplianceFramework,
  periodStart?: string,
  periodEnd?: string
): Promise<ComplianceReport> {
  const res = await client.post<ComplianceReport>('/compliance/reports', {
    framework,
    period_start: periodStart,
    period_end: periodEnd,
  });
  return res.data;
}

/**
 * Trigger a browser download of the compliance report CSV for the given report id.
 *
 * @param id - The compliance report identifier
 * @throws Error if the server responds with a non-OK status
 */
export async function downloadComplianceCSV(id: string): Promise<void> {
  const res = await fetch(`/api/v1/compliance/reports/${id}/csv`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to download CSV');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `compliance-${id}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
