import client from './client';
import type { SavedSearch } from '../types';

interface SavedSearchList {
  total: number;
  items: SavedSearch[];
}

export async function getSavedSearches(): Promise<SavedSearch[]> {
  const response = await client.get<SavedSearchList>('/saved-searches');
  return response.data.items;
}

export async function createSavedSearch(data: { name: string; description?: string; query: string }): Promise<SavedSearch> {
  const response = await client.post<SavedSearch>('/saved-searches', data);
  return response.data;
}

export async function updateSavedSearch(id: string, data: Partial<{ name: string; description: string; query: string }>): Promise<SavedSearch> {
  const response = await client.put<SavedSearch>(`/saved-searches/${id}`, data);
  return response.data;
}

export async function deleteSavedSearch(id: string): Promise<void> {
  await client.delete(`/saved-searches/${id}`);
}
