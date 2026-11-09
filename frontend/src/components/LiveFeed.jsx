import { Activity, Radio, ShieldCheck } from 'lucide-react';

import { EventCard } from './EventCard';
import { EmptyState } from './EmptyState';

const CONNECTION_META = {
  connected: { label: 'Live', className: 'live-connected' },
  connecting: { label: 'Connecting', className: 'live-connecting' },
  reconnecting: { label: 'Reconnecting', className: 'live-connecting' },
  disconnected: { label: 'Offline', className: 'live-disconnected' },
};

export function LiveFeed({ events = [], connectionStatus = 'connecting', liveCount = 0 }) {
  const connection = CONNECTION_META[connectionStatus] || CONNECTION_META.connecting;

  return (
    <section className="card live-feed">
      <header className="card-head">
        <div>
          <div className="card-title-row">
            <span className="card-icon card-icon-indigo">
              <Activity size={17} />
            </span>
            <h2 className="card-title">Live event feed</h2>
          </div>
          <p className="card-subtitle">Every match reported by the edge devices, in real time.</p>
        </div>
        <div className="live-feed-tools">
          {liveCount > 0 ? (
            <span className="live-counter">
              <Radio size={13} /> {liveCount} new
            </span>
          ) : null}
          <span className={`live-pill ${connection.className}`}>
            <span className="live-dot" />
            {connection.label}
          </span>
        </div>
      </header>

      <div className="event-list">
        {events.length ? (
          events.map((event) => (
            <EventCard key={event.id} event={event} isNew={Boolean(event.isNew)} />
          ))
        ) : (
          <EmptyState
            icon={ShieldCheck}
            title="Waiting for the first entry"
            message="Events will appear here the moment a device reports a fingerprint match."
          />
        )}
      </div>
    </section>
  );
}
