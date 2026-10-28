// zero-trace frontend: profile SSE feed + inline SVG topology renderer.

window.startProfileFeed = async function (profileId) {
  const badge = document.getElementById('badge');
  const bar = document.getElementById('bar-fill');
  const error = document.getElementById('error');
  const eventsEl = document.getElementById('events');

  const stages = ['resolve', 'override', 'start', 'ready', 'index', 'capture', 'exercise', 'parse', 'done'];
  let last = null;

  while (true) {
    let data;
    try {
      const res = await fetch(`/api/profiles/${profileId}`);
      data = await res.json();
    } catch (err) {
      await new Promise((r) => setTimeout(r, 2000));
      continue;
    }

    if (badge) {
      badge.className = `badge badge-${data.status}`;
      badge.textContent = data.status;
    }
    if (error) {
      error.hidden = !data.error;
      error.textContent = data.error || '';
    }
    if (bar) {
      const progress = stages.indexOf(data.status === 'done' ? 'done' : data.events.at(-1)?.stage) + 1;
      bar.style.width = stages.length ? `${Math.min(100, (progress / stages.length) * 100 + 20)}%` : '0%';
      if (data.status === 'done') bar.style.width = '100%';
    }
    if (eventsEl && data.events && (!last || JSON.stringify(data.events) !== last)) {
      renderEvents(eventsEl, data.events);
      last = JSON.stringify(data.events);
    }
    if (data.status === 'done' || data.status === 'failed') {
      if (data.status === 'done') bar.style.width = '100%';
      break;
    }
    await new Promise((r) => setTimeout(r, 1500));
  }
};

function renderEvents(el, events) {
  el.innerHTML = '';
  for (const ev of events) {
    const li = document.createElement('li');
    const span = document.createElement('span');
    span.className = 'stage';
    span.textContent = ev.stage;
    li.appendChild(span);
    li.appendChild(document.createTextNode(' ' + ev.msg));
    el.appendChild(li);
  }
  el.scrollTop = el.scrollHeight;
}

// --- inline SVG topology ---
window.renderGraph = async function (profileId) {
  const host = document.getElementById('graph');
  try {
    const res = await fetch(`/api/graph/${profileId}`);
    const { nodes, edges } = await res.json();
    if (!nodes.length) {
      host.innerHTML = '<p class="muted">No edges yet — run a profile first.</p>';
      return;
    }
    host.innerHTML = graphSvg(nodes, edges);
  } catch (err) {
    host.innerHTML = `<p class="error">failed to load graph: ${err}</p>`;
  }
};

function graphSvg(nodes, edges) {
  const W = 720, H = 480, R = 150, CX = W / 2, CY = H / 2;
  const byId = Object.fromEntries(nodes.map((n) => [n.data.id, n.data]));
  const ids = nodes.map((n) => n.data.id);
  const pos = {};
  ids.forEach((id, i) => {
    const a = (i / ids.length) * 2 * Math.PI - Math.PI / 2;
    pos[id] = [CX + R * Math.cos(a), CY + R * Math.sin(a)];
  });

  const edgeEls = edges.map((e) => {
    const d = e.data;
    const [x1, y1] = pos[d.source] || [CX, CY];
    const [x2, y2] = pos[d.target] || [CX, CY];
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    return `
      <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#7dd3fc" stroke-opacity="0.6"/>
      <g transform="translate(${mx} ${my})">
        <rect x="-64" y="-11" width="128" height="22" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
        <text x="0" y="4" text-anchor="middle" font-size="11" fill="#e2e8f0">${d.label} (${d.packets})</text>
      </g>`;
  }).join('');

  const nodeEls = ids.map((id) => {
    const [x, y] = pos[id];
    const d = byId[id];
    const fill = d.external ? '#7f1d1d' : '#155e75';
    return `
      <g transform="translate(${x} ${y})">
        <circle r="26" fill="${fill}" stroke="#38bdf8" stroke-width="2"/>
        <text y="42" text-anchor="middle" font-size="12" fill="#e2e8f0" font-weight="600">${d.label}</text>
      </g>`;
  }).join('');

  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    ${edgeEls}
    ${nodeEls}
  </svg>`;
}