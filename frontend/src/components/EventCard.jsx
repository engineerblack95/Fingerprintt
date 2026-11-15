import { useState } from 'react';
import { Mail, MapPin, Phone, ShieldAlert, Wrench } from 'lucide-react';

import { STATUS_META } from '../utils/constants';
import { formatDateTime, formatTime, initials, resolveMediaUrl, timeAgo } from '../utils/format';

export function EventCard({ event, isNew = false }) {
  const status = event.status || 'UNKNOWN';
  const meta = STATUS_META[status] || STATUS_META.UNKNOWN;
  const member = event.member;
  const memberName = member?.full_name || event.member_name || '';
  const location = event.device?.location_name || 'Unknown location';
  const [imageFailed, setImageFailed] = useState(false);

  const isEnrolled = status === 'ENROLLED';
  const isUnknown = !isEnrolled && (status === 'UNKNOWN' || !memberName);
  const normalizedStatus = isUnknown ? 'unknown' : status.toLowerCase();

  const slot = event.hardware_slot ?? event.member_id ?? '—';
  const photoUrl = member ? resolveMediaUrl(member.photo_url) : '';
  const phoneNumber = member?.phone_number || '';
  const email = member?.email || '';

  const title = isEnrolled
    ? `🔧 Hardware Update: Fingerprint enrolled for Member ID ${slot}`
    : isUnknown
      ? 'UNKNOWN PERSON DETECTED'
      : memberName;

  return (
    <article
      className={`event-card event-${normalizedStatus} ${isNew ? 'is-new' : ''}`}
    >
      <div className="event-media">
        {isEnrolled ? (
          <div className="event-media-fallback event-media-info">
            <span className="event-hero-icon">
              <Wrench size={30} />
            </span>
            <span className="event-hero-label">Hardware enrollment · slot {slot}</span>
          </div>
        ) : isUnknown ? (
          <div className="event-media-fallback event-media-alert">
            <span className="event-radar" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span className="event-hero-icon">
              <ShieldAlert size={30} />
            </span>
            <span className="event-hero-label">No registered profile match</span>
          </div>
        ) : photoUrl && !imageFailed ? (
          <img
            src={photoUrl}
            alt={memberName}
            onError={() => setImageFailed(true)}
            loading="lazy"
          />
        ) : (
          <div className="event-media-fallback">
            <span className={`event-initials fallback-${normalizedStatus}`}>
              {initials(memberName)}
            </span>
          </div>
        )}

        <span className={`event-status-pill status-${normalizedStatus}`}>
          <span className="badge-dot" />
          {meta.label}
        </span>
        {isNew ? <span className="live-new">NEW</span> : null}
        <span className="event-scrim" aria-hidden="true" />
      </div>

      <div className="event-body">
        <div className="event-topline">
          <span
            className={
              isEnrolled
                ? 'event-title event-title-info'
                : isUnknown
                  ? 'event-title event-title-danger'
                  : 'event-title'
            }
          >
            {title}
          </span>
        </div>

        {!isEnrolled && !isUnknown && (phoneNumber || email) ? (
          <div className="event-contact">
            {phoneNumber ? (
              <span className="meta-item">
                <Phone size={13} /> {phoneNumber}
              </span>
            ) : null}
            {email ? (
              <span className="meta-item">
                <Mail size={13} /> {email}
              </span>
            ) : null}
          </div>
        ) : null}

        <div className="event-meta">
          <span className="meta-item">
            <MapPin size={13} /> {location}
          </span>
          <span className="meta-item">
            <time dateTime={event.timestamp} title={formatDateTime(event.timestamp)}>
              {formatTime(event.timestamp)} · {timeAgo(event.timestamp)}
            </time>
          </span>
        </div>
      </div>
    </article>
  );
}
