import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

/**
 * Global Axios API Client instance configured for backend communications.
 * Proxied via Vite to http://localhost:8001/api/v1 during development.
 */
export const apiClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach Authorization header from localStorage if available
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    if (token && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401 Unauthorized globally
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      // Avoid triggering logout event for login attempts or initial auth checks
      if (!url.includes('/auth/login') && !url.includes('/auth/me')) {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('auth:logout'));
        }
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
