import { Skeleton } from './Loader';

export function StatCard({ label, value, icon: Icon, tone = 'indigo', hint, loading }) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <div className="stat-glow" />
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        <span className="stat-icon">
          <Icon size={19} />
        </span>
      </div>
      {loading ? (
        <Skeleton className="stat-skeleton" />
      ) : (
        <div className="stat-value">{value ?? 0}</div>
      )}
      <div className="stat-hint">{hint}</div>
    </div>
  );
}
