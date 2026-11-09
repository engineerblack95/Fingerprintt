import { Link } from 'react-router-dom';
import { ArrowLeft, Fingerprint } from 'lucide-react';

export function NotFoundPage() {
  return (
    <div className="not-found">
      <div className="not-found-mark">
        <Fingerprint size={34} />
      </div>
      <span className="eyebrow">404</span>
      <h1>This page is not on the map.</h1>
      <p>The address you followed does not exist in the access control dashboard.</p>
      <Link to="/dashboard" className="btn btn-primary">
        <ArrowLeft size={16} /> Back to dashboard
      </Link>
    </div>
  );
}
