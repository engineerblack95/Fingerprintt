import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, Mail, MailCheck, Send } from 'lucide-react';

import { AuthShell } from '../components/AuthShell';
import { ErrorBanner } from '../components/ErrorBanner';
import { Spinner } from '../components/Loader';
import { authApi, getErrorMessage } from '../api/client';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sentTo, setSentTo] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    const address = email.trim();
    if (!address) {
      setError('Enter the email address linked to your owner account.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) {
      setError('Enter a valid email address, for example owner@example.com.');
      return;
    }

    setLoading(true);
    try {
      await authApi.requestPasswordReset({ email: address });
      setSentTo(address);
    } catch (requestError) {
      setError(
        getErrorMessage(
          requestError,
          'We could not start the reset right now. Please try again in a moment.',
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  if (sentTo) {
    return (
      <AuthShell
        eyebrow="Check your inbox"
        title="Reset link sent"
        subtitle="For your security the link is single-use and expires automatically."
        footer={<><MailCheck size={13} /> Delivered by Brevo · check Spam or Promotions too</>}
      >
        <div className="auth-success">
          <span className="auth-success-icon">
            <CheckCircle2 size={30} />
          </span>
          <h3>We&apos;ve sent a reset link</h3>
          <p>
            If an account exists for <strong>{sentTo}</strong>, an email with a
            password reset link is on its way. Open it on this device to choose
            a new password.
          </p>
          <p className="auth-success-note">
            Nothing arrived? Wait a minute, check the spam folder, then try again.
          </p>
        </div>

        <div className="auth-actions">
          <button
            type="button"
            className="btn btn-ghost btn-block"
            onClick={() => {
              setSentTo('');
              setEmail('');
            }}
          >
            <Send size={16} /> Use a different email
          </button>
          <Link className="btn btn-primary btn-block" to="/login">
            <ArrowLeft size={16} /> Back to sign in
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Forgot your password?"
      subtitle="Enter the email address registered on your owner account and we'll send you a secure reset link."
      footer={<><Mail size={13} /> We never reveal whether an email is registered</>}
    >
      <ErrorBanner message={error} />

      <form className="login-form" onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span className="field-label">Email address</span>
          <div className="input-wrap">
            <Mail size={16} />
            <input
              className="input"
              name="email"
              type="email"
              autoComplete="email"
              inputMode="email"
              placeholder="owner@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoFocus
            />
          </div>
        </label>

        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
          {loading ? <Spinner size={17} /> : <Send size={16} />}
          {loading ? 'Sending reset link…' : 'Send reset link'}
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
