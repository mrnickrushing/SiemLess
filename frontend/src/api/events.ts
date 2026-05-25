import client from './client';
import type { SecurityEvent, PaginatedResponse, EventFilters } from '../types';

export async function getEvents(filters: EventFilters = {}): Promise<PaginatedResponse<SecurityEvent>> {
  const params = new URLSearchParams();
  if (filters.page !== undefined) params.set('page', String(filters.page));
  if (filters.page_size !== undefined) params.set('page_size', String(filters.page_size));
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.category) params.set('category', filters.category);
  if (filters.log_type) params.set('log_type', filters.log_type);
  if (filters.source_ip) params.set('source_ip', filters.source_ip);
  if (filters.hostname) params.set('hostname', filters.hostname);
  if (filters.start_time) params.set('start_time', filters.start_time);
  if (filters.end_time) params.set('end_time', filters.end_time);
  if (filters.search) params.set('search', filters.search);

  const response = await client.get<PaginatedResponse<SecurityEvent>>(`/events?${params.toString()}`);
  return response.data;
}

export async function getEvent(id: string): Promise<SecurityEvent> {
  const response = await client.get<SecurityEvent>(`/events/${id}`);
  return response.data;
}

export async function getEventCategories(): Promise<string[]> {
  const response = await client.get<string[]>('/events/categories');
  return response.data;
}

export async function getEventLogTypes(): Promise<string[]> {
  const response = await client.get<string[]>('/events/log-types');
  return response.data;
}
