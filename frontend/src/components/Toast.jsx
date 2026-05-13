import React, { useEffect, useState } from 'react';

function Toast({ message, onClose }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(true);
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onClose?.(), 250);
    }, 4000);

    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className={`toast ${visible ? 'toast-show' : ''}`} role="status" aria-live="polite">
      <span className="material-symbols-outlined">notifications</span>
      <span>{message}</span>
    </div>
  );
}

export default Toast;
