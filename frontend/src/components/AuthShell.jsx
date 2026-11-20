import { Fingerprint, KeyRound, ShieldCheck, Sparkles } from 'lucide-react';

/**
 * Shared chrome for the public account-recovery pages.
 *
 * It mirrors the sign-in screen (same brand panel, card and typography) so the
 * reset journey feels like part of the same product rather than a separate
 * form.
 */
export function AuthShell({ eyebrow, title, subtitle, children, footer }) {
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
              <Sparkles size={14} /> Account recovery · secure by design
            </span>
            <h1>
              Back to your
              <br />
              <span>dashboard.</span>
            </h1>
            <p>
              Password recovery is handled with single-use, time-limited links.
              Nobody else can use the link once your new password is saved.
            </p>

            <ul className="login-features">
              <li>
                <span className="login-feature-icon">
                  <ShieldCheck size={18} />
                </span>
                <div>
                  <strong>Single-use reset links</strong>
                  <span>Every link expires automatically and stops working after one reset.</span>
                </div>
              </li>
              <li>
                <span className="login-feature-icon">
                  <KeyRound size={18} />
                </span>
                <div>
                  <strong>No password is ever emailed</strong>
                  <span>You choose the new password yourself; it is stored only as a secure hash.</span>
                </div>
              </li>
              <li>
                <span className="login-feature-icon">
                  <Fingerprint size={18} />
                </span>
                <div>
                  <strong>Your data stays protected</strong>
                  <span>The rest of your account, devices and entry history remain untouched.</span>
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
            <span className="eyebrow">{eyebrow}</span>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>

          {children}

          {footer ? <div className="login-card-foot">{footer}</div> : null}
        </div>
      </section>
    </div>
  );
}
