import { Loader2 } from 'lucide-react';

export function Spinner({ size = 18, className = '' }) {
  return <Loader2 size={size} className={`spin ${className}`} aria-hidden="true" />;
}

export function FullScreenLoader({ label = 'Loading…' }) {
  return (
    <div className="fullscreen-loader">
      <div className="loader-mark">
        <Loader2 size={28} className="spin" />
      </div>
      <p>{label}</p>
    </div>
  );
}

export function Skeleton({ className = '', style }) {
  return <div className={`skeleton ${className}`} style={style} aria-hidden="true" />;
}
