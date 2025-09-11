const delayHistoryByHost = {};
const MAX_POINTS = 1000;

function updateDelayHistories(nodes) {
  const now = Date.now();
  nodes.forEach(node => {
    const host = node.host;
    const status = node.status || {};
    const value = parseFloat(status.wsrep_local_recv_queue) || 0;
    const arr = delayHistoryByHost[host] || (delayHistoryByHost[host] = []);
    arr.push({ t: now, v: value });
    if (arr.length > MAX_POINTS) arr.splice(0, arr.length - MAX_POINTS);
  });
}

function renderDelayCharts(nodes) {
  const chartsContainer = document.getElementById('charts-container');
  if (!chartsContainer) return;
  chartsContainer.innerHTML = nodes.map(node => {
    const hostId = safeId(node.host);
    const arr = delayHistoryByHost[node.host] || [];
    const latest = arr.length ? Math.round(arr[arr.length - 1].v || 0) : 0;
    return `
      <div class="metric-group" style="grid-column: 1 / -1;">
        <div class="group-title">${node.host} — Replication Delay (wsrep_local_recv_queue) — Waiting: ${latest} tx</div>
        <div id="chart-delay-${hostId}" style="height: 180px;"></div>
      </div>
    `;
  }).join('');

  nodes.forEach(node => {
    const host = node.host;
    const arr = delayHistoryByHost[host] || [];
    const x = arr.map(p => new Date(p.t));
    const y = arr.map(p => Math.max(0, Math.round(p.v || 0)));
    const elId = `chart-delay-${safeId(host)}`;
    const el = document.getElementById(elId);
    if (!el) return;

    Plotly.react(el, [
      { x, y, mode: 'lines', line: { color: '#00ff00', width: 2 }, name: 'recv_queue', hovertemplate: '%{y} tx<extra></extra>' }
    ], {
      margin: { l: 40, r: 10, t: 10, b: 24 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      xaxis: { color: '#aaa', gridcolor: '#333', showgrid: true, tickfont: { color: '#aaa', size: 10 }, showspikes: true, spikemode: 'across' },
      yaxis: { color: '#aaa', gridcolor: '#333', zerolinecolor: '#444', tickfont: { color: '#aaa', size: 10 }, rangemode: 'tozero', tickformat: ',d', ticksuffix: ' tx' },
      showlegend: false
    }, { displayModeBar: false, responsive: true });
  });
}

document.addEventListener('shown.bs.tab', function (event) {
  const target = event.target && event.target.getAttribute('data-bs-target');
  if (target === '#charts-pane') {
    const chartsContainer = document.getElementById('charts-container');
    if (!chartsContainer) return;
    const plots = chartsContainer.querySelectorAll('.js-plotly-plot');
    plots.forEach(p => Plotly.Plots.resize(p));
  }
});

window.updateDelayHistories = updateDelayHistories;
window.renderDelayCharts = renderDelayCharts;

