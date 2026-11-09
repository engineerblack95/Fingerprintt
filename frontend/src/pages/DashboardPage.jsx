import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  CalendarDays,
  RefreshCw,
  ShieldAlert,
  UserCheck,
  Users,
  Wifi,
} from 'lucide-react';

import { dashboardApi, getErrorMessage, logsApi } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useDashboardSocket } from '../hooks/useDashboardSocket';
import { formatDateTime } from '../utils/format';
import { CHART_COLORS } from '../utils/constants';
import { PageHeader } from '../components/PageHeader';
import { StatCard } from '../components/StatCard';
import { TrafficChart } from '../components/TrafficChart';
import { StatusDonut } from '../components/StatusDonut';
import { HourlyChart } from '../components/HourlyChart';
import { LiveFeed } from '../components/LiveFeed';
import { ErrorBanner } from '../components/ErrorBanner';
import { Skeleton } from '../components/Loader';

const EMPTY_STATS = {
  today: { total: 0, members: 0, visitors: 0, unknowns: 0 },
  totals: { members: 0, visitors: 0, registered: 0 },
  devices: { total: 0, online: 0 },
  status_distribution: [],
  trend: [],
  hourly: [],
};

function logToEvent(log) {
  return {
    id: `log-${log.id}`,
    status: log.status,
    member: log.member
      ? {
          full_name: log.member.full_name,
          phone_number: log.member.phone_number,
          email: log.member.email,
          photo_url: log.member.photo_url,
        }
      : null,
    device: log.device ? { location_name: log.device.location_name } : null,
    timestamp: log.timestamp,
    isNew: false,
  };
}

export function DashboardPage() {
  const { user, accessToken } = useAuth();
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [liveCount, setLiveCount] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const statsTimerRef = useRef(null);
  const liveEventIdRef = useRef(0);
  const statsRequestRef = useRef(0);
  const loadRequestRef = useRef(0);

  const refreshStats = useCallback(async () => {
    const requestId = statsRequestRef.current + 1;
    statsRequestRef.current = requestId;
    try {
      const { data } = await dashboardApi.stats();
      if (requestId !== statsRequestRef.current) return;
      setStats(data);
      setLastUpdated(new Date());
      setError('');
    } catch (statsError) {
      if (requestId !== statsRequestRef.current) return;
      setError(getErrorMessage(statsError, 'Could not refresh dashboard statistics.'));
    }
  }, []);

  const loadDashboard = useCallback(async ({ silent = false } = {}) => {
    const requestId = loadRequestRef.current + 1;
    loadRequestRef.current = requestId;
    // A full refresh supersedes any stats-only request already in flight.
    statsRequestRef.current += 1;
    if (!silent) setLoading(true);
    setRefreshing(true);
    try {
      const [statsResponse, logsResponse] = await Promise.all([
        dashboardApi.stats(),
        logsApi.list({ page_size: 12 }),
      ]);
      if (requestId !== loadRequestRef.current) return;
      setStats(statsResponse.data);
      setEvents(logsResponse.data.results.map(logToEvent));
      setLastUpdated(new Date());
      setError('');
    } catch (loadError) {
      if (requestId !== loadRequestRef.current) return;
      setError(getErrorMessage(loadError, 'Could not load the dashboard.'));
    } finally {
      if (requestId === loadRequestRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    loadDashboard();
    return () => window.clearTimeout(statsTimerRef.current);
  }, [loadDashboard]);

  const handleLiveEvent = useCallback((payload) => {
    const event = {
      ...payload,
      id: `live-${Date.now()}-${(liveEventIdRef.current += 1)}`,
      isNew: true,
    };
    setEvents((current) => [event, ...current].slice(0, 30));
    setLiveCount((current) => current + 1);

    window.clearTimeout(statsTimerRef.current);
    statsTimerRef.current = window.setTimeout(() => {
      refreshStats();
    }, 700);
  }, [refreshStats]);

  const { status: socketStatus } = useDashboardSocket({
    token: accessToken,
    onEvent: handleLiveEvent,
    enabled: Boolean(accessToken),
  });

  const data = stats || EMPTY_STATS;
  const today = data.today;
  const onlineDevices = data.devices?.online || 0;
  const totalDevices = data.devices?.total || 0;
  const onlinePercent = totalDevices ? Math.round((onlineDevices / totalDevices) * 100) : 0;
  const displayName = user?.full_name || user?.username || 'Owner';

  const socketLabel = {
    connected: 'Live',
    connecting: 'Connecting',
    reconnecting: 'Reconnecting',
    disconnected: 'Offline',
  }[socketStatus];

  return (
    <div className="page">
      <PageHeader
        eyebrow={new Intl.DateTimeFormat(undefined, {
          weekday: 'long',
          month: 'long',
          day: 'numeric',
          year: 'numeric',
        }).format(new Date())}
        title={`Good to see you, ${displayName.split(' ')[0]}.`}
        subtitle="A live view of everyone moving through your doors."
        actions={
          <div className="head-actions">
            <span className={`live-pill live-${socketStatus === 'connected' ? 'connected' : socketStatus === 'disconnected' ? 'disconnected' : 'connecting'}`}>
              <span className="live-dot" /> {socketLabel}
            </span>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => loadDashboard({ silent: true })}
              disabled={refreshing}
            >
              <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
              Refresh
            </button>
          </div>
        }
      />

      <ErrorBanner message={error} onRetry={() => loadDashboard({ silent: true })} />

      <div className="stats-grid">
        <StatCard
          label="Total today"
          value={today.total}
          icon={Activity}
          tone="indigo"
          hint="All entries since midnight"
          loading={loading && !stats}
        />
        <StatCard
          label="Members today"
          value={today.members}
          icon={UserCheck}
          tone="green"
          hint="Authorized family & staff"
          loading={loading && !stats}
        />
        <StatCard
          label="Visitors today"
          value={today.visitors}
          icon={Users}
          tone="blue"
          hint="Pre-enrolled special visitors"
          loading={loading && !stats}
        />
        <StatCard
          label="Unknowns today"
          value={today.unknowns}
          icon={ShieldAlert}
          tone="red"
          hint={today.unknowns ? 'Requires your attention' : 'No intruders detected'}
          loading={loading && !stats}
        />
      </div>

      <div className="dashboard-grid">
        <section className="card chart-card">
          <header className="card-head">
            <div>
              <div className="card-title-row">
                <span className="card-icon card-icon-indigo">
                  <CalendarDays size={17} />
                </span>
                <h2 className="card-title">Entry traffic</h2>
              </div>
              <p className="card-subtitle">Seven-day movement by identity type.</p>
            </div>
            <div className="chart-legend">
              <span><i style={{ background: CHART_COLORS.members }} /> Members</span>
              <span><i style={{ background: CHART_COLORS.visitors }} /> Visitors</span>
              <span><i style={{ background: CHART_COLORS.unknowns }} /> Unknowns</span>
            </div>
          </header>
          <div className="card-body">
            {loading && !stats ? (
              <Skeleton className="chart-skeleton" />
            ) : (
              <TrafficChart data={data.trend} />
            )}
          </div>
        </section>

        <section className="card">
          <header className="card-head">
            <div>
              <div className="card-title-row">
                <span className="card-icon card-icon-green">
                  <Activity size={17} />
                </span>
                <h2 className="card-title">Today's mix</h2>
              </div>
              <p className="card-subtitle">How today's entries break down.</p>
            </div>
          </header>
          <div className="card-body">
            {loading && !stats ? (
              <Skeleton className="donut-skeleton" />
            ) : (
              <StatusDonut data={data.status_distribution} total={today.total} />
            )}
          </div>
        </section>
      </div>

      <div className="dashboard-grid dashboard-grid-feed">
        <LiveFeed events={events} connectionStatus={socketStatus} liveCount={liveCount} />

        <div className="stack">
          <section className="card">
            <header className="card-head">
              <div>
                <div className="card-title-row">
                  <span className="card-icon card-icon-blue">
                    <Activity size={17} />
                  </span>
                  <h2 className="card-title">Hourly activity</h2>
                </div>
                <p className="card-subtitle">Entries by hour today.</p>
              </div>
            </header>
            <div className="card-body">
              {loading && !stats ? (
                <Skeleton className="chart-skeleton-sm" />
              ) : (
                <HourlyChart data={data.hourly} />
              )}
            </div>
          </section>

          <section className="card device-summary">
            <div className="device-summary-top">
              <div>
                <span className="eyebrow">System health</span>
                <h2>{onlineDevices} of {totalDevices} devices online</h2>
              </div>
              <span className="device-summary-icon">
                <Wifi size={20} />
              </span>
            </div>
            <div className="progress-track">
              <span className="progress-fill" style={{ width: `${onlinePercent}%` }} />
            </div>
            <div className="device-summary-stats">
              <div>
                <strong>{data.totals.registered}</strong>
                <span>Registered people</span>
              </div>
              <div>
                <strong>{data.totals.members}</strong>
                <span>Members</span>
              </div>
              <div>
                <strong>{data.totals.visitors}</strong>
                <span>Visitors</span>
              </div>
            </div>
            <Link to="/devices" className="text-link">
              View devices <ArrowRight size={14} />
            </Link>
          </section>
        </div>
      </div>

      <footer className="page-foot">
        <span>Last updated {lastUpdated ? formatDateTime(lastUpdated) : '—'}</span>
        <span>Edge matching · encrypted templates · no fingerprint images stored</span>
      </footer>
    </div>
  );
}
