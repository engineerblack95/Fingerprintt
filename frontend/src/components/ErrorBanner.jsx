import { AlertCircle, RefreshCw } from 'lucide-react';

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="error-banner" role="alert">
      <span className="error-banner-icon">
        <AlertCircle size={18} />
      </span>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}>
          <RefreshCw size={14} />
          Retry
        </button>
      ) : null}
    </div>
  );
}
