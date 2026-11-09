export const STATUS_META = {
  MEMBER: {
    label: 'Member',
    emoji: '🟢',
    color: '#16a34a',
    dark: '#15803d',
    soft: '#dcfce7',
    border: '#86efac',
    description: 'Authorized family / staff',
  },
  VISITOR: {
    label: 'Visitor',
    emoji: '🔵',
    color: '#2563eb',
    dark: '#1d4ed8',
    soft: '#dbeafe',
    border: '#93c5fd',
    description: 'Pre-enrolled visitor',
  },
  UNKNOWN: {
    label: 'Unknown',
    emoji: '🔴',
    color: '#dc2626',
    dark: '#b91c1c',
    soft: '#fee2e2',
    border: '#fca5a5',
    description: 'No match · intruder alert',
  },
  ENROLLED: {
    label: 'Enrolled',
    emoji: '🔧',
    color: '#d97706',
    dark: '#b45309',
    soft: '#fef3c7',
    border: '#fcd34d',
    description: 'Fingerprint enrolled on hardware',
  },
};

export const ROLE_META = {
  MEMBER: { label: 'Member', className: 'badge-member' },
  VISITOR: { label: 'Visitor', className: 'badge-visitor' },
};

export const CHART_COLORS = {
  members: '#16a34a',
  visitors: '#2563eb',
  unknowns: '#dc2626',
  enrollments: '#d97706',
  primary: '#4f46e5',
};

export const PAGE_SIZE = 12;

const RENDER_BACKEND_FALLBACK = 'https://fingerprint-backend-7032.onrender.com';

/**
 * Base URL of the Django backend. In production the committed .env may still
 * point at localhost, so fall back to the deployed Render service when the
 * configured URL is a local one.
 */
export function getBackendBaseUrl() {
  const configured = String(import.meta.env.VITE_BACKEND_URL || '')
    .trim()
    .replace(/\/+$/, '');
  const isLocal = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(configured);

  if (configured && !(import.meta.env.PROD && isLocal)) return configured;
  return import.meta.env.PROD ? RENDER_BACKEND_FALLBACK : 'http://localhost:8000';
}

export function getAdminUrl() {
  return `${getBackendBaseUrl()}/admin/`;
}
