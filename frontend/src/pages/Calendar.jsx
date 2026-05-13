import React, { useEffect, useMemo, useState } from 'react';
import Sidebar from '../components/Sidebar';
import BottomNav from '../components/BottomNav';
import Toast from '../components/Toast';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

function formatDateTime(dateTimeLike) {
  if (!dateTimeLike) return '—';
  const date = new Date(dateTimeLike);
  if (Number.isNaN(date.getTime())) return String(dateTimeLike);
  return date.toLocaleString();
}

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

function Calendar() {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [calendarError, setCalendarError] = useState('');
  const [processedMeetings, setProcessedMeetings] = useState([]);
  const [upcomingEvents, setUpcomingEvents] = useState([]);
  const [toastMessage, setToastMessage] = useState('');

  const fetchMeetings = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/calendar/meetings?limit=200&upcoming=20`);
      const data = res.ok ? await res.json() : {};
      setProcessedMeetings(Array.isArray(data.processed_meetings) ? data.processed_meetings : []);
      setUpcomingEvents(Array.isArray(data.upcoming_events) ? data.upcoming_events : []);
      setCalendarError(data.calendar_error || '');
    } catch (error) {
      setProcessedMeetings([]);
      setUpcomingEvents([]);
      setCalendarError('Unable to reach backend calendar endpoint.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const safeFetch = async () => {
      if (!mounted) return;
      await fetchMeetings();
    };

    safeFetch();
    const timer = setInterval(safeFetch, 20000);

    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const syncNow = async () => {
    setSyncing(true);
    try {
      const processRes = await fetch(`${API_BASE}/process-emails`, { method: 'POST' });
      const processData = processRes.ok ? await processRes.json() : [];
      const count = Array.isArray(processData) ? processData.length : 0;
      await fetchMeetings();
      setToastMessage(count ? `Synced ${count} email(s)` : 'No new unread meeting emails');
    } catch (error) {
      setToastMessage('Sync failed. Check backend.');
    } finally {
      setSyncing(false);
    }
  };

  const meetingStats = useMemo(() => {
    let free = 0;
    let busy = 0;
    let unknown = 0;

    processedMeetings.forEach((item) => {
      const status = item?.meeting_status;
      if (!status || !status.checked) {
        unknown += 1;
      } else if (status.available === true) {
        free += 1;
      } else if (status.available === false) {
        busy += 1;
      } else {
        unknown += 1;
      }
    });

    return { free, busy, unknown, total: processedMeetings.length };
  }, [processedMeetings]);

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="content-area page-content">
        <section className="small-hero glass-card">
          <h1>Calendar Intelligence</h1>
          <p>Real-time meeting checks, booked slots, and upcoming calendar events.</p>
        </section>

        <section className="glass-card search-card">
          <div className="filter-pills">
            <span className="filter-pill filter-pill-active">Total: {meetingStats.total}</span>
            <span className="filter-pill">Free: {meetingStats.free}</span>
            <span className="filter-pill">Busy: {meetingStats.busy}</span>
            <span className="filter-pill">Unparsed: {meetingStats.unknown}</span>
            <button type="button" className="filter-pill" onClick={syncNow} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Sync Meetings Now'}
            </button>
          </div>
        </section>

        {calendarError && (
          <div className="offline-banner" style={{ marginBottom: 16 }}>
            <span className="material-symbols-outlined">error</span>
            <span>{calendarError}</span>
          </div>
        )}

        <section className="glass-card table-card" style={{ marginBottom: 16 }}>
          <div className="stream-header">
            <div>
              <h2>Processed Meeting Requests</h2>
              <p>From MailMind history with free/busy checks and booking status.</p>
            </div>
          </div>

          <div className="table-wrap">
            <table className="emails-table">
              <thead>
                <tr>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Slot</th>
                  <th>Availability</th>
                  <th>Action</th>
                  <th>Booked Event</th>
                  <th>Processed At</th>
                </tr>
              </thead>
              <tbody>
                {loading &&
                  Array.from({ length: 4 }).map((_, idx) => (
                    <tr key={`loading-${idx}`} className="row-loading">
                      <td colSpan={7}>
                        <div className="skeleton-line shimmer" />
                      </td>
                    </tr>
                  ))}

                {!loading && !processedMeetings.length && (
                  <tr>
                    <td colSpan={7}>
                      <div className="empty-state small">
                        <span className="material-symbols-outlined">event_busy</span>
                        <p>No meeting requests processed yet.</p>
                      </div>
                    </td>
                  </tr>
                )}

                {!loading &&
                  processedMeetings.map((item, idx) => {
                    const sender = parseSender(item.sender || '');
                    const meeting = item.meeting_status || {};
                    const slotText = meeting.display || meeting.reason || '—';
                    const availabilityClass =
                      meeting.available === true
                        ? 'badge-action-green'
                        : meeting.available === false
                        ? 'badge-action-red'
                        : 'badge-action-yellow';
                    const availabilityText =
                      meeting.available === true ? 'FREE' : meeting.available === false ? 'BUSY' : 'UNKNOWN';

                    const eventLink = item?.calendar_event?.html_link;

                    return (
                      <tr key={`${item.id || idx}-${idx}`}>
                        <td>
                          <div className="sender-cell">
                            <div className="avatar-circle">{(sender.name || 'M').slice(0, 2).toUpperCase()}</div>
                            <div>
                              <strong>{sender.name}</strong>
                              <small>{sender.email || '—'}</small>
                            </div>
                          </div>
                        </td>
                        <td>{item.subject || 'No subject'}</td>
                        <td title={slotText}>{String(slotText).slice(0, 45)}</td>
                        <td>
                          <span className={`badge ${availabilityClass}`}>{availabilityText}</span>
                        </td>
                        <td>
                          <span className="badge badge-intent-blue">{(item.action || '—').toUpperCase()}</span>
                        </td>
                        <td>
                          {eventLink ? (
                            <a href={eventLink} target="_blank" rel="noreferrer" className="view-all-btn">
                              Open Event
                            </a>
                          ) : (
                            <small>Not booked</small>
                          )}
                        </td>
                        <td>
                          <small>{formatDateTime(item.processed_at)}</small>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </section>

        <section className="glass-card table-card">
          <div className="stream-header">
            <div>
              <h2>Upcoming Google Calendar Events</h2>
              <p>Live events from your primary calendar.</p>
            </div>
          </div>

          <div className="table-wrap">
            <table className="emails-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Attendees</th>
                  <th>Link</th>
                </tr>
              </thead>
              <tbody>
                {!loading && !upcomingEvents.length && (
                  <tr>
                    <td colSpan={5}>
                      <div className="empty-state small">
                        <span className="material-symbols-outlined">event_available</span>
                        <p>No upcoming events found.</p>
                      </div>
                    </td>
                  </tr>
                )}

                {upcomingEvents.map((event, idx) => (
                  <tr key={`${event.event_id || idx}-${idx}`}>
                    <td>{event.summary || '(No title)'}</td>
                    <td><small>{formatDateTime(event.start)}</small></td>
                    <td><small>{formatDateTime(event.end)}</small></td>
                    <td><small>{(event.attendees || []).slice(0, 3).join(', ') || '—'}</small></td>
                    <td>
                      {event.html_link ? (
                        <a href={event.html_link} target="_blank" rel="noreferrer" className="view-all-btn">
                          Open
                        </a>
                      ) : (
                        <small>—</small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <BottomNav />
      {toastMessage && <Toast message={toastMessage} onClose={() => setToastMessage('')} />}
    </div>
  );
}

export default Calendar;
