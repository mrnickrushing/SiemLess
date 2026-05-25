import client from './client';
import type { WatchlistEntry } from '../types';

interface WatchlistList {
  total: number;
  items: WatchlistEntry[];
}

export async function getWatchlist(params?: { entry_type?: string; q?: string }): Promise<WatchlistList> {
  const p = new URLSearchParams();
  if (params?.entry_type) p.set('entry_type', params.entry_type);
  if (params?.q) p.set('q', params.q);
  const response = await client.get<WatchlistList>(`/watchlist?${p.toString()}`);
  return response.data;
}

export async function createWatchlistEntry(data: {
  entry_type: string;
  value: string;
  label?: string;
  tags?: string[];
  notes?: string;
}): Promise<WatchlistEntry> {
  const response = await client.post<WatchlistEntry>('/watchlist', data);
  return response.data;
}

export async function deleteWatchlistEntry(id: string): Promise<void> {
  await client.delete(`/watchlist/${id}`);
}
