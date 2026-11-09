import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Clock,
  MapPin,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  UserRound,
} from 'lucide-react';

import { devicesApi, getErrorMessage, logsApi } from '../api/client';
import { PAGE_SIZE, STATUS_META } from '../utils/constants';
import { formatDateTime, initials, resolveMediaUrl, timeAgo } from '../utils/format';
import { PageHeader } from '../components/PageHeader';
import { ErrorBanner } from '../components/ErrorBanner';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/Loader';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/Badges';

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'MEMBER', label: 'Members' },
  { value: 'VISITOR', label: 'Visitors' },
  { value: 'UNKNOWN', label: 'Unknowns' },
];

const EMPTY_FILTERS = { status: '', dateFrom: '', dateTo: '', device: '' };

export function LogsPage() {
  const [logs, setLogs] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const requestIdRef = useRef(0);

  useEffect(() => {
    let active = true;
    devicesApi
      .list({ page_size: 100 })
      .then(({ data }) => {
        if (active) setDevices(data.results || data);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const loadLogs = useCallback(async () => {
    // Filters can change faster than the network replies. Only the newest
    // request is allowed to write state, so stale responses cannot win.
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (filters.status) params.status = filters.status;
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;
      if (filters.device) params.device = filters.device;
      if (search) params.search = search;
      const { data } = await logsApi.list(params);
      if (requestId !== requestIdRef.current) return;
      setLogs(data.results);
      setCount(data.count);
    } catch (loadError) {
      if (requestId !== requestIdRef.current) return;
      setError(getErrorMessage(loadError, 'Could not load entry history.'));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [page, filters, search]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs, refreshKey]);

  const updateFilter = (name, value) => {
    setFilters((current) => ({ ...current, [name]: value }));
    setPage(1);
  };

  const resetFilters = () => {
    setFilters(EMPTY_FILTERS);
    setSearchInput('');
    setSearch('');
    setPage(1);
  };

  const hasFilters =
    filters.status || filters.dateFrom || filters.dateTo || filters.device || search;

  return (
    <div className="page">
      <PageHeader
        eyebrow="History"
        title="Entry logs"
        subtitle="Every reported entry, with status, device and timestamp."
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

      <ErrorBanner message={error} onRetry={loadLogs} />

      <section className="card filter-card">
        <div className="filter-row">
          <div className="segmented" role="tablist" aria-label="Filter by status">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value || 'all'}
                type="button"
                className={filters.status === tab.value ? 'active' : ''}
                onClick={() => updateFilter('status', tab.value)}
              >
                {tab.value ? (
                  <span
                    className="seg-dot"
                    style={{ background: STATUS_META[tab.value].color }}
                  />
                ) : null}
                {tab.label}
              </button>
            ))}
          </div>
          <div className="filter-count">{count} entries</div>
        </div>

        <div className="filter-grid">
          <label className="field field-compact">
            <span className="field-label">From</span>
            <input
              type="date"
              className="input"
              value={filters.dateFrom}
              max={filters.dateTo || undefined}
              onChange={(event) => updateFilter('dateFrom', event.target.value)}
            />
          </label>
          <label className="field field-compact">
            <span className="field-label">To</span>
            <input
              type="date"
              className="input"
              value={filters.dateTo}
              min={filters.dateFrom || undefined}
              onChange={(event) => updateFilter('dateTo', event.target.value)}
            />
          </label>
          <label className="field field-compact">
            <span className="field-label">Device</span>
            <select
              className="select"
              value={filters.device}
              onChange={(event) => updateFilter('device', event.target.value)}
            >
              <option value="">All devices</option>
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.location_name} · {device.device_id}
                </option>
              ))}
            </select>
          </label>
          <div className="field field-compact">
            <span className="field-label">Search</span>
            <div className="search-wrap">
              <Search size={15} />
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Name, username or location…"
                aria-label="Search logs"
              />
            </div>
          </div>
          <div className="filter-reset">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={resetFilters}
              disabled={!hasFilters}
            >
              <RotateCcw size={14} /> Reset
            </button>
          </div>
        </div>
      </section>

      <section className="card table-card">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Status</th>
                <th>Device</th>
                <th>Timestamp</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }).map((_, index) => (
                  <tr key={index}>
                    <td colSpan={5}>
                      <Skeleton className="table-skeleton" />
                    </td>
                  </tr>
                ))
              ) : logs.length ? (
                logs.map((log) => {
                  const photoUrl = resolveMediaUrl(log.member?.photo_url);
                  return (
                    <tr key={log.id}>
                      <td>
                        <div className="table-person">
                          <div className="table-avatar">
                            {log.member ? (
                              photoUrl ? (
                                <img src={photoUrl} alt={log.member.full_name} loading="lazy" />
                              ) : (
                                <span className="avatar avatar-photo">
                                  {initials(log.member.full_name)}
                                </span>
                              )
                            ) : (
                              <span className="table-avatar-unknown">
                                <ShieldAlert size={16} />
                              </span>
                            )}
                          </div>
                          <div>
                            <strong>
                              {log.member ? log.member.full_name : 'Unknown person'}
                            </strong>
                            <span>
                              {log.member
                                ? `@${log.member.username} · ${log.member.email}`
                                : 'No registered profile found'}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={log.status} />
                      </td>
                      <td>
                        <div className="table-device">
                          <span>
                            <MapPin size={13} /> {log.device?.location_name || '—'}
                          </span>
                          <small>{log.device?.device_id || ''}</small>
                        </div>
                      </td>
                      <td>
                        <div className="table-time">
                          <span>
                            <Clock size={13} /> {formatDateTime(log.timestamp)}
                          </span>
                          <small>{timeAgo(log.timestamp)}</small>
                        </div>
                      </td>
                      <td>
                        <span
                          className={`source-pill ${
                            log.synced_from_device ? 'source-sync' : 'source-live'
                          }`}
                        >
                          {log.synced_from_device ? 'Buffered sync' : 'Live report'}
                        </span>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5}>
                    <EmptyState
                      icon={hasFilters ? Search : UserRound}
                      title={hasFilters ? 'No entries match these filters' : 'No entries yet'}
                      message={
                        hasFilters
                          ? 'Try a wider date range or clear the filters.'
                          : 'Entries will appear here as soon as a device reports a result.'
                      }
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <Pagination
        page={page}
        count={count}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        loading={loading}
      />
    </div>
  );
}
