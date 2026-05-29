import client from './client';
import type { CloudConnector, ConnectorType, PaginatedResponse } from '../types';

export async function getConnectors(params: {
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResponse<CloudConnector>> {
  const q = new URLSearchParams();
  if (params.page !== undefined) q.set('page', String(params.page));
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size));
  const res = await client.get<PaginatedResponse<CloudConnector>>(`/connectors?${q.toString()}`);
  return res.data;
}

export async function getConnector(id: string): Promise<CloudConnector> {
  const res = await client.get<CloudConnector>(`/connectors/${id}`);
  return res.data;
}

export async function createConnector(data: {
  name: string;
  connector_type: ConnectorType;
  config: Record<string, unknown>;
  enabled?: boolean;
}): Promise<CloudConnector> {
  const res = await client.post<CloudConnector>('/connectors', data);
  return res.data;
}

export async function updateConnector(
  id: string,
  data: Partial<{ name: string; config: Record<string, unknown>; enabled: boolean }>
): Promise<CloudConnector> {
  const res = await client.patch<CloudConnector>(`/connectors/${id}`, data);
  return res.data;
}

export async function deleteConnector(id: string): Promise<void> {
  await client.delete(`/connectors/${id}`);
}

export async function pollConnector(id: string): Promise<{ message: string; events_ingested: number }> {
  const res = await client.post<{ message: string; events_ingested: number }>(`/connectors/${id}/poll`);
  return res.data;
}

export async function getConnectorStatus(id: string): Promise<{
  id: string;
  name: string;
  enabled: boolean;
  last_polled_at: string | null;
  last_error: string | null;
  events_ingested: number;
}> {
  const res = await client.get(`/connectors/${id}/status`);
  return res.data;
}
