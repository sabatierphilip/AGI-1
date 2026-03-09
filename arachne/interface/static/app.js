const chatLog = document.getElementById('chat-log');
const ruleList = document.getElementById('rule-list');
const typing = document.getElementById('typing');
const conn = document.getElementById('connection');
let lastIlpEvents = 0;

function nowStamp() { return new Date().toLocaleTimeString(); }

function addMessage(text, trace, role='system') {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const traceHTML = role === 'system' ? `<span class="trace-badge">[trace]</span><div class="trace">${trace || 'none'}</div>` : '';
  div.innerHTML = `<div>${text}</div>${traceHTML}<span class="timestamp">${nowStamp()}</span>`;
  if (role === 'system') {
    div.querySelector('.trace-badge').onclick = () => {
      const t = div.querySelector('.trace');
      t.style.display = t.style.display === 'block' ? 'none' : 'block';
    };
  }
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function refreshState() {
  try {
    const res = await fetch('/api/state');
    const state = await res.json();
    conn.innerHTML = `<span class="conn-dot" style="background:#22c55e"></span>CONNECTED`;
    document.getElementById('rules-loaded').textContent = state.rule_count;
    document.getElementById('ilp-events').textContent = state.ilp_events;
    document.getElementById('sources-active').textContent = state.sources_active;
    const watchdog = document.getElementById('watchdog');
    watchdog.textContent = `${state.watchdog_seconds}s`;
    watchdog.className = state.watchdog_seconds < 1800 ? 'warn' : '';
    document.getElementById('rule-header').innerHTML = `LIVE RULE BASE (${state.rule_count} rules) <span class="dot pulse"></span>`;

    if (state.ilp_events > lastIlpEvents) {
      document.getElementById('ilp-events').style.animation = 'flashBlue .4s ease';
      setTimeout(() => document.getElementById('ilp-events').style.animation = '', 400);
    }
    lastIlpEvents = state.ilp_events;

    ruleList.innerHTML = '';
    (state.rules || []).forEach((r, idx) => {
      const li = document.createElement('li');
      let cls = r.confidence >= 0.75 ? 'high' : (r.confidence < 0.6 ? 'low' : 'mid');
      const name = r.name.length > 35 ? `${r.name.slice(0, 35)}…` : r.name;
      li.className = `rule-item ${idx < state.new_rule_flash ? 'flash' : ''}`;
      li.innerHTML = `${name}<span class="badge ${cls}">${r.confidence}</span>`;
      ruleList.appendChild(li);
    });

    const inductionLog = document.getElementById('induction-log');
    inductionLog.innerHTML = (state.induction_log || []).map(e => `${e.ts} | ${e.signature} | support=${e.support} | ${e.accepted ? 'accepted' : 'rejected'}`).join('<br>');
  } catch {
    conn.innerHTML = `<span class="conn-dot" style="background:#ef4444"></span>OFFLINE`;
  }
}

document.getElementById('send').onclick = async () => {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;
  addMessage(message, 'user', 'user');
  input.value = '';
  typing.classList.remove('hidden');
  const res = await fetch('/api/chat', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message})
  });
  const data = await res.json();
  typing.classList.add('hidden');
  (data.messages || []).forEach(m => addMessage(m.message, m.trace));
  await refreshState();
};

document.getElementById('chat-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('send').click();
});

setInterval(refreshState, 2000);
refreshState();
