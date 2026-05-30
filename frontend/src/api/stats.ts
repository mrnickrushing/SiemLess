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
    const response = await fetch('/health');
    return response.ok;
  } catch {
    return false;
  }
}

export interface AlertTimelinePoint {
  /** ISO-8601 UTC hour bucket, e.g. "2026-05-25T14:00:00Z" */
  hour: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

export async function getAlertTimeline(hours = 24): Promise<AlertTimelinePoint[]> {
  try {
    const response = await client.get<{ hours: number; since: string; timeline: AlertTimelinePoint[] }>(
      `/stats/alert-trend?hours=${hours}`
    );
    return response.data.timeline ?? [];
  } catch {
    return [];
  }
}
