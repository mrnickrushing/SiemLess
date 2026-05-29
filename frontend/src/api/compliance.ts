import client from './client';
import type { ComplianceReport, ComplianceFramework, PaginatedResponse } from '../types';

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

export async function getComplianceReport(id: string): Promise<ComplianceReport> {
  const res = await client.get<ComplianceReport>(`/compliance/reports/${id}`);
  return res.data;
}

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
