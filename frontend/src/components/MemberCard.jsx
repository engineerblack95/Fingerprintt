import { useState } from 'react';
import { Fingerprint, Mail, Pencil, Phone, Trash2 } from 'lucide-react';

import { RoleBadge } from './Badges';
import { formatDate, initials, resolveMediaUrl } from '../utils/format';

export function MemberCard({ member, onEdit, onDelete, onEnroll, enrolling }) {
  const [imageFailed, setImageFailed] = useState(false);
  const photoUrl = resolveMediaUrl(member.photo_url);
  const fingerprints = member.fingerprints || [];
  const hasPending = fingerprints.some((item) => item.sync_status === 'PENDING');
  const fingerprintState = !member.fingerprint_count
    ? { label: 'No template', className: 'fp-none' }
    : hasPending
      ? { label: 'Sync pending', className: 'fp-pending' }
      : { label: 'Template synced', className: 'fp-synced' };

  return (
    <article className={`member-card ${member.is_active ? '' : 'member-inactive'}`}>
      <div className="member-card-top">
        <div className="member-photo">
          {photoUrl && !imageFailed ? (
            <img
              src={photoUrl}
              alt={member.full_name}
              onError={() => setImageFailed(true)}
              loading="lazy"
            />
          ) : (
            <span className="avatar avatar-photo">{initials(member.full_name)}</span>
          )}
        </div>
        <div className="member-identity">
          <div className="member-name-row">
            <h3>{member.full_name}</h3>
            {!member.is_active ? <span className="badge badge-muted">Inactive</span> : null}
          </div>
          <span className="member-username">@{member.username}</span>
          <div className="member-badges">
            <RoleBadge role={member.role} />
          </div>
        </div>
      </div>

      <div className="member-details">
        <span>
          <Mail size={14} /> {member.email}
        </span>
        <span>
          <Phone size={14} /> {member.phone_number}
        </span>
      </div>

      <div className="member-foot">
        <span className={`fp-chip ${fingerprintState.className}`}>
          <Fingerprint size={13} /> {fingerprintState.label}
        </span>
        <span className="member-created">Added {formatDate(member.created_at)}</span>
      </div>

      <div className="member-actions">
        <button type="button" className="member-action" onClick={() => onEdit(member)}>
          <Pencil size={14} /> Edit
        </button>
        <button
          type="button"
          className="member-action"
          onClick={() => onEnroll(member)}
          disabled={enrolling || !member.fingerprint_count}
          title={
            member.fingerprint_count
              ? 'Queue templates for the next device sync'
              : 'No fingerprint template on file yet'
          }
        >
          <Fingerprint size={14} /> {enrolling ? 'Queueing…' : 'Enroll'}
        </button>
        <button type="button" className="member-action danger" onClick={() => onDelete(member)}>
          <Trash2 size={14} /> Delete
        </button>
      </div>
    </article>
  );
}
