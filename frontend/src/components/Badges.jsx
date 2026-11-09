import { STATUS_META } from '../utils/constants';

export function StatusBadge({ status, withDot = true }) {
  const meta = STATUS_META[status] || STATUS_META.UNKNOWN;
  return (
    <span className={`badge badge-${String(status).toLowerCase()}`}>
      {withDot ? <span className="badge-dot" /> : null}
      {meta.label}
    </span>
  );
}

export function RoleBadge({ role }) {
  const isVisitor = role === 'VISITOR';
  return (
    <span className={`badge ${isVisitor ? 'badge-visitor' : 'badge-member'}`}>
      <span className="badge-dot" />
      {isVisitor ? 'Visitor' : 'Member'}
    </span>
  );
}
