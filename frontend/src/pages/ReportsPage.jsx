import { useEffect, useState } from 'react';
import {
  CalendarRange,
  Download,
  FileSpreadsheet,
  FileText,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react';

import { devicesApi, getErrorMessage, logsApi } from '../api/client';
import { useToast } from '../context/ToastContext';
import { STATUS_META } from '../utils/constants';
import { PageHeader } from '../components/PageHeader';
import { ErrorBanner } from '../components/ErrorBanner';

const EMPTY_FILTERS = { status: '', dateFrom: '', dateTo: '', device: '' };

const STATUS_OPTIONS = [
  { value: '', label: 'All activity' },
  { value: 'MEMBER', label: 'Members' },
  { value: 'VISITOR', label: 'Visitors' },
  { value: 'UNKNOWN', label: 'Unknowns' },
  { value: 'ENROLLED', label: 'Enrollments' },
];

function filenameFromResponse(response, fallback) {
  const disposition = response.headers?.['content-disposition'] || '';
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return match ? match[1] : fallback;
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function describeExportError(error) {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      return (
        parsed?.detail ||
        parsed?.filetype?.[0] ||
        parsed?.errors?.filetype?.[0] ||
        'Could not generate the report.'
      );
    } catch {
      return 'Could not generate the report.';
    }
  }
  return getErrorMessage(error, 'Could not generate the report.');
}

export function ReportsPage() {
  const toast = useToast();
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [devices, setDevices] = useState([]);
  const [exporting, setExporting] = useState('');
  const [error, setError] = useState('');

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

  const updateFilter = (name, value) => {
    setFilters((current) => ({ ...current, [name]: value }));
  };

  const resetFilters = () => setFilters(EMPTY_FILTERS);

  const hasFilters =
    filters.status || filters.dateFrom || filters.dateTo || filters.device;

  const handleExport = async (filetype) => {
    setExporting(filetype);
    setError('');
    try {
      const params = { filetype };
      if (filters.status) params.status = filters.status;
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;
      if (filters.device) params.device = filters.device;

      const response = await logsApi.export(params);
      const fallback = `activity-report.${filetype}`;
      saveBlob(response.data, filenameFromResponse(response, fallback));
      toast.success(`${filetype.toUpperCase()} report downloaded.`);
    } catch (exportError) {
      const message = await describeExportError(exportError);
      setError(message);
      toast.error(message);
    } finally {
      setExporting('');
    }
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow="Reports"
        title="Activity reports"
        subtitle="Download the system activity history as a spreadsheet or a printable PDF."
        actions={
          <button
            type="button"
            className="btn btn-ghost"
            onClick={resetFilters}
            disabled={!hasFilters}
          >
            <RotateCcw size={15} /> Reset filters
          </button>
        }
      />

      <ErrorBanner message={error} />

      <section className="card filter-card">
        <div className="filter-row">
          <div className="card-title-row">
            <span className="card-icon card-icon-indigo">
              <CalendarRange size={17} />
            </span>
            <h2 className="card-title">Report range</h2>
          </div>
          <div className="filter-count">
            {hasFilters ? 'Filtered report' : 'All recorded activity'}
          </div>
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
            <span className="field-label">Activity type</span>
            <select
              className="select"
              value={filters.status}
              onChange={(event) => updateFilter('status', event.target.value)}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value || 'all'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
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
        </div>
      </section>

      <div className="report-grid">
        <section className="card report-card">
          <span className="report-icon report-icon-csv">
            <FileSpreadsheet size={24} />
          </span>
          <h2>CSV spreadsheet</h2>
          <p>
            A complete, Excel-friendly export of every matching event, including
            person, status, device, timestamp and source.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleExport('csv')}
            disabled={Boolean(exporting)}
          >
            <Download size={15} className={exporting === 'csv' ? 'spin' : ''} />
            {exporting === 'csv' ? 'Preparing…' : 'Download CSV'}
          </button>
        </section>

        <section className="card report-card">
          <span className="report-icon report-icon-pdf">
            <FileText size={24} />
          </span>
          <h2>PDF report</h2>
          <p>
            A printable, paginated summary of the matching activity. Large
            histories are capped at 3,000 rows — use CSV for the full set.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleExport('pdf')}
            disabled={Boolean(exporting)}
          >
            <Download size={15} className={exporting === 'pdf' ? 'spin' : ''} />
            {exporting === 'pdf' ? 'Preparing…' : 'Download PDF'}
          </button>
        </section>
      </div>

      <section className="card report-note">
        <span className="report-note-icon">
          <ShieldCheck size={18} />
        </span>
        <div>
          <strong>Reports respect the selected filters</strong>
          <p>
            Timestamps use the server timezone. Hardware enrollment events are
            included as system activity and are never treated as access grants.
          </p>
        </div>
      </section>

      <div className="report-status-legend">
        {Object.entries(STATUS_META).map(([key, meta]) => (
          <span key={key}>
            <i style={{ background: meta.color }} />
            {meta.label}
          </span>
        ))}
      </div>
    </div>
  );
}
