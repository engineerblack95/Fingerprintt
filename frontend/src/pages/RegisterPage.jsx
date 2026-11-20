import { useMemo, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserPlus,
  UserRound,
} from 'lucide-react';

import { AuthShell } from '../components/AuthShell';
import { ErrorBanner } from '../components/ErrorBanner';
import { Spinner } from '../components/Loader';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { getErrorMessage } from '../api/client';

const USERNAME_RE = /^[\w.@+-]+$/;

export function RegisterPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user, register } = useAuth();

  const [form, setForm] = useState({
    fullName: '',
    username: '',
    email: '',
    password: '',
    password_confirm: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const checks = useMemo(
    () => [
      { id: 'length', label: 'At least 8 characters', met: form.password.length >= 8 },
      {
        id: 'not-numeric',
        label: 'Not entirely numbers',
        met: form.password.length > 0 && !/^\d+$/.test(form.password),
      },
      {
        id: 'match',
        label: 'Both passwords match',
        met: form.password.length > 0 && form.password === form.password_confirm,
      },
    ],
    [form.password, form.password_confirm],
  );

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    const username = form.username.trim();
    const email = form.email.trim();

    if (!username || !email || !form.password || !form.password_confirm) {
      setError('Fill in your username, email and both password fields.');
      return;
    }
    if (username.length < 3 || !USERNAME_RE.test(username)) {
      setError(
        'Usernames need at least 3 characters: letters, numbers or @ . + - _',
      );
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Enter a valid email address, for example you@example.com.');
      return;
    }
    if (form.password.length < 8) {
      setError('Your password must be at least 8 characters long.');
      return;
    }
    if (form.password !== form.password_confirm) {
      setError('The two passwords do not match.');
      return;
    }

    const parts = form.fullName.trim().split(/\s+/).filter(Boolean);
    const first_name = parts.shift() || '';
    const last_name = parts.join(' ');

    setLoading(true);
    try {
      const created = await register({
        username,
        email,
        first_name,
        last_name,
        password: form.password,
        password_confirm: form.password_confirm,
      });
      toast.success(`Welcome, ${created.full_name || created.username}. Your dashboard is ready.`);
      navigate('/dashboard', { replace: true });
    } catch (registerError) {
      setError(
        getErrorMessage(
          registerError,
          'We could not create your account. Please try again.',
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Create account"
      title="Start monitoring your doors"
      subtitle="Create a free dashboard account to follow entries, visitors and unknown detections in real time."
      footer={<><ShieldCheck size={13} /> Standard accounts are read-only · administrator keeps full control</>}
    >
      <ErrorBanner message={error} />

      <form className="login-form" onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span className="field-label">Full name <em className="field-optional">optional</em></span>
          <div className="input-wrap">
            <UserRound size={16} />
            <input
              className="input"
              name="fullName"
              type="text"
              autoComplete="name"
              placeholder="Ada Lovelace"
              value={form.fullName}
              onChange={handleChange}
              autoFocus
            />
          </div>
        </label>

        <div className="field-row">
          <label className="field">
            <span className="field-label">Username</span>
            <div className="input-wrap">
              <UserRound size={16} />
              <input
                className="input"
                name="username"
                type="text"
                autoComplete="username"
                placeholder="ada"
                value={form.username}
                onChange={handleChange}
              />
            </div>
          </label>

          <label className="field">
            <span className="field-label">Email</span>
            <div className="input-wrap">
              <Mail size={16} />
              <input
                className="input"
                name="email"
                type="email"
                autoComplete="email"
                inputMode="email"
                placeholder="ada@example.com"
                value={form.email}
                onChange={handleChange}
              />
            </div>
          </label>
        </div>

        <label className="field">
          <span className="field-label">Password</span>
          <div className="input-wrap">
            <LockKeyhole size={16} />
            <input
              className="input"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="At least 8 characters"
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

        <label className="field">
          <span className="field-label">Confirm password</span>
          <div className="input-wrap">
            <LockKeyhole size={16} />
            <input
              className="input"
              name="password_confirm"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="Repeat your password"
              value={form.password_confirm}
              onChange={handleChange}
            />
          </div>
        </label>

        <ul className="password-hints">
          {checks.map((check) => (
            <li
              key={check.id}
              className={check.met ? 'password-hint is-met' : 'password-hint'}
            >
              <span className="password-hint-dot">
                {check.met ? <Check size={11} /> : null}
              </span>
              {check.label}
            </li>
          ))}
        </ul>

        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
          {loading ? <Spinner size={17} /> : <UserPlus size={16} />}
          {loading ? 'Creating your account…' : 'Create account'}
        </button>
      </form>

      <div className="auth-switch">
        <span>Already have an account?</span>
        <Link className="login-link" to="/login">
          Sign in
        </Link>
      </div>

      <div className="auth-actions">
        <Link className="login-link auth-back" to="/login">
          <ArrowLeft size={15} /> Back to sign in
        </Link>
      </div>
    </AuthShell>
  );
}
