import { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw, Router, ShieldCheck, Wifi, WifiOff } from 'lucide-react';

import { devicesApi, getErrorMessage } from '../api/client';
import { formatDateTime, timeAgo } from '../utils/format';
import { PageHeader } from '../components/PageHeader';
import { StatCard } from '../components/StatCard';
import { ErrorBanner } from '../components/ErrorBanner';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/Loader';

function DeviceCard({ device }) {
  const online = device.is_online;
  return (
    <article className={`device-card ${online ? 'device-online' : 'device-offline'}`}>
      <div className="device-card-top">
        <span className={`device-icon ${online ? 'online' : 'offline'}`}>
          <Router size={22} />
        </span>
        <span className={`device-state ${online ? 'state-online' : 'state-offline'}`}>
          <span className="live-dot" /> {online ? 'Online' : 'Offline'}
        </span>
      </div>
      <h3>{device.location_name}</h3>
      <span className="device-id">{device.device_id}</span>

      <div className="device-meta">
        <div>
          <span className="device-meta-label">Last seen</span>
          <strong>{device.last_seen_at ? timeAgo(device.last_seen_at) : 'Never'}</strong>
        </div>
        <div>
          <span className="device-meta-label">Exact time</span>
          <strong>{device.last_seen_at ? formatDateTime(device.last_seen_at) : '—'}</strong>
        </div>
      </div>

      <div className="device-card-foot">
        {online ? <Wifi size={14} /> : <WifiOff size={14} />}
        {online ? 'Heartbeat received' : 'Waiting for heartbeat'}
      </div>
    </article>
  );
}

export function DevicesPage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const requestIdRef = useRef(0);

  const loadDevices = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setError('');
    try {
      const { data } = await devicesApi.list({ page_size: 100 });
      if (requestId !== requestIdRef.current) return;
      setDevices(data.results || data);
    } catch (loadError) {
      if (requestId !== requestIdRef.current) return;
      setError(getErrorMessage(loadError, 'Could not load devices.'));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDevices();
  }, [loadDevices, refreshKey]);

  const online = devices.filter((device) => device.is_online).length;
  const offline = devices.length - online;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Hardware"
        title="Devices"
        subtitle="Fingerprint terminals reporting heartbeats to this server."
        actions={
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setRefreshKey((current) => current + 1)}
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh
          </button>
        }
      />

      <ErrorBanner message={error} onRetry={loadDevices} />

      <div className="stats-grid stats-grid-3">
        <StatCard
          label="Installed devices"
          value={devices.length}
          icon={Router}
          tone="indigo"
          hint="Registered terminals"
          loading={loading}
        />
        <StatCard
          label="Online now"
          value={online}
          icon={Wifi}
          tone="green"
          hint="Recent heartbeat received"
          loading={loading}
        />
        <StatCard
          label="Offline"
          value={offline}
          icon={WifiOff}
          tone="red"
          hint="No recent heartbeat"
          loading={loading}
        />
      </div>

      {loading ? (
        <div className="devices-grid">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="device-skeleton" />
          ))}
        </div>
      ) : devices.length ? (
        <div className="devices-grid">
          {devices.map((device) => (
            <DeviceCard key={device.id} device={device} />
          ))}
        </div>
      ) : (
        <div className="card">
          <EmptyState
            icon={ShieldCheck}
            title="No devices registered"
            message="Register a fingerprint terminal with `python manage.py create_device` to start receiving events."
          />
        </div>
      )}

      <div className="info-strip">
        <ShieldCheck size={16} />
        <span>
          Devices authenticate with an API key and send only match results. Fingerprint templates
          are fetched over the authenticated sync endpoint and stored encrypted at rest.
        </span>
      </div>
    </div>
  );
}
