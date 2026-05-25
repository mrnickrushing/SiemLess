import client from './client';

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
