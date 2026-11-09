import axios from 'axios';

export const ACCESS_TOKEN_KEY = 'fp_access_token';
export const REFRESH_TOKEN_KEY = 'fp_refresh_token';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api';

export const api = axios.create({ baseURL });

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeTokens({ access, refresh }) {
  if (access) localStorage.setItem(ACCESS_TOKEN_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshPromise = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {};
    const status = error.response?.status;
    const refresh = getRefreshToken();
    const isAuthCall =
      original.url?.includes('/auth/login/') ||
      original.url?.includes('/auth/refresh/');

    if (status === 401 && refresh && !original._retry && !isAuthCall) {
      original._retry = true;
      try {
        if (!refreshPromise) {
          refreshPromise = axios.post(`${baseURL}/auth/refresh/`, { refresh });
        }
        const { data } = await refreshPromise;
        refreshPromise = null;
        storeTokens(data);
        window.dispatchEvent(
          new CustomEvent('auth:tokens', { detail: { access: data.access } }),
        );
        original.headers = original.headers || {};
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch (refreshError) {
        refreshPromise = null;
        clearTokens();
        window.dispatchEvent(new Event('auth:logout'));
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  },
);

export function getErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  if (!error) return fallback;
  const data = error.response?.data;
  if (data?.detail) return data.detail;
  if (typeof data === 'string') return data;
  if (data?.errors && typeof data.errors === 'object') {
    const messages = [];
    const walk = (value) => {
      if (Array.isArray(value)) value.forEach(walk);
      else if (value && typeof value === 'object') Object.values(value).forEach(walk);
      else if (value) messages.push(String(value));
    };
    walk(data.errors);
    if (messages.length) return messages.join(' ');
  }
  return error.message || fallback;
}

export function getFieldErrors(error) {
  const errors = error?.response?.data?.errors;
  return errors && typeof errors === 'object' && !Array.isArray(errors) ? errors : {};
}

export const authApi = {
  login: (payload) => api.post('/auth/login/', payload),
  me: () => api.get('/auth/me/'),
};

export const membersApi = {
  list: (params) => api.get('/members/', { params }),
  get: (id) => api.get(`/members/${id}/`),
  create: (formData) => api.post('/members/', formData),
  update: (id, formData) => api.patch(`/members/${id}/`, formData),
  remove: (id) => api.delete(`/members/${id}/`),
  enroll: (id, payload = {}) => api.post(`/members/${id}/enroll/`, payload),
};

export const logsApi = {
  list: (params) => api.get('/logs/', { params }),
};

export const devicesApi = {
  list: (params) => api.get('/devices/', { params }),
};

export const dashboardApi = {
  stats: () => api.get('/dashboard/stats/'),
};
