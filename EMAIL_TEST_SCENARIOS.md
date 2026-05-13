# MailMind Email Test Scenarios

This file gives ready-to-send Gmail examples and what you should expect in MailMind.

## Quick rules used by the app

- Inbox source: **Gmail `INBOX + UNREAD` only**
- Spam action:
  - If spam model says spam, status = `spam`
- Intent action (for non-spam):
  - confidence >= 85 → `auto_send`
  - 60 <= confidence < 85 → `flag_review`
  - confidence < 60 → `escalate_human`
- Sentiment labels:
  - compound >= 0.05 → `positive`
  - compound <= -0.05 → `negative`
  - else → `neutral`

---

## How to run each scenario

1. Send test email from another account to the connected Gmail account.
2. Do **not** open the incoming message in Gmail before processing.
3. In MailMind UI, click **Sync Inbox Now** on `Emails` page (or wait on Dashboard poll).
4. Check `Dashboard` stream and `Emails` table.

---

## Scenarios (copy-paste templates)

> Note: ML confidence can vary. Expected values are best-case targets.

### 1) Meeting request (should often auto-send)

**Subject:** Meeting tomorrow for roadmap

**Body:**
Hi, can we schedule a meeting tomorrow at 10:30 AM for 30 minutes to review the Q2 roadmap and deliverables?

**Expected:**
- Intent: `meeting_request`
- Sentiment: usually `neutral`
- Calendar check: slot should be checked in Google Calendar
- Action: often `auto_send` if confidence high and slot is free
- Reply: generated

---

### 2) Complaint (negative tone)

**Subject:** Unhappy with delayed delivery

**Body:**
I am very disappointed. My order is delayed again and support has not resolved this issue.

**Expected:**
- Intent: `complaint`
- Sentiment: `negative`
- Action: usually `flag_review` or `escalate_human`
- Reply: generated (unless detected spam)

---

### 3) Product inquiry

**Subject:** Pricing details for enterprise plan

**Body:**
Could you share pricing, onboarding steps, and support SLA details for your enterprise plan?

**Expected:**
- Intent: `inquiry`
- Sentiment: `neutral`
- Action: often `flag_review` or `auto_send`

---

### 4) Follow-up reminder

**Subject:** Following up on last email

**Body:**
Just following up on my previous email regarding contract approval. Any update?

**Expected:**
- Intent: `follow_up`
- Sentiment: `neutral`
- Action: often `flag_review`

---

### 5) Feedback (positive)

**Subject:** Great experience with latest release

**Body:**
Great work team! The latest release is smooth, fast, and really improved our workflow.

**Expected:**
- Intent: `feedback`
- Sentiment: `positive`
- Action: often `flag_review` or `auto_send`

---

### 6) Urgent incident

**Subject:** Urgent: payment API down

**Body:**
Urgent: production payment API is failing for all users. Need immediate assistance.

**Expected:**
- Intent: `urgent`
- Sentiment: usually `negative` or `neutral`
- Action: often `escalate_human` or `flag_review`

---

### 7) General informational

**Subject:** Monthly report attached

**Body:**
Please find attached the monthly operations report for your reference. No immediate action required.

**Expected:**
- Intent: `general`
- Sentiment: `neutral`
- Action: often `flag_review`

---

### 8) Likely spam/phishing style

**Subject:** Congratulations! Claim reward now

**Body:**
You won an exclusive gift card. Click this link immediately to claim your reward.

**Expected:**
- Status: likely `spam`
- Spam badge: `SPAM`
- Action workflow: skipped (non-spam pipeline won’t run)

---

## Advanced checklist for each processed mail

In `Emails` page row, verify:
- Sender + Subject shown
- Spam badge + confidence shown
- Sentiment shown (emoji + label)
- Intent badge shown
- Confidence bar shown
- Action shown (`auto_send` / `flag_review` / `escalate_human`)
- Clicking row opens generated reply modal (when reply exists)

---

## If a scenario does not appear

- Message is not unread anymore
- Message not in Inbox (landed in spam/promotions)
- OAuth connected to another Gmail account
- Backend not running on `http://localhost:8000`
- No new unread messages to process
