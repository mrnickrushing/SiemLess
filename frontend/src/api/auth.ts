import client, { setToken, clearToken } from './client';

export async function login(username: string, password: string): Promise<string> {
  const { data } = await client.post('/auth/login', { username, password });
  setToken(data.access_token);
  return data.username;
}

export async function logout() {
  clearToken();
  window.location.href = '/login';
}
