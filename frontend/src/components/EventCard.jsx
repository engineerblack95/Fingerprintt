import { useState } from 'react';
import { Mail, MapPin, Phone, ShieldAlert, Wrench } from 'lucide-react';

import { STATUS_META } from '../utils/constants';
import { formatDateTime, formatTime, initials, resolveMediaUrl, timeAgo } from '../utils/format';

export function EventCard({ event, isNew = false }) {
  const status = event.status || 'UNKNOWN';
  const meta = STATUS_META[status] || STATUS_META.UNKNOWN;
  const member = event.member;
  const location = event.device?.location_name || 'Unknown location';
  const [imageFailed, setImageFailed] = useState(false);

  if (status === 'ENROLLED') {
    const slot = event.hardware_slot ?? event.member_id ?? '—';
    return (
      <article className={`event-card event-enrolled ${isNew ? 'is-new' : ''}`}>
        <div className="event-icon event-icon-info">
          <Wrench size={22} />
        </div>
        <div className="event-body">
          <div className="event-topline">
            <span className="event-title event-title-info">
              🔧 Hardware Update: Fingerprint enrolled for Member ID {slot}
            </span>
            {isNew ? <span className="live-new">NEW</span> : null}
          </div>
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
        <span className="event-status-pill status-enrolled">
          <span className="badge-dot" />
          {meta.label}
        </span>
      </article>
    );
  }

  if (status === 'UNKNOWN' || !member) {
    return (
      <article className={`event-card event-unknown ${isNew ? 'is-new' : ''}`}>
        <div className="event-icon event-icon-danger">
          <ShieldAlert size={22} />
        </div>
        <div className="event-body">
          <div className="event-topline">
            <span className="event-title event-title-danger">UNKNOWN PERSON DETECTED</span>
            {isNew ? <span className="live-new">NEW</span> : null}
          </div>
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
        <span className={`event-status-pill status-${status.toLowerCase()}`}>
          <span className="badge-dot" />
          {meta.label}
        </span>
      </article>
    );
  }

  const photoUrl = resolveMediaUrl(member.photo_url);

  return (
    <article className={`event-card event-${status.toLowerCase()} ${isNew ? 'is-new' : ''}`}>
      <div className="event-photo">
        {photoUrl && !imageFailed ? (
          <img
            src={photoUrl}
            alt={member.full_name}
            onError={() => setImageFailed(true)}
            loading="lazy"
          />
        ) : (
          <span className={`avatar avatar-photo fallback-${status.toLowerCase()}`}>
            {initials(member.full_name)}
          </span>
        )}
      </div>

      <div className="event-body">
        <div className="event-topline">
          <span className="event-title">{member.full_name}</span>
          <span className={`badge badge-${status.toLowerCase()}`}>
            <span className="badge-dot" />
            {meta.label}
          </span>
          {isNew ? <span className="live-new">NEW</span> : null}
        </div>

        <div className="event-contact">
          <span className="meta-item">
            <Phone size={13} /> {member.phone_number}
          </span>
          <span className="meta-item">
            <Mail size={13} /> {member.email}
          </span>
        </div>

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
