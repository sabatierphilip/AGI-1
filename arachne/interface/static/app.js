const chatLog = document.getElementById('chat-log');
const ruleList = document.getElementById('rule-list');
const statusBar = document.getElementById('status-bar');

async function refreshState() {
  const res = await fetch('/api/state');
  const state = await res.json();
  statusBar.textContent = `rules=${state.rule_count} | ilp_events=${state.ilp_events} | sources=${state.sources_active} | watchdog=${state.watchdog_seconds}s`;
  ruleList.innerHTML = '';
  (state.rules || []).forEach((r, idx) => {
    const li = document.createElement('li');
    li.className = 'rule-item' + (idx < state.new_rule_flash ? ' new' : '');
    let cls = 'mid';
    if (r.confidence >= 0.75) cls = 'high';
    if (r.confidence < 0.6) cls = 'low';
    li.innerHTML = `${r.name}<span class="badge ${cls}">${r.confidence}</span>`;
    ruleList.appendChild(li);
  });
}

function addMessage(text, trace) {
  const div = document.createElement('div');
  div.className = 'msg';
  div.innerHTML = `<div>${text}</div><div class="trace">trace: ${trace}</div>`;
  div.onclick = () => {
    const t = div.querySelector('.trace');
    t.style.display = t.style.display === 'block' ? 'none' : 'block';
  };
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

document.getElementById('send').onclick = async () => {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;
  addMessage(`> ${message}`, 'user');
  input.value = '';
  const res = await fetch('/api/chat', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message})
  });
  const data = await res.json();
  (data.messages || []).forEach(m => addMessage(m.message + (m.raw ? ` (${m.raw})` : ''), m.trace));
  await refreshState();
};

setInterval(refreshState, 2000);
refreshState();
