import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Link2Off,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react';

import { AuthShell } from '../components/AuthShell';
import { ErrorBanner } from '../components/ErrorBanner';
import { Spinner } from '../components/Loader';
import { authApi, clearTokens, getErrorMessage } from '../api/client';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const uid = (searchParams.get('uid') || '').trim();
  const token = (searchParams.get('token') || '').trim();

  const [form, setForm] = useState({ password: '', password_confirm: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [linkError, setLinkError] = useState('');
  const [done, setDone] = useState(false);

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

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    if (!form.password || !form.password_confirm) {
      setError('Choose a new password and confirm it to continue.');
      return;
    }
    if (form.password.length < 8) {
      setError('Your new password must be at least 8 characters long.');
      return;
    }
    if (form.password !== form.password_confirm) {
      setError('The two passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await authApi.confirmPasswordReset({
        uid,
        token,
        password: form.password,
        password_confirm: form.password_confirm,
      });
      clearTokens();
      setDone(true);
    } catch (resetError) {
      const status = resetError?.response?.status;
      if (status === 400) {
        setLinkError(
          getErrorMessage(
            resetError,
            'This password reset link is invalid or has expired. Please request a new one.',
          ),
        );
      } else {
        setError(
          getErrorMessage(
            resetError,
            'We could not update your password right now. Please try again.',
          ),
        );
      }
    } finally {
      setLoading(false);
    }
  };

  if (!uid || !token) {
    return (
      <AuthShell
        eyebrow="Account recovery"
        title="Link is incomplete"
        subtitle="This page needs the full reset link from your email."
        footer={<><ShieldCheck size={13} /> Reset links are single-use and time-limited</>}
      >
        <div className="auth-success auth-success-warn">
          <span className="auth-success-icon">
            <Link2Off size={28} />
          </span>
          <h3>That reset link is not valid</h3>
          <p>
            The address is missing its security code. Copy the complete link
            from the email, or request a fresh one below.
          </p>
        </div>
        <div className="auth-actions">
          <Link className="btn btn-primary btn-block" to="/forgot-password">
            <KeyRound size={16} /> Request a new link
          </Link>
          <Link className="btn btn-ghost btn-block" to="/login">
            <ArrowLeft size={16} /> Back to sign in
          </Link>
        </div>
      </AuthShell>
    );
  }

  if (linkError) {
    return (
      <AuthShell
        eyebrow="Account recovery"
        title="Link expired"
        subtitle="Reset links are valid for one hour and can only be used once."
        footer={<><ShieldCheck size={13} /> Your password has not been changed</>}
      >
        <div className="auth-success auth-success-warn">
          <span className="auth-success-icon">
            <Link2Off size={28} />
          </span>
          <h3>We couldn&apos;t use this link</h3>
          <p>{linkError}</p>
        </div>
        <div className="auth-actions">
          <Link className="btn btn-primary btn-block" to="/forgot-password">
            <KeyRound size={16} /> Request a new link
          </Link>
          <Link className="btn btn-ghost btn-block" to="/login">
            <ArrowLeft size={16} /> Back to sign in
          </Link>
        </div>
      </AuthShell>
    );
  }

  if (done) {
    return (
      <AuthShell
        eyebrow="All set"
        title="Password updated"
        subtitle="Your new password is active immediately."
        footer={<><ShieldCheck size={13} /> Stored as a secure hash · never in plain text</>}
      >
        <div className="auth-success">
          <span className="auth-success-icon">
            <CheckCircle2 size={30} />
          </span>
          <h3>You can sign in now</h3>
          <p>
            Your password has been changed and the reset link is no longer
            valid. Use your new password on the sign-in screen.
          </p>
        </div>
        <div className="auth-actions">
          <Link
            className="btn btn-primary btn-block"
            to="/login"
            state={{ passwordReset: true }}
          >
            <LockKeyhole size={16} /> Go to sign in
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Choose a new password"
      subtitle="Pick a strong password you haven't used before. You'll sign in with it right away."
      footer={<><ShieldCheck size={13} /> Single-use link · expires after 60 minutes</>}
    >
      <ErrorBanner message={error} />

      <form className="login-form" onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span className="field-label">New password</span>
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
              autoFocus
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
          <span className="field-label">Confirm new password</span>
          <div className="input-wrap">
            <LockKeyhole size={16} />
            <input
              className="input"
              name="password_confirm"
              type={showConfirm ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="Repeat your new password"
              value={form.password_confirm}
              onChange={handleChange}
            />
            <button
              type="button"
              className="input-action"
              onClick={() => setShowConfirm((current) => !current)}
              aria-label={showConfirm ? 'Hide password' : 'Show password'}
            >
              {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
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
          {loading ? <Spinner size={17} /> : <KeyRound size={16} />}
          {loading ? 'Updating password…' : 'Update password'}
        </button>
      </form>

      <div className="auth-actions">
        <Link className="login-link auth-back" to="/login">
          <ArrowLeft size={15} /> Back to sign in
        </Link>
      </div>
    </AuthShell>
  );
}
