import React, { useEffect, useMemo, useState } from 'react';
import Sidebar from '../components/Sidebar';
import BottomNav from '../components/BottomNav';
import Toast from '../components/Toast';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

function formatUptime(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${hours}h ${minutes}m ${seconds}s`;
}

function Settings() {
  const [threshold, setThreshold] = useState(85);
  const [maxEmails, setMaxEmails] = useState(10);
  const [refreshInterval, setRefreshInterval] = useState('30 min');
  const [toastMessage, setToastMessage] = useState('');
  const [uptime, setUptime] = useState(0);
  const [apiOnline, setApiOnline] = useState(false);
  const [responseTime, setResponseTime] = useState(0);

  useEffect(() => {
    const tick = setInterval(() => setUptime((prev) => prev + 1), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    let mounted = true;

    const pingHealth = async () => {
      const started = performance.now();
      try {
        const res = await fetch(`${API_BASE}/health`);
        const elapsed = performance.now() - started;
        if (!mounted) return;
        setApiOnline(res.ok);
        setResponseTime(Math.max(5, Math.round(elapsed)));
      } catch (error) {
        if (!mounted) return;
        setApiOnline(false);
      }
    };

    pingHealth();
    const interval = setInterval(pingHealth, 15000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const apiResponseScore = useMemo(() => {
    if (!apiOnline) return 5;
    if (responseTime <= 80) return 92;
    if (responseTime <= 160) return 74;
    return 52;
  }, [apiOnline, responseTime]);

  const handleSave = () => {
    setToastMessage('Settings saved successfully');
  };

  const clearMemory = async () => {
    try {
      const res = await fetch(`${API_BASE}/clear-memory`, { method: 'POST' });
      if (!res.ok) throw new Error('Endpoint unavailable');
      setToastMessage('Memory cleared');
    } catch (error) {
      setToastMessage('Clear memory endpoint not available yet');
    }
  };

  const resetAnalytics = async () => {
    try {
      const res = await fetch(`${API_BASE}/reset-analytics`, { method: 'POST' });
      if (!res.ok) throw new Error('Endpoint unavailable');
      setToastMessage('Analytics reset completed');
    } catch (error) {
      setToastMessage('Reset analytics endpoint not available yet');
    }
  };

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="content-area page-content">
        <section className="small-hero glass-card">
          <h1>System Configuration</h1>
          <p>Manage API connections, pipeline behavior, and model health.</p>
        </section>

        <section className="settings-grid">
          <div className="settings-left-col">
            <div className="glass-card settings-card">
              <h3>API Connections</h3>

              <div className="settings-row">
                <div className="settings-row-left">
                  <span className="material-symbols-outlined">smart_toy</span>
                  <span>Gemini 2.0 Flash</span>
                </div>
                <span className="badge badge-action-green">Connected</span>
              </div>

              <div className="settings-row">
                <div className="settings-row-left">
                  <span className="material-symbols-outlined">mail</span>
                  <span>Gmail API</span>
                </div>
                <span className="badge badge-action-green">Connected</span>
              </div>

              <div className="settings-row">
                <div className="settings-row-left">
                  <span className="material-symbols-outlined">calendar_today</span>
                  <span>Google Calendar</span>
                </div>
                <span className="badge badge-action-green">Connected</span>
              </div>
            </div>

            <div className="glass-card settings-card">
              <h3>Pipeline Settings</h3>

              <label className="form-label" htmlFor="threshold-slider">
                Auto-send threshold: <strong>{threshold}</strong>
              </label>
              <input
                id="threshold-slider"
                type="range"
                min="0"
                max="100"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
              />
              <p className="form-help">Emails auto send above this score</p>

              <label className="form-label" htmlFor="max-emails">
                Max emails to process
              </label>
              <input
                id="max-emails"
                className="input-field"
                type="number"
                min="1"
                max="100"
                value={maxEmails}
                onChange={(e) => setMaxEmails(Number(e.target.value))}
              />

              <label className="form-label" htmlFor="refresh-interval">
                Refresh interval
              </label>
              <select
                id="refresh-interval"
                className="input-field"
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(e.target.value)}
              >
                <option>Real-time</option>
                <option>5 min</option>
                <option>30 min</option>
              </select>

              <button type="button" className="btn btn-primary settings-save-btn" onClick={handleSave}>
                Save Settings
              </button>
            </div>

            <div className="glass-card settings-card danger-zone">
              <h3>Danger Zone</h3>

              <div className="danger-item">
                <button type="button" className="btn btn-danger-outline" onClick={clearMemory}>
                  Clear Memory
                </button>
                <p>Clears ChromaDB vector memory store.</p>
              </div>

              <div className="danger-item">
                <button type="button" className="btn btn-danger-outline" onClick={resetAnalytics}>
                  Reset Analytics
                </button>
                <p>Resets dashboard counters to zero.</p>
              </div>
            </div>
          </div>

          <div className="settings-right-col">
            <div className="glass-card settings-card">
              <h3>AI Models Performance</h3>

              <div className="model-row">
                <div>
                  <strong>Spam Detector</strong>
                  <small>XGBoost + Sentence Transformers</small>
                </div>
                <div className="model-right">
                  <span className="badge badge-action-green">96.52%</span>
                  <span className="green-dot" />
                </div>
              </div>

              <div className="model-row">
                <div>
                  <strong>Intent Classifier</strong>
                  <small>SVM + Sentence Transformers</small>
                </div>
                <div className="model-right">
                  <span className="badge badge-action-green">90.48%</span>
                  <span className="green-dot" />
                </div>
              </div>

              <div className="model-row">
                <div>
                  <strong>Sentiment Analyzer</strong>
                  <small>VADER Rule Based</small>
                </div>
                <div className="model-right">
                  <span className="badge badge-action-green">Active</span>
                  <span className="green-dot" />
                </div>
              </div>

              <div className="model-row">
                <div>
                  <strong>Memory System</strong>
                  <small>ChromaDB Vector Database</small>
                </div>
                <div className="model-right">
                  <span className="badge badge-intent-blue">3 entries</span>
                  <span className="green-dot" />
                </div>
              </div>

              <div className="model-row">
                <div>
                  <strong>Reply Generator</strong>
                  <small>Gemini 2.0 Flash API</small>
                </div>
                <div className="model-right">
                  <span className="badge badge-action-green">Connected</span>
                  <span className="green-dot" />
                </div>
              </div>
            </div>

            <div className="glass-card settings-card">
              <h3>System Health</h3>

              <div className="health-row">
                <span>API Response Time</span>
                <strong>{apiOnline ? `${responseTime}ms` : 'Offline'}</strong>
              </div>
              <div className="progress-track">
                <div className="progress-fill progress-yellow" style={{ width: `${apiResponseScore}%` }} />
              </div>

              <div className="health-row">
                <span>Models Loaded</span>
                <strong className="text-green">5/5</strong>
              </div>

              <div className="health-row">
                <span>Memory Usage</span>
                <strong>64%</strong>
              </div>
              <div className="progress-track">
                <div className="progress-fill progress-blue" style={{ width: '64%' }} />
              </div>

              <div className="health-row">
                <span>Uptime</span>
                <strong>{formatUptime(uptime)}</strong>
              </div>

              <div className="health-row compact">
                <span>Backend Status</span>
                <span className={`badge ${apiOnline ? 'badge-action-green' : 'badge-action-red'}`}>
                  {apiOnline ? 'ONLINE' : 'OFFLINE'}
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>

      <BottomNav />
      {toastMessage && <Toast message={toastMessage} onClose={() => setToastMessage('')} />}
    </div>
  );
}

export default Settings;
