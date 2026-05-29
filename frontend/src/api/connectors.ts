import client from './client';
import type { CloudConnector, ConnectorType, PaginatedResponse } from '../types';

/**
 * Fetches a paginated list of cloud connectors.
 *
 * @param params - Optional pagination parameters.
 * @param params.page - The page number to retrieve.
 * @param params.page_size - The number of items per page.
 * @returns A paginated response containing `CloudConnector` items.
 */
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

/**
 * Fetches a connector by its identifier.
 *
 * @param id - The connector identifier used in the API path
 * @returns The requested `CloudConnector` object
 */
export async function getConnector(id: string): Promise<CloudConnector> {
  const res = await client.get<CloudConnector>(`/connectors/${id}`);
  return res.data;
}

/**
 * Create a new cloud connector using the provided configuration.
 *
 * @param data - Connector attributes:
 *   - `name`: Human-readable connector name.
 *   - `connector_type`: Type identifier for the connector.
 *   - `config`: Connector-specific configuration object.
 *   - `enabled` (optional): Whether the connector is enabled.
 * @returns The created `CloudConnector` object
 */
export async function createConnector(data: {
  name: string;
  connector_type: ConnectorType;
  config: Record<string, unknown>;
  enabled?: boolean;
}): Promise<CloudConnector> {
  const res = await client.post<CloudConnector>('/connectors', data);
  return res.data;
}

/**
 * Updates fields of an existing cloud connector.
 *
 * @param id - The identifier of the connector to update.
 * @param data - Partial connector properties to update; may include `name`, `config`, and `enabled`.
 * @returns The updated CloudConnector object.
 */
export async function updateConnector(
  id: string,
  data: Partial<{ name: string; config: Record<string, unknown>; enabled: boolean }>
): Promise<CloudConnector> {
  const res = await client.patch<CloudConnector>(`/connectors/${id}`, data);
  return res.data;
}

/**
 * Deletes a connector by its identifier.
 *
 * @param id - The connector's ID
 */
export async function deleteConnector(id: string): Promise<void> {
  await client.delete(`/connectors/${id}`);
}

/**
 * Triggers an ingestion poll for the specified connector.
 *
 * @param id - The connector's unique identifier
 * @returns An object containing a human-readable `message` and the number of `events_ingested`
 */
export async function pollConnector(id: string): Promise<{ message: string; events_ingested: number }> {
  const res = await client.post<{ message: string; events_ingested: number }>(`/connectors/${id}/poll`);
  return res.data;
}

/**
 * Fetches status information for a connector.
 *
 * @param id - The connector's unique identifier
 * @returns An object containing connector status:
 * - `id`: Connector identifier
 * - `name`: Connector name
 * - `enabled`: Whether the connector is enabled
 * - `last_polled_at`: ISO timestamp of the last poll, or `null` if never polled
 * - `last_error`: Last error message, or `null` if none
 * - `events_ingested`: Number of events ingested by the connector
 */
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
