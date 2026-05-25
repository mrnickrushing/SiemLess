import axios from 'axios';

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
  withCredentials: true, // send the httpOnly session cookie on every request
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
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
