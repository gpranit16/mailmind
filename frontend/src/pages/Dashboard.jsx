import React, { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import BottomNav from '../components/BottomNav';
import Toast from '../components/Toast';

const API_BASE = 'http://localhost:8000';

const defaultAnalytics = {
  emails_processed: 0,
  spam_blocked: 0,
  auto_replied: 0,
  flagged_review: 0,
};

const pipelineNodes = [
  { key: 'gmail_fetch', label: 'GMAIL FETCH', icon: 'inbox' },
  { key: 'spam_check', label: 'SPAM CHECK', icon: 'security' },
  { key: 'sentiment', label: 'SENTIMENT', icon: 'psychology' },
  { key: 'intent', label: 'INTENT', icon: 'target' },
  { key: 'memory_recall', label: 'MEMORY RECALL', icon: 'database' },
  { key: 'gemini_reply', label: 'GEMINI REPLY', icon: 'smart_toy' },
  { key: 'final_send', label: 'FINAL SEND', icon: 'send' },
];

const intentBadgeClass = {
  meeting_request: 'badge-intent-blue',
  complaint: 'badge-intent-red',
  inquiry: 'badge-intent-purple',
  follow_up: 'badge-intent-yellow',
  urgent: 'badge-intent-orange',
  general: 'badge-intent-gray',
};

const actionBadgeClass = {
  auto_send: 'badge-action-green',
  flag_review: 'badge-action-yellow',
  escalate_human: 'badge-action-red',
};

function parseSender(rawSender = '') {
  const match = rawSender.match(/^(.*)<([^>]+)>$/);
  if (match) {
    return {
      name: match[1].trim() || match[2].trim(),
      email: match[2].trim(),
    };
  }
  return {
    name: rawSender || 'Unknown Sender',
    email: rawSender || '',
  };
}

function getInitials(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return 'MM';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function Dashboard() {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(defaultAnalytics);
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [activeStep, setActiveStep] = useState('MEMORY RECALL');
  const [apiOnline, setApiOnline] = useState(true);
  const [toastMessage, setToastMessage] = useState('');

  useEffect(() => {
    let mounted = true;

    const fetchAll = async (showLoader = false) => {
      if (showLoader && mounted) setLoading(true);

      try {
        const healthRes = await fetch(`${API_BASE}/health`);
        const isOnline = healthRes.ok;
        if (mounted) setApiOnline(isOnline);

        if (!isOnline) {
          if (mounted) {
            setLoading(false);
          }
          return;
        }

        const [analyticsRes, historyRes] = await Promise.all([
          fetch(`${API_BASE}/analytics`),
          fetch(`${API_BASE}/history?limit=500`),
        ]);

        const analyticsData = analyticsRes.ok ? await analyticsRes.json() : defaultAnalytics;
        const emailsData = historyRes.ok ? await historyRes.json() : [];

        if (mounted) {
          setAnalytics({ ...defaultAnalytics, ...analyticsData });
          setEmails(Array.isArray(emailsData) ? emailsData : []);
          setActiveStep('MEMORY RECALL');
        }
      } catch (error) {
        if (mounted) {
          setApiOnline(false);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchAll(true);
    const interval = setInterval(() => fetchAll(false), 30000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const syncInboxNow = async () => {
    setSyncing(true);
    try {
      const processRes = await fetch(`${API_BASE}/process-emails`, { method: 'POST' });
      const processedNow = processRes.ok ? await processRes.json() : [];

      const [analyticsRes, historyRes] = await Promise.all([
        fetch(`${API_BASE}/analytics`),
        fetch(`${API_BASE}/history?limit=500`),
      ]);

      const analyticsData = analyticsRes.ok ? await analyticsRes.json() : defaultAnalytics;
      const historyData = historyRes.ok ? await historyRes.json() : [];

      setAnalytics({ ...defaultAnalytics, ...analyticsData });
      setEmails(Array.isArray(historyData) ? historyData : []);

      const count = Array.isArray(processedNow) ? processedNow.length : 0;
      setToastMessage(count ? `Inbox synced: ${count} email(s) processed` : 'Inbox synced: no new unread emails');
    } catch (error) {
      setToastMessage('Sync failed. Check backend connection.');
      setApiOnline(false);
    } finally {
      setSyncing(false);
    }
  };

  const volumeData = useMemo(() => {
    const days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
    const initial = days.map((day) => ({ day, emails: 0 }));

    if (!emails.length) {
      return [
        { day: 'MON', emails: 44 },
        { day: 'TUE', emails: 66 },
        { day: 'WED', emails: 82 },
        { day: 'THU', emails: 58 },
        { day: 'FRI', emails: 70 },
        { day: 'SAT', emails: 34 },
        { day: 'SUN', emails: 26 },
      ];
    }

    emails.forEach((_, index) => {
      const dayIndex = index % 7;
      initial[dayIndex].emails += 1;
    });

    return initial;
  }, [emails]);

  const sentimentData = useMemo(() => {
    const sentimentCounts = { positive: 0, neutral: 0, negative: 0 };

    emails.forEach((emailItem) => {
      const label = emailItem?.sentiment?.label;
      if (label && Object.prototype.hasOwnProperty.call(sentimentCounts, label)) {
        sentimentCounts[label] += 1;
      }
    });

    const total = sentimentCounts.positive + sentimentCounts.neutral + sentimentCounts.negative;

    if (!total) {
      return {
        pie: [
          { name: 'Positive', value: 72, color: '#6af7ba' },
          { name: 'Neutral', value: 18, color: '#8f9aa8' },
          { name: 'Negative', value: 10, color: '#ffb4ab' },
        ],
        positivePercent: 72,
      };
    }

    const positivePercent = Math.round((sentimentCounts.positive / total) * 100);
    const neutralPercent = Math.round((sentimentCounts.neutral / total) * 100);
    const negativePercent = Math.max(0, 100 - positivePercent - neutralPercent);

    return {
      pie: [
        { name: 'Positive', value: positivePercent, color: '#6af7ba' },
        { name: 'Neutral', value: neutralPercent, color: '#8f9aa8' },
        { name: 'Negative', value: negativePercent, color: '#ffb4ab' },
      ],
      positivePercent,
    };
  }, [emails]);

  const streamItems = emails.slice(0, 12).map((item, index) => {
    const senderInfo = parseSender(item.sender || '');
    return {
      ...item,
      senderInfo,
      timeAgo: `${(index + 1) * 2} minutes ago`,
      intentLabel: item?.intent?.intent || (item?.status === 'spam' ? 'complaint' : 'general'),
      actionLabel: item?.action || (item?.status === 'spam' ? 'escalate_human' : 'flag_review'),
    };
  });

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="content-area">
        {!apiOnline && (
          <div className="offline-banner">
            <span className="material-symbols-outlined">wifi_off</span>
            <span>Backend is offline. Trying to reconnect...</span>
          </div>
        )}

        <section className="hero-section">
          <div className="hero-overlay" />
          <div className="hero-content">
            <h1 className="hero-title">
              Neural <span>Intelligence</span>
            </h1>
            <p className="hero-subtitle">
              Real-time autonomous processing of your global communications.
            </p>
            <div className="hero-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={syncInboxNow}
                disabled={syncing}
              >
                {syncing ? 'Syncing...' : 'Sync Inbox Now'}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setToastMessage('Log viewer opened')}
              >
                View Logs
              </button>
            </div>
          </div>
        </section>

        <main className="dashboard-main">
          <section className="stats-grid">
            <div className="glass-card stat-card stat-blue">
              <div className="stat-top">
                <div className="stat-icon stat-icon-blue">
                  <span className="material-symbols-outlined">forward_to_inbox</span>
                </div>
                <span className="trend up">+12%</span>
              </div>
              <h3>{Number(analytics.emails_processed || 0).toLocaleString()}</h3>
              <p>Emails Processed</p>
            </div>

            <div className="glass-card stat-card stat-green">
              <div className="stat-top">
                <div className="stat-icon stat-icon-green">
                  <span className="material-symbols-outlined">auto_awesome</span>
                </div>
                <span className="trend up">+8.4%</span>
              </div>
              <h3>{Number(analytics.auto_replied || 0).toLocaleString()}</h3>
              <p>Auto Replied</p>
            </div>

            <div className="glass-card stat-card stat-red">
              <div className="stat-top">
                <div className="stat-icon stat-icon-red">
                  <span className="material-symbols-outlined">block</span>
                </div>
                <span className="trend down">-2.1%</span>
              </div>
              <h3>{Number(analytics.spam_blocked || 0).toLocaleString()}</h3>
              <p>Spam Blocked</p>
            </div>

            <div className="glass-card stat-card stat-gold">
              <div className="stat-top">
                <div className="stat-icon stat-icon-gold">
                  <span className="material-symbols-outlined">flag</span>
                </div>
                <span className="priority">High Priority</span>
              </div>
              <h3>{Number(analytics.flagged_review || 0).toLocaleString()}</h3>
              <p>Flagged for Review</p>
            </div>
          </section>

          <section className="glass-card pipeline-card">
            <div className="pipeline-header">
              <h2>Intelligence Pipeline</h2>
              <div className="pipeline-meta">
                <span className="active-step">
                  <span className="dot" /> ACTIVE STEP: {activeStep}
                </span>
                <span className="latency">LATENCY: 142MS</span>
              </div>
            </div>

            <div className="pipeline-row">
              {pipelineNodes.map((node, index) => (
                <React.Fragment key={node.key}>
                  <div className="pipeline-node-wrap">
                    <div className={`pipeline-node ${node.label === activeStep ? 'pipeline-node-active' : ''}`}>
                      <span className="material-symbols-outlined">{node.icon}</span>
                    </div>
                    <span className={`pipeline-label ${node.label === activeStep ? 'pipeline-label-active' : ''}`}>
                      {node.label}
                    </span>
                  </div>
                  {index !== pipelineNodes.length - 1 && <span className="pipeline-connector" />}
                </React.Fragment>
              ))}
            </div>
          </section>

          <section className="charts-grid">
            <div className="glass-card chart-card volume-card">
              <div className="chart-head">
                <div>
                  <h3>Email Volume</h3>
                  <p>Weekly performance tracking</p>
                </div>
                <div className="toggle-group">
                  <button type="button" className="toggle-btn toggle-btn-active">
                    WEEKLY
                  </button>
                  <button type="button" className="toggle-btn">
                    MONTHLY
                  </button>
                </div>
              </div>
              <div className="chart-body">
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={volumeData} margin={{ top: 8, right: 12, left: -12, bottom: 4 }}>
                    <XAxis dataKey="day" stroke="#93a0ad" tickLine={false} axisLine={false} />
                    <YAxis stroke="#93a0ad" tickLine={false} axisLine={false} width={24} />
                    <Tooltip
                      cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                      contentStyle={{
                        background: '#111a28',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: 10,
                        color: '#dbe3f3',
                      }}
                    />
                    <Bar dataKey="emails" radius={[8, 8, 0, 0]}>
                      {volumeData.map((entry, idx) => (
                        <Cell key={`${entry.day}-${idx}`} fill="#e6c364" />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="glass-card chart-card sentiment-card">
              <h3>Sentiment</h3>
              <div className="donut-wrap">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={sentimentData.pie}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={70}
                      outerRadius={92}
                      stroke="none"
                      paddingAngle={2}
                    >
                      {sentimentData.pie.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: '#111a28',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: 10,
                        color: '#dbe3f3',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="donut-center">
                  <strong>{sentimentData.positivePercent}%</strong>
                  <span>POSITIVE</span>
                </div>
              </div>

              <div className="sentiment-legend">
                {sentimentData.pie.map((item) => (
                  <div key={item.name} className="legend-item">
                    <span className="legend-dot" style={{ background: item.color }} />
                    <span>{item.name}</span>
                    <strong>{item.value}%</strong>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="glass-card stream-card">
            <div className="stream-header">
              <div>
                <h2>Live Intelligence Stream</h2>
                <p>System events processed in real-time</p>
              </div>
              <button type="button" className="view-all-btn" onClick={() => navigate('/emails')}>
                VIEW ALL HISTORY <span className="material-symbols-outlined">open_in_new</span>
              </button>
            </div>

            <div className="stream-list">
              {loading &&
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={`skeleton-${i}`} className="stream-item stream-skeleton">
                    <div className="skeleton-avatar shimmer" />
                    <div className="stream-main">
                      <div className="skeleton-line shimmer" />
                      <div className="skeleton-line small shimmer" />
                    </div>
                  </div>
                ))}

              {!loading && !streamItems.length && (
                <div className="empty-state">
                  <span className="material-symbols-outlined">inbox</span>
                  <p>No processed emails yet. Click Sync Inbox Now to process unread emails.</p>
                </div>
              )}

              {!loading &&
                streamItems.map((item, index) => {
                  const intentClass = intentBadgeClass[item.intentLabel] || 'badge-intent-gray';
                  const actionClass = actionBadgeClass[item.actionLabel] || 'badge-action-yellow';
                  return (
                    <div key={`${item.id}-${index}`} className="stream-item">
                      <div className="avatar-circle">{getInitials(item.senderInfo.name)}</div>
                      <div className="stream-main">
                        <div className="stream-title-row">
                          <strong>{item.senderInfo.name}</strong>
                          <span className="time-ago">• {item.timeAgo}</span>
                        </div>
                        <p>{item.subject || 'No subject'}</p>
                      </div>
                      <div className="stream-badges">
                        <span className={`badge ${intentClass}`}>{item.intentLabel.replace('_', ' ')}</span>
                        <span className={`badge ${actionClass}`}>
                          {item.actionLabel === 'auto_send'
                            ? 'AUTO SENT'
                            : item.actionLabel === 'flag_review'
                            ? 'REVIEW'
                            : 'ESCALATE'}
                        </span>
                      </div>
                      <button type="button" className="stream-visibility" aria-label="view">
                        <span className="material-symbols-outlined">visibility</span>
                      </button>
                    </div>
                  );
                })}
            </div>
          </section>
        </main>
      </div>

      <BottomNav />
      {toastMessage && <Toast message={toastMessage} onClose={() => setToastMessage('')} />}
    </div>
  );
}

export default Dashboard;
