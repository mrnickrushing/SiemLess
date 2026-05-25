import client from './client';
import type { CorrelationRule, RuleFormData, PaginatedResponse } from '../types';

export async function getRules(page = 1, pageSize = 50): Promise<PaginatedResponse<CorrelationRule>> {
  const response = await client.get<PaginatedResponse<CorrelationRule>>(
    `/rules?page=${page}&page_size=${pageSize}`
  );
  return response.data;
}

export async function getRule(id: string): Promise<CorrelationRule> {
  const response = await client.get<CorrelationRule>(`/rules/${id}`);
  return response.data;
}

export async function createRule(data: RuleFormData): Promise<CorrelationRule> {
  const response = await client.post<CorrelationRule>('/rules', data);
  return response.data;
}

export async function updateRule(id: string, data: Partial<RuleFormData>): Promise<CorrelationRule> {
  const response = await client.put<CorrelationRule>(`/rules/${id}`, data);
  return response.data;
}

export async function toggleRule(id: string, enabled: boolean): Promise<CorrelationRule> {
  const response = await client.patch<CorrelationRule>(`/rules/${id}/toggle`, { enabled });
  return response.data;
}

export async function deleteRule(id: string): Promise<void> {
  await client.delete(`/rules/${id}`);
}
