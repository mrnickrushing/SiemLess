import client from './client';
import type { SecurityEvent, PaginatedResponse } from '../types';

export interface SearchResult {
  items: SecurityEvent[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  query: string;
  took_ms: number;
}

export async function searchEvents(
  query: string,
  page = 1,
  pageSize = 50
): Promise<SearchResult> {
  const params = new URLSearchParams({
    q: query,
    page: String(page),
    page_size: String(pageSize),
  });
  const response = await client.get<SearchResult>(`/search?${params.toString()}`);
  return response.data;
}

export async function searchEventsPost(
  query: string,
  page = 1,
  pageSize = 50
): Promise<PaginatedResponse<SecurityEvent> & { took_ms?: number }> {
  const response = await client.post<PaginatedResponse<SecurityEvent> & { took_ms?: number }>(
    '/search',
    { query, page, page_size: pageSize }
  );
  return response.data;
}
