import React, { useEffect, useMemo, useState } from 'react';
import Sidebar from '../components/Sidebar';
import BottomNav from '../components/BottomNav';
import Toast from '../components/Toast';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

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

function sentimentUI(label = 'neutral') {
  if (label === 'positive') return { emoji: '😊', text: 'Positive', className: 'text-green' };
  if (label === 'negative') return { emoji: '😟', text: 'Negative', className: 'text-red' };
  return { emoji: '😐', text: 'Neutral', className: 'text-muted' };
}

function confidenceClass(confidence) {
  if (confidence >= 85) return 'progress-green';
  if (confidence >= 60) return 'progress-yellow';
  return 'progress-red';
}

function Emails() {
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState('All');
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [toastMessage, setToastMessage] = useState('');

  useEffect(() => {
    let mounted = true;

    const fetchHistory = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/history?limit=500`);
        const data = res.ok ? await res.json() : [];
        if (mounted) setEmails(Array.isArray(data) ? data : []);
      } catch (error) {
        if (mounted) setEmails([]);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchHistory();
    return () => {
      mounted = false;
    };
  }, []);

  const syncInbox = async () => {
    setSyncing(true);
    try {
      const processRes = await fetch(`${API_BASE}/process-emails`, { method: 'POST' });
      const processedNow = processRes.ok ? await processRes.json() : [];

      const historyRes = await fetch(`${API_BASE}/history?limit=500`);
      const historyData = historyRes.ok ? await historyRes.json() : [];
      setEmails(Array.isArray(historyData) ? historyData : []);

      const count = Array.isArray(processedNow) ? processedNow.length : 0;
      setToastMessage(count ? `Inbox synced: ${count} email(s) processed` : 'Inbox synced: no new unread emails');
    } catch (error) {
      setToastMessage('Sync failed. Check backend connection.');
    } finally {
      setSyncing(false);
    }
  };

  const filteredEmails = useMemo(() => {
    const q = search.trim().toLowerCase();

    return emails.filter((item) => {
      const senderInfo = parseSender(item.sender || '');
      const senderStr = `${senderInfo.name} ${senderInfo.email}`.toLowerCase();
      const subjectStr = (item.subject || '').toLowerCase();

      const matchesSearch = !q || senderStr.includes(q) || subjectStr.includes(q);
      if (!matchesSearch) return false;

      if (activeFilter === 'Auto Sent') return item.action === 'auto_send';
      if (activeFilter === 'Flagged') return item.action === 'flag_review';
      if (activeFilter === 'Spam') return item.status === 'spam' || item?.spam?.is_spam;
      return true;
    });
  }, [emails, search, activeFilter]);

  const openModal = (emailItem) => {
    if (!emailItem?.reply) return;
    setSelectedEmail(emailItem);
  };

  const copyReply = async () => {
    if (!selectedEmail?.reply) return;
    try {
      await navigator.clipboard.writeText(selectedEmail.reply);
      setToastMessage('Reply copied to clipboard');
    } catch (error) {
      setToastMessage('Unable to copy reply');
    }
  };

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="content-area page-content">
        <section className="small-hero glass-card">
          <h1>Email Intelligence</h1>
          <p>Explore processed conversations, confidence, intent, and automated actions.</p>
        </section>

        <section className="glass-card search-card">
          <div className="search-input-wrap">
            <span className="material-symbols-outlined">search</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by sender or subject"
            />
          </div>

          <div className="filter-pills">
            {['All', 'Auto Sent', 'Flagged', 'Spam'].map((filter) => (
              <button
                key={filter}
                type="button"
                className={`filter-pill ${activeFilter === filter ? 'filter-pill-active' : ''}`}
                onClick={() => setActiveFilter(filter)}
              >
                {filter}
              </button>
            ))}

            <button type="button" className="filter-pill" onClick={syncInbox} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Sync Inbox Now'}
            </button>
          </div>
        </section>

        <section className="glass-card table-card">
          <div className="table-wrap">
            <table className="emails-table">
              <thead>
                <tr>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Spam</th>
                  <th>Sentiment</th>
                  <th>Intent</th>
                  <th>Meeting Slot</th>
                  <th>Confidence</th>
                  <th>Action</th>
                  <th>Reply</th>
                </tr>
              </thead>
              <tbody>
                {loading &&
                  Array.from({ length: 6 }).map((_, idx) => (
                    <tr key={`loading-${idx}`} className="row-loading">
                      <td colSpan={9}>
                        <div className="skeleton-line shimmer" />
                      </td>
                    </tr>
                  ))}

                {!loading && !filteredEmails.length && (
                  <tr>
                    <td colSpan={9}>
                      <div className="empty-state small">
                        <span className="material-symbols-outlined">mark_email_unread</span>
                        <p>No emails found for current filters.</p>
                      </div>
                    </td>
                  </tr>
                )}

                {!loading &&
                  filteredEmails.map((item, index) => {
                    const senderInfo = parseSender(item.sender || '');
                    const isSpam = item.status === 'spam' || item?.spam?.is_spam;
                    const spamConfidence = Number(item?.spam?.confidence_percentage || 0);
                    const sentimentLabel = item?.sentiment?.label || 'neutral';
                    const sentiment = sentimentUI(sentimentLabel);
                    const intentLabel = item?.intent?.intent || (isSpam ? 'complaint' : 'general');
                    const intentConfidence = Number(item?.intent?.confidence_percentage || spamConfidence);
                    const actionLabel = item?.action || (isSpam ? 'escalate_human' : 'flag_review');
                    const replyText = item?.reply || '';
                    const meetingStatus = item?.meeting_status || {};
                    const isMeeting = intentLabel === 'meeting_request' || meetingStatus?.checked;

                    const meetingBadgeClass =
                      meetingStatus.available === true
                        ? 'badge-action-green'
                        : meetingStatus.available === false
                        ? 'badge-action-red'
                        : 'badge-action-yellow';

                    const meetingText = !isMeeting
                      ? '—'
                      : meetingStatus.display || meetingStatus.reason || 'Check pending';

                    return (
                      <tr
                        key={`${item.id || index}-${index}`}
                        className={`email-row ${replyText ? 'clickable' : ''}`}
                        onClick={() => openModal(item)}
                      >
                        <td>
                          <div className="sender-cell">
                            <div className="avatar-circle">{getInitials(senderInfo.name)}</div>
                            <div>
                              <strong>{senderInfo.name}</strong>
                              <small>{senderInfo.email || '—'}</small>
                            </div>
                          </div>
                        </td>
                        <td title={item.subject || ''}>{(item.subject || 'No subject').slice(0, 40)}</td>
                        <td>
                          <div>
                            <span className={`badge ${isSpam ? 'badge-action-red' : 'badge-action-green'}`}>
                              {isSpam ? 'SPAM' : 'NOT SPAM'}
                            </span>
                            <small>{Math.round(spamConfidence)}%</small>
                          </div>
                        </td>
                        <td>
                          <div className={`sentiment-cell ${sentiment.className}`}>
                            <span>{sentiment.emoji}</span>
                            <span>{sentiment.text}</span>
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${intentBadgeClass[intentLabel] || 'badge-intent-gray'}`}>
                            {intentLabel.replace('_', ' ')}
                          </span>
                        </td>
                        <td>
                          {!isMeeting ? (
                            <small>—</small>
                          ) : (
                            <>
                              <span className={`badge ${meetingBadgeClass}`}>
                                {meetingStatus.available === true
                                  ? 'FREE'
                                  : meetingStatus.available === false
                                  ? 'BUSY'
                                  : 'UNKNOWN'}
                              </span>
                              <small title={meetingText}>{String(meetingText).slice(0, 36)}</small>
                            </>
                          )}
                        </td>
                        <td>
                          <div className="confidence-cell">
                            <div className="progress-track">
                              <div
                                className={`progress-fill ${confidenceClass(intentConfidence)}`}
                                style={{ width: `${Math.min(100, Math.max(0, intentConfidence))}%` }}
                              />
                            </div>
                            <small>{Math.round(intentConfidence)}%</small>
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${actionBadgeClass[actionLabel] || 'badge-action-yellow'}`}>
                            {actionLabel}
                          </span>
                        </td>
                        <td title={replyText}>{replyText ? `${replyText.slice(0, 40)}...` : 'No reply generated'}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <BottomNav />

      {selectedEmail && (
        <div className="modal-overlay" onClick={() => setSelectedEmail(null)}>
          <div className="modal-card glass-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h3>Generated Reply</h3>
                <p>{parseSender(selectedEmail.sender || '').name}</p>
              </div>
              <button type="button" className="icon-btn" onClick={() => setSelectedEmail(null)}>
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="modal-body">{selectedEmail.reply}</div>
            <div className="modal-actions">
              <button type="button" className="btn btn-primary" onClick={copyReply}>
                Copy Reply
              </button>
            </div>
          </div>
        </div>
      )}

      {toastMessage && <Toast message={toastMessage} onClose={() => setToastMessage('')} />}
    </div>
  );
}

export default Emails;
