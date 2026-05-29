import client from './client';

export interface SSOProvider {
  provider_name: string;
  scopes: string;
  login_url: string;
}

export interface SSOConfigRead {
  id: string;
  provider_name: string;
  client_id: string;
  client_secret_masked: string | null;
  authorization_endpoint: string;
  token_endpoint: string;
  userinfo_endpoint: string;
  jwks_uri: string | null;
  scopes: string;
  enabled: boolean;
  created_at: string;
}

export interface SSOConfigCreate {
  provider_name: string;
  client_id: string;
  client_secret: string;
  authorization_endpoint: string;
  token_endpoint: string;
  userinfo_endpoint: string;
  jwks_uri?: string;
  scopes?: string;
  enabled?: boolean;
}

export async function login(username: string, password: string): Promise<string> {
  const { data } = await client.post('/auth/login', { username, password });
  return data.username;
}

export async function logout(): Promise<void> {
  try {
    await client.post('/auth/logout');
  } finally {
    window.location.href = '/login';
  }
}

export async function getMe(): Promise<string | null> {
  try {
    const { data } = await client.get('/auth/me');
    return data.username as string;
  } catch {
    return null;
  }
}

export async function getSSOProviders(): Promise<SSOProvider[]> {
  try {
    const { data } = await client.get('/auth/oidc/providers');
    return data as SSOProvider[];
  } catch {
    return [];
  }
}

export function initiateSSOLogin(provider: string): void {
  window.location.href = `/api/v1/auth/oidc/${provider}/login`;
}

export async function getSSOConfigs(): Promise<SSOConfigRead[]> {
  const { data } = await client.get('/auth/oidc/configs');
  return data as SSOConfigRead[];
}

export async function createSSOConfig(payload: SSOConfigCreate): Promise<SSOConfigRead> {
  const { data } = await client.post('/auth/oidc/configs', payload);
  return data as SSOConfigRead;
}

export async function updateSSOConfig(id: string, payload: Partial<SSOConfigCreate>): Promise<SSOConfigRead> {
  const { data } = await client.put(`/auth/oidc/configs/${id}`, payload);
  return data as SSOConfigRead;
}

export async function deleteSSOConfig(id: string): Promise<void> {
  await client.delete(`/auth/oidc/configs/${id}`);
}
