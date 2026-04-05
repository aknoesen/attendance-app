const express = require('express');
const qrcode = require('qrcode');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ─── Configuration ────────────────────────────────────────────────────────────

const COURSE_NAMES = {
  ENG6: 'ENG 006',
  EEC1: 'EEC 001'
};

// ─── In-memory session store ──────────────────────────────────────────────────

const sessions = {};  // code -> session object

// ─── Helpers ──────────────────────────────────────────────────────────────────

function generateCode() {
  // Avoid visually ambiguous chars: 0/O, 1/I/l
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let code = '';
  for (let i = 0; i < 6; i++) code += chars[Math.floor(Math.random() * chars.length)];
  return code;
}

function buildBaseUrl(req) {
  const proto = req.headers['x-forwarded-proto'] || req.protocol;
  const host  = req.headers['x-forwarded-host']  || req.headers.host;
  return `${proto}://${host}`;
}

function buildCsv(session) {
  const lines = ['Login ID,Check-in Time'];
  for (const r of session.attendance) {
    lines.push(`"${r.loginId}","${new Date(r.time).toLocaleString()}"`);
  }
  return lines.join('\n');
}

// ─── Routes ───────────────────────────────────────────────────────────────────

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'teacher.html'));
});

app.get('/api/status', (req, res) => {
  res.json({ ok: true });
});

app.post('/api/session/start', async (req, res) => {
  const { course, topic } = req.body;

  if (!COURSE_NAMES[course]) {
    return res.status(400).json({ error: 'Invalid course.' });
  }

  let code;
  let attempts = 0;
  do {
    code = generateCode();
    attempts++;
  } while (sessions[code] && attempts < 100);

  const baseUrl = buildBaseUrl(req);
  const url = `${baseUrl}/attend/${code}`;

  let qrDataUrl;
  try {
    qrDataUrl = await qrcode.toDataURL(url, { width: 320, margin: 2, color: { dark: '#1a1a2e' } });
  } catch (err) {
    return res.status(500).json({ error: 'Failed to generate QR code' });
  }

  sessions[code] = {
    code,
    course,
    topic: topic || '',
    startTime: new Date().toISOString(),
    url,
    active: true,
    attendance: []
  };

  console.log(`Session started: ${code} | ${COURSE_NAMES[course]} | "${topic || 'no topic'}" | ${url}`);

  res.json({ code, url, qrDataUrl });
});

app.get('/api/session/:code', (req, res) => {
  const session = sessions[req.params.code];
  if (!session) return res.status(404).json({ error: 'Session not found' });
  res.json({
    code:       session.code,
    course:     session.course,
    courseName: COURSE_NAMES[session.course],
    topic:      session.topic,
    startTime:  session.startTime,
    active:     session.active,
    count:      session.attendance.length,
    attendance: session.attendance
  });
});

app.post('/api/session/:code/save', (req, res) => {
  const session = sessions[req.params.code];
  if (!session) return res.status(404).json({ error: 'Session not found' });

  const dateStr  = new Date().toISOString().split('T')[0];
  const filename = `${session.course}_${dateStr}_${session.code}.csv`;
  const csv      = buildCsv(session);

  console.log(`Saved (download): ${filename} | ${session.attendance.length} check-ins`);

  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  res.send(csv);
});

app.post('/api/session/:code/end', (req, res) => {
  const session = sessions[req.params.code];
  if (!session) return res.status(404).json({ error: 'Session not found' });

  session.active  = false;
  session.endTime = new Date().toISOString();

  const dateStr  = new Date().toISOString().split('T')[0];
  const filename = `${session.course}_${dateStr}_${session.code}.csv`;
  const csv      = buildCsv(session);

  console.log(`Session ended: ${session.code} | ${session.attendance.length} check-ins`);

  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  res.send(csv);
});

// Student check-in page
app.get('/attend/:code', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'student.html'));
});

// Student submit attendance
app.post('/api/attend/:code', (req, res) => {
  const { code } = req.params;
  const session  = sessions[code];

  if (!session) {
    return res.status(404).json({ error: 'Session not found. Scan the QR code again or check the code.' });
  }
  if (!session.active) {
    return res.status(410).json({ error: 'This session has ended. Check with your instructor.' });
  }

  const input = req.body.loginId?.trim().toLowerCase();
  if (!input) {
    return res.status(400).json({ error: 'Please enter your login ID.' });
  }

  // Check for duplicate
  const existing = session.attendance.find(a => a.loginId === input);
  if (existing) {
    return res.status(200).json({ already: true, loginId: input, time: existing.time });
  }

  const record = { loginId: input, time: new Date().toISOString() };
  session.attendance.push(record);

  console.log(`  ✓ ${input} — ${COURSE_NAMES[session.course]}`);

  res.json({ success: true, loginId: input, count: session.attendance.length });
});

// ─── Start ────────────────────────────────────────────────────────────────────

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Attendance App running on port ${PORT}`);
});
