import { useCallback, useEffect, useRef, useState } from 'react';

function buildSocketUrl(token) {
  const configured = import.meta.env.VITE_WS_URL;
  let base = configured;
  if (!base) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    base = `${protocol}//${window.location.host}/ws/dashboard/`;
  }
  const url = new URL(base, window.location.href);
  url.searchParams.set('token', token);
  return url.toString();
}

/**
 * Subscribes to the authenticated dashboard WebSocket with automatic
 * exponential-backoff reconnection and application-level keepalive pings.
 */
export function useDashboardSocket({ token, onEvent, enabled = true }) {
  const [status, setStatus] = useState('disconnected');
  const onEventRef = useRef(onEvent);
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const pingTimerRef = useRef(null);
  const attemptsRef = useRef(0);
  const closedByUserRef = useRef(false);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    if (!token || !enabled) {
      setStatus('disconnected');
      return;
    }

    setStatus(attemptsRef.current > 0 ? 'reconnecting' : 'connecting');
    let socket;
    try {
      socket = new WebSocket(buildSocketUrl(token));
    } catch {
      setStatus('disconnected');
      return;
    }
    socketRef.current = socket;

    socket.onopen = () => {
      attemptsRef.current = 0;
      setStatus('connected');
      window.clearInterval(pingTimerRef.current);
      pingTimerRef.current = window.setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: 'ping' }));
        }
      }, 25000);
    };

    socket.onmessage = (messageEvent) => {
      try {
        const payload = JSON.parse(messageEvent.data);
        if (payload.type === 'entry_event') {
          onEventRef.current?.(payload);
        }
      } catch {
        // Ignore malformed frames.
      }
    };

    socket.onerror = () => {
      socket.close();
    };

    socket.onclose = () => {
      window.clearInterval(pingTimerRef.current);
      if (closedByUserRef.current) return;
      setStatus('disconnected');
      const delay = Math.min(1000 * 2 ** attemptsRef.current, 15000);
      attemptsRef.current += 1;
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = window.setTimeout(connect, delay);
    };
  }, [token, enabled]);

  useEffect(() => {
    closedByUserRef.current = false;
    connect();
    return () => {
      closedByUserRef.current = true;
      window.clearTimeout(reconnectTimerRef.current);
      window.clearInterval(pingTimerRef.current);
      if (socketRef.current) {
        socketRef.current.onclose = null;
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [connect]);

  return { status };
}
