const chatLog = document.getElementById('chat-log');
const ruleList = document.getElementById('rule-list');
const typing = document.getElementById('typing');
const conn = document.getElementById('connection');
let lastIlpEvents = 0;
let graphMode = false;

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

async function refreshAnalytics() {
  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();
    const tops = (data.top_predicates || []).map(p => `${p.predicate} (${p.count})`).join(', ');
    document.getElementById('analytics-panel').innerHTML = `
      <div class="stat"><label>TOTAL FACTS</label><strong>${data.total_facts || 0}</strong></div>
      <div class="stat"><label>NARS STORE</label><strong>${data.nars_store_size || 0}</strong></div>
      <div class="stat full"><label>TOP PREDICATES</label><strong>${tops || 'none'}</strong></div>
    `;
  } catch (_) {}
}

function renderGraph(payload) {
  const svg = d3.select('#graph-svg');
  svg.selectAll('*').remove();
  const width = document.getElementById('graph-view').clientWidth || 500;
  const height = 300;
  svg.attr('width', width).attr('height', height);

  const nodes = payload.nodes || [];
  const links = payload.edges || [];
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(70))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width / 2, height / 2));

  const link = svg.append('g').selectAll('line').data(links).enter().append('line')
    .attr('stroke', '#4b5563').attr('stroke-width', 1.2);

  const node = svg.append('g').selectAll('circle').data(nodes).enter().append('circle')
    .attr('r', 5).attr('fill', '#00ff88');

  const label = svg.append('g').selectAll('text').data(nodes).enter().append('text')
    .text(d => d.id).attr('fill', '#e5e7eb').attr('font-size', 10);

  simulation.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('cx', d => d.x).attr('cy', d => d.y);
    label.attr('x', d => d.x + 6).attr('y', d => d.y + 3);
  });
}

async function refreshGraph() {
  if (!graphMode) return;
  const res = await fetch('/api/graph');
  const data = await res.json();
  renderGraph(data);
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
    await refreshAnalytics();
    await refreshGraph();
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

document.getElementById('paste-btn').onclick = () => {
  document.getElementById('paste-area').classList.toggle('hidden');
};

document.getElementById('ingest-cancel').onclick = () => {
  document.getElementById('paste-area').classList.add('hidden');
};

document.getElementById('ingest-submit').onclick = async () => {
  const text = document.getElementById('paste-input').value.trim();
  if (!text) return;
  addMessage('⬇ Ingesting passage...', 'system', 'system');
  document.getElementById('paste-area').classList.add('hidden');
  document.getElementById('paste-input').value = '';

  const res = await fetch('/api/ingest', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text})
  });
  const data = await res.json();
  addMessage(data.message, 'ingest', 'system');
  await refreshState();
};

document.getElementById('graph-tab').onclick = () => {
  graphMode = !graphMode;
  document.getElementById('graph-view').classList.toggle('hidden', !graphMode);
  document.getElementById('rule-list').classList.toggle('hidden', graphMode);
  document.getElementById('graph-tab').textContent = graphMode ? 'Rules' : 'Graph';
  refreshGraph();
};

setInterval(refreshState, 2000);
refreshState();
