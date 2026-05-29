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

/**
 * Authenticate with the backend using a username and password.
 *
 * @param username - The user's login name
 * @param password - The user's password
 * @returns The authenticated user's username
 */
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

/**
 * Fetches the current authenticated user's username.
 *
 * Returns the username from the server, or `null` when the username is unavailable (for example, when not authenticated or the request fails).
 *
 * @returns The current user's `username`, or `null` if unavailable
 */
export async function getMe(): Promise<string | null> {
  try {
    const { data } = await client.get('/auth/me');
    return data.username as string;
  } catch {
    return null;
  }
}

/**
 * Fetches available SSO/OIDC providers.
 *
 * @returns An array of `SSOProvider` objects representing available providers; returns an empty array if the request fails.
 */
export async function getSSOProviders(): Promise<SSOProvider[]> {
  try {
    const { data } = await client.get('/auth/oidc/providers');
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

/**
 * Redirects the browser to the OIDC login endpoint for the given provider.
 *
 * @param provider - The SSO provider identifier inserted into the login URL path
 */
export function initiateSSOLogin(provider: string): void {
  window.location.href = `/api/v1/auth/oidc/${provider}/login`;
}

/**
 * Fetches persisted SSO (OIDC) configurations from the server.
 *
 * @returns The list of SSO configuration objects returned by the API.
 */
export async function getSSOConfigs(): Promise<SSOConfigRead[]> {
  const { data } = await client.get('/auth/oidc/configs');
  return data as SSOConfigRead[];
}

/**
 * Create a new SSO (OIDC) configuration on the server.
 *
 * @param payload - Configuration to persist; includes required OIDC fields (`provider_name`, `client_id`, `client_secret`, `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint`) and optional fields such as `jwks_uri`, `scopes`, and `enabled`
 * @returns The persisted SSO configuration, including server-generated fields like `id`, `created_at`, and `client_secret_masked`
 */
export async function createSSOConfig(payload: SSOConfigCreate): Promise<SSOConfigRead> {
  const { data } = await client.post('/auth/oidc/configs', payload);
  return data as SSOConfigRead;
}

/**
 * Update an existing SSO configuration by ID.
 *
 * @param id - The identifier of the SSO configuration to update
 * @param payload - Partial fields to apply to the configuration
 * @returns The updated SSO configuration as `SSOConfigRead`
 */
export async function updateSSOConfig(id: string, payload: Partial<SSOConfigCreate>): Promise<SSOConfigRead> {
  const { data } = await client.put(`/auth/oidc/configs/${id}`, payload);
  return data as SSOConfigRead;
}

/**
 * Delete an existing SSO configuration by its identifier.
 *
 * @param id - The identifier of the SSO configuration to remove
 */
export async function deleteSSOConfig(id: string): Promise<void> {
  await client.delete(`/auth/oidc/configs/${id}`);
}
