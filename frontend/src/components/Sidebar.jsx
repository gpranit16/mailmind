import React from 'react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/emails', label: 'Emails', icon: 'mail' },
  { to: '/calendar', label: 'Calendar', icon: 'calendar_month' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
];

function Sidebar() {
  return (
    <aside className="sidebar desktop-only">
      <div className="sidebar-logo-wrap">
        <div className="logo-square">M</div>
        <div>
          <h1 className="logo-title">MailMind</h1>
          <p className="logo-subtitle">Autonomous AI</p>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link-active' : ''}`
            }
          >
            <span className="material-symbols-outlined">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="api-status-card glass-card">
        <span className="material-symbols-outlined api-status-icon">sensors</span>
        <div>
          <div className="api-status-title">API Connected</div>
          <div className="api-status-sub">
            <span className="green-dot pulse-dot" />
            <span>SYSTEM ONLINE</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
