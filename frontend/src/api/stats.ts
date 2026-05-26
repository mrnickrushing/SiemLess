import client from './client';
import type { DashboardStats, StatsOverview } from '../types';

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await client.get<DashboardStats>('/stats/dashboard');
  return response.data;
}

export async function getStatsOverview(): Promise<StatsOverview> {
  const response = await client.get<StatsOverview>('/stats/overview');
  return response.data;
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    await client.get('/health');
    return true;
  } catch {
    return false;
  }
}

export interface AlertTimelinePoint {
  hour: string;   // e.g. "14:00"
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

export async function getAlertTimeline(hours = 24): Promise<AlertTimelinePoint[]> {
  try {
    const response = await client.get<AlertTimelinePoint[]>(`/stats/alert-timeline?hours=${hours}`);
    return response.data;
  } catch {
    // Gracefully return empty array if endpoint not yet available
    return [];
  }
}
