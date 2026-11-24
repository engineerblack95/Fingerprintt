import { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle2,
  KeyRound,
  MailCheck,
  RefreshCw,
  Send,
  ShieldAlert,
  X,
} from 'lucide-react';

import { getErrorMessage, notificationsApi } from '../api/client';
import { useToast } from '../context/ToastContext';
import { Spinner } from './Loader';

/**
 * Administrator-only panel that proves email delivery works on the deployed
 * service and lets the owner install a corrected Brevo key without host access.
 */
export function EmailHealthCard() {
  const toast = useToast();
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [showKeyForm, setShowKeyForm] = useState(false);
  const [apiKey, setApiKey] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await notificationsApi.status();
      setState(data);
      setError('');
    } catch (loadError) {
      setState(null);
      setError(
        getErrorMessage(loadError, 'Could not read the email configuration.'),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSendTest = async () => {
    setSending(true);
    try {
      const { data } = await notificationsApi.sendTest();
      toast.success(data.detail || 'Test email sent.');
    } catch (sendError) {
      toast.error(
        getErrorMessage(sendError, 'The test email could not be delivered.'),
      );
    } finally {
      setSending(false);
    }
  };

  const handleSaveKey = async (event) => {
    event.preventDefault();
    if (!apiKey.trim()) return;
    setSaving(true);
    try {
      const { data } = await notificationsApi.setKey(apiKey.trim());
      toast.success(data.detail || 'The new key is active.');
      setApiKey('');
      setShowKeyForm(false);
      await load();
    } catch (saveError) {
      toast.error(getErrorMessage(saveError, 'That key was not accepted.'));
    } finally {
      setSaving(false);
    }
  };

  const ok = state?.ok;
  const tone = loading ? 'neutral' : ok ? 'ok' : 'danger';

  return (
    <section className={`card email-card email-card-${tone}`}>
      <header className="card-head">
        <div>
          <div className="card-title-row">
            <span className={`card-icon ${ok ? 'card-icon-green' : 'card-icon-red'}`}>
              {ok ? <MailCheck size={17} /> : <ShieldAlert size={17} />}
            </span>
            <h2 className="card-title">Email delivery</h2>
          </div>
          <p className="card-subtitle">
            Access alerts and password reset links for this deployment.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={load}
          disabled={loading}
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
          Check
        </button>
      </header>

      <div className="card-body email-card-body">
        {loading && !state ? (
          <p className="email-line muted">
            <Spinner size={15} /> Checking the transport…
          </p>
        ) : null}

        {error ? <p className="email-line danger">{error}</p> : null}

        {state ? (
          <>
            <p className={`email-line ${ok ? 'ok' : 'danger'}`}>
              {ok ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}
              {ok ? 'Brevo accepted the active key.' : state.detail}
            </p>

            <dl className="email-meta">
              <div>
                <dt>Sender</dt>
                <dd>{state.from_email}</dd>
              </div>
              <div>
                <dt>Alerts to</dt>
                <dd>{state.owner_email || 'Not configured'}</dd>
              </div>
              <div>
                <dt>Key</dt>
                <dd>
                  {state.key}
                  <span className="email-source">{state.source}</span>
                </dd>
              </div>
              <div>
                <dt>Build</dt>
                <dd>{state.commit}</dd>
              </div>
            </dl>

            <div className="email-actions">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleSendTest}
                disabled={sending || !ok}
                title={ok ? 'Send a real message to the alert inbox' : 'Fix the key first'}
              >
                {sending ? <Spinner size={14} /> : <Send size={14} />}
                {sending ? 'Sending…' : 'Send test email'}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowKeyForm((current) => !current)}
              >
                <KeyRound size={14} />
                {showKeyForm ? 'Cancel' : 'Replace key'}
              </button>
            </div>

            {showKeyForm ? (
              <form className="email-key-form" onSubmit={handleSaveKey}>
                <label className="field">
                  <span className="field-label">Brevo API key</span>
                  <div className="input-wrap">
                    <KeyRound size={15} />
                    <input
                      className="input"
                      type="password"
                      autoComplete="off"
                      spellCheck={false}
                      placeholder="xkeysib-…"
                      value={apiKey}
                      onChange={(event) => setApiKey(event.target.value)}
                    />
                    {apiKey ? (
                      <button
                        type="button"
                        className="input-action"
                        onClick={() => setApiKey('')}
                        aria-label="Clear the key"
                      >
                        <X size={15} />
                      </button>
                    ) : null}
                  </div>
                </label>
                <p className="field-hint">
                  Copied from Brevo → SMTP &amp; API → API keys. It is validated
                  with Brevo before it replaces the current key, stored encrypted,
                  and never displayed again.
                </p>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={saving || !apiKey.trim()}
                >
                  {saving ? <Spinner size={14} /> : <CheckCircle2 size={14} />}
                  {saving ? 'Validating…' : 'Validate and install'}
                </button>
              </form>
            ) : null}
          </>
        ) : null}
      </div>
    </section>
  );
}
