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
