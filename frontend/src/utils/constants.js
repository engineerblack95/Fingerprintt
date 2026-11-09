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
};

export const ROLE_META = {
  MEMBER: { label: 'Member', className: 'badge-member' },
  VISITOR: { label: 'Visitor', className: 'badge-visitor' },
};

export const CHART_COLORS = {
  members: '#16a34a',
  visitors: '#2563eb',
  unknowns: '#dc2626',
  primary: '#4f46e5',
};

export const PAGE_SIZE = 12;
