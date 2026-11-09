import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  ExternalLink,
  Fingerprint,
  LayoutDashboard,
  LogOut,
  Menu,
  Router,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { getAdminUrl } from '../utils/constants';
import { initials } from '../utils/format';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/members', label: 'Members', icon: Users },
  { to: '/logs', label: 'Entry logs', icon: ScrollText },
  { to: '/devices', label: 'Devices', icon: Router },
];

const ADMIN_URL = getAdminUrl();

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const displayName = user?.full_name || user?.username || 'Owner';

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-glow" />
        <div className="brand">
          <div className="brand-mark">
            <Fingerprint size={24} />
          </div>
          <div className="brand-text">
            <span className="brand-name">Fingerprint</span>
            <span className="brand-sub">Access Control</span>
          </div>
          <button
            type="button"
            className="sidebar-close"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="nav" aria-label="Main navigation">
          <span className="nav-label">Workspace</span>
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">
                <Icon size={19} />
              </span>
              <span>{label}</span>
              <span className="nav-active-dot" />
            </NavLink>
          ))}

          <span className="nav-label nav-label-spaced">Administration</span>
          <a
            href={ADMIN_URL}
            className="nav-item"
            target="_blank"
            rel="noreferrer"
            title="Open the Django admin dashboard in a new tab"
          >
            <span className="nav-icon">
              <Settings size={19} />
            </span>
            <span>Django admin</span>
            <ExternalLink size={13} className="nav-external" />
          </a>
        </nav>

        <div className="sidebar-spacer" />

        <div className="edge-card">
          <span className="edge-icon">
            <ShieldCheck size={17} />
          </span>
          <div>
            <strong>Edge matching</strong>
            <p>Fingerprints are matched on the device. Only results reach the server.</p>
          </div>
        </div>

        <div className="sidebar-user">
          <div className="avatar avatar-sm">{initials(displayName)}</div>
          <div className="sidebar-user-meta">
            <strong>{displayName}</strong>
            <span>{user?.email || 'Owner account'}</span>
          </div>
          <button
            type="button"
            className="btn-icon btn-icon-dark"
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>

      {sidebarOpen ? (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation overlay"
        />
      ) : null}

      <div className="main-shell">
        <header className="mobile-topbar">
          <button
            type="button"
            className="btn-icon"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>
          <div className="mobile-brand">
            <Fingerprint size={19} />
            <span>Fingerprint Access</span>
          </div>
          <div className="avatar avatar-sm">{initials(displayName)}</div>
        </header>
        <main className="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
