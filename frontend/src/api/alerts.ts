import client from './client';
import type { Alert, AlertFilters, AlertUpdateData, PaginatedResponse } from '../types';

export async function getAlerts(filters: AlertFilters = {}): Promise<PaginatedResponse<Alert>> {
  const params = new URLSearchParams();
  if (filters.page !== undefined) params.set('page', String(filters.page));
  if (filters.page_size !== undefined) params.set('page_size', String(filters.page_size));
  if (filters.status) params.set('status', filters.status);
  if (filters.severity) params.set('severity', filters.severity);

  const response = await client.get<PaginatedResponse<Alert>>(`/alerts?${params.toString()}`);
  return response.data;
}

export async function getAlert(id: string): Promise<Alert> {
  const response = await client.get<Alert>(`/alerts/${id}`);
  return response.data;
}

export async function updateAlert(id: string, data: AlertUpdateData): Promise<Alert> {
  const response = await client.patch<Alert>(`/alerts/${id}`, data);
  return response.data;
}

export async function deleteAlert(id: string): Promise<void> {
  await client.delete(`/alerts/${id}`);
}
