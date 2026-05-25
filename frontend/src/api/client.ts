import axios from 'axios';

const TOKEN_KEY = 'siemless_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      (error.request ? 'Network error — unable to reach the server' : error.message) ||
      'An unknown error occurred';
    return Promise.reject(new Error(message));
  }
);

export default client;
