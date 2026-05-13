import React from 'react';
import { NavLink } from 'react-router-dom';

const items = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/emails', label: 'Emails', icon: 'mail' },
  { to: '/calendar', label: 'Calendar', icon: 'calendar_month' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
];

function BottomNav() {
  return (
    <nav className="bottom-nav mobile-only">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) => `bottom-nav-link ${isActive ? 'bottom-nav-active' : ''}`}
        >
          <span className="material-symbols-outlined">{item.icon}</span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export default BottomNav;
