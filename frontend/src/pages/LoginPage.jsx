import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import {
  Eye,
  EyeOff,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { getErrorMessage } from '../api/client';
import { ErrorBanner } from '../components/ErrorBanner';
import { Spinner } from '../components/Loader';

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  const [form, setForm] = useState({ username: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (user) {
    return <Navigate to={location.state?.from || '/dashboard'} replace />;
  }

  const handleChange = (event) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (!form.username.trim() || !form.password) {
      setError('Enter your username and password to continue.');
      return;
    }
    setLoading(true);
    try {
      await login(form.username.trim(), form.password);
      toast.success('Welcome back. Your dashboard is ready.');
      navigate(location.state?.from || '/dashboard', { replace: true });
    } catch (loginError) {
      setError(getErrorMessage(loginError, 'Invalid username or password.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-shell">
      <section className="login-brand">
        <div className="login-orbit orbit-one" />
        <div className="login-orbit orbit-two" />
        <div className="login-orbit orbit-three" />
        <div className="login-brand-inner">
          <div className="brand brand-on-dark">
            <div className="brand-mark brand-mark-lg">
              <Fingerprint size={27} />
            </div>
            <div className="brand-text">
              <span className="brand-name">Fingerprint</span>
              <span className="brand-sub">Access Control</span>
            </div>
          </div>

          <div className="login-hero">
            <span className="login-pill">
              <Sparkles size={14} /> Edge-matched · Privacy first
            </span>
            <h1>
              Every entry,
              <br />
              <span>verified.</span>
            </h1>
            <p>
              A calm command center for your fingerprint terminals. See who arrives,
              catch unknown visitors instantly, and keep every fingerprint on the edge.
            </p>

            <ul className="login-features">
              <li>
                <span className="login-feature-icon">
                  <Fingerprint size={18} />
                </span>
                <div>
                  <strong>On-device matching</strong>
                  <span>Raw prints never leave the terminal. Only the result is reported.</span>
                </div>
              </li>
              <li>
                <span className="login-feature-icon">
                  <ShieldCheck size={18} />
                </span>
                <div>
                  <strong>Instant security alerts</strong>
                  <span>Unknown detections turn the dashboard red and email you immediately.</span>
                </div>
              </li>
              <li>
                <span className="login-feature-icon">
                  <KeyRound size={18} />
                </span>
                <div>
                  <strong>Encrypted templates</strong>
                  <span>Templates are encrypted at rest; no fingerprint images are stored.</span>
                </div>
              </li>
            </ul>
          </div>

          <div className="login-brand-foot">
            <span className="live-dot" /> Edge devices · PostgreSQL · Django Channels
          </div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="login-mobile-brand">
            <div className="brand-mark">
              <Fingerprint size={22} />
            </div>
            <span>Fingerprint Access</span>
          </div>

          <div className="login-card-head">
            <span className="eyebrow">Owner access</span>
            <h2>Welcome back</h2>
            <p>Sign in to monitor entries, manage people and watch the live feed.</p>
          </div>

          <ErrorBanner message={error} />

          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span className="field-label">Username</span>
              <div className="input-wrap">
                <UserRound size={16} />
                <input
                  className="input"
                  name="username"
                  type="text"
                  autoComplete="username"
                  placeholder="Engineer"
                  value={form.username}
                  onChange={handleChange}
                  autoFocus
                />
              </div>
            </label>

            <label className="field">
              <span className="field-label">Password</span>
              <div className="input-wrap">
                <LockKeyhole size={16} />
                <input
                  className="input"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={form.password}
                  onChange={handleChange}
                />
                <button
                  type="button"
                  className="input-action"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>

            <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
              {loading ? <Spinner size={17} /> : <LockKeyhole size={16} />}
              {loading ? 'Signing in…' : 'Sign in to dashboard'}
            </button>
          </form>

          <div className="login-card-foot">
            <LockKeyhole size={13} /> JWT-secured session · access tokens rotate automatically
          </div>
        </div>
      </section>
    </div>
  );
}
