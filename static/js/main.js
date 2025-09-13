function formatMetricValue(value, type = 'normal') {
  if (value === null || value === undefined) return '-';
  if (type === 'size') return value;
  if (type === 'memory') {
    const bytes = parseInt(value);
    if (isNaN(bytes)) return value;
    const gb = bytes / (1024 * 1024 * 1024);
    return gb.toFixed(2) + ' GB';
  }
  if (type === 'number') {
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    if (type === 'flow_control_paused') return num.toFixed(6);
    return num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 3 });
  }
  return value;
}

function getStatusClass(value, thresholds = {}) {
  if (!value) return '';
  if (value === 'true' || value === 'false') return value;
  const numValue = parseFloat(value);
  if (isNaN(numValue)) return '';
  if (thresholds.danger && numValue >= thresholds.danger) return 'danger';
  if (thresholds.warning && numValue >= thresholds.warning) return 'warning';
  return '';
}

function safeId(text) { return String(text || '').replace(/[^a-zA-Z0-9_-]/g, '_'); }

function createNodeRow(nodeData) {
  const status = nodeData.status || {};
  const weight = nodeData.weight || status.haproxy_weight || 1;
  return `
    <div class="node-row">
      <div class="d-flex flex-column">
        <div class="instance-info">
          <h5 class="status-up">${nodeData.host} <span class="status-up">UP</span></h5>
          <div>OSU: ${status.wsrep_cluster_status || '-'}</div>
          <div class="version-tag">Ver: ${status.wsrep_provider_version || '-'}</div>
          <div>Current: ${status.haproxy_current || '0'}</div>
          <div>Weight: <span id="weight-${safeId(nodeData.host)}">${weight}</span></div>
          <div class="mt-2 d-flex gap-2 flex-wrap">
            <button class="btn btn-sm btn-outline-success" onclick="hapEnable('${nodeData.host}')">Enable</button>
            <button class="btn btn-sm btn-outline-danger" onclick="hapDisable('${nodeData.host}')">Disable</button>
            <button class="btn btn-sm btn-outline-info" onclick="showWeightModal('${nodeData.host}', ${weight})">Set Weight</button>
          </div>
        </div>
        <div class="cert-fail-info">
          <span class="cert-fail-label">certFail:</span>
          <span class="cert-fail-value">${formatMetricValue(status.wsrep_local_cert_failures, 'number')}</span>
        </div>
      </div>
      <div class="metrics-container">
        <div class="metric-group">
          <div class="metric-row">
            <span class="metric-label">wsrep_local_send_queue:</span>
            <span class="metric-value ${getStatusClass(status.wsrep_local_send_queue, { warning: 10 })}">${formatMetricValue(status.wsrep_local_send_queue, 'number')}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">wsrep_local_recv_queue:</span>
            <span class="metric-value ${getStatusClass(status.wsrep_local_recv_queue, { warning: 10 })}">${formatMetricValue(status.wsrep_local_recv_queue, 'number')}</span>
          </div>
          <div class="metric-row"><span class="metric-label">wsrep_cert_deps_distance:</span><span class="metric-value">${formatMetricValue(status.wsrep_cert_deps_distance, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_last_committed:</span><span class="metric-value">${formatMetricValue(status.wsrep_last_committed, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_thread_count:</span><span class="metric-value">${formatMetricValue(status.wsrep_thread_count, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_applier_thread_count:</span><span class="metric-value">${formatMetricValue(status.wsrep_applier_thread_count, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_rollbacker_thread_count:</span><span class="metric-value">${formatMetricValue(status.wsrep_rollbacker_thread_count, 'number')}</span></div>
        </div>
        <div class="metric-group">
          <div class="metric-row"><span class="metric-label">wsrep_flow_control_sent:</span><span class="metric-value">${formatMetricValue(status.wsrep_flow_control_sent, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_flow_control_recv:</span><span class="metric-value">${formatMetricValue(status.wsrep_flow_control_recv, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_flow_control_paused:</span><span class="metric-value">${formatMetricValue(status.wsrep_flow_control_paused, 'flow_control_paused')}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_flow_control_active:</span><span class="metric-value ${status.wsrep_flow_control_active === 'true' ? 'true' : 'false'}">${status.wsrep_flow_control_active}</span></div>
          <div class="metric-row"><span class="metric-label">gcache.page_size:</span><span class="metric-value">${formatMetricValue(status['gcache.page_size'], 'size')}</span></div>
          <div class="metric-row"><span class="metric-label">gcache.size:</span><span class="metric-value">${formatMetricValue(status['gcache.size'], 'size')}</span></div>
          <div class="metric-row"><span class="metric-label">gcs.fc_limit:</span><span class="metric-value">${formatMetricValue(status['gcs.fc_limit'], 'number')}</span></div>
        </div>
        <div class="metric-group">
          <div class="metric-row"><span class="metric-label">Queries/sec:</span><span class="metric-value">${formatMetricValue(status.queries_per_second, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">Writes/sec:</span><span class="metric-value">${formatMetricValue(status.writes_per_second, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">Reads/sec:</span><span class="metric-value">${formatMetricValue(status.reads_per_second, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">Lock Tables:</span><span class="metric-value">${formatMetricValue(status.Com_lock_tables, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_local_state_comment:</span><span class="metric-value metric-value-wrap">${formatMetricValue(status.wsrep_local_state_comment)}</span></div>
          <div class="metric-row"><span class="metric-label">wsrep_cluster_status:</span><span class="metric-value">${formatMetricValue(status.wsrep_cluster_status)}</span></div>
        </div>
        <div class="metric-group">
          <div class="metric-row"><span class="metric-label">Running Threads:</span><span class="metric-value">${formatMetricValue(status.Threads_running, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">Memory Used:</span><span class="metric-value">${formatMetricValue(status.Memory_used, 'memory')}</span></div>
          <div class="metric-row"><span class="metric-label">Slave Connections:</span><span class="metric-value">${formatMetricValue(status.Slave_connections, 'number')}</span></div>
          <div class="metric-row"><span class="metric-label">Slaves Connected:</span><span class="metric-value">${formatMetricValue(status.Slaves_connected, 'number')}</span></div>
        </div>
      </div>
      <div class="overall-status">
        ${status.need_more_slave ? '<div class="status-badge need-slave">NEED_MORE_SLAVE_T</div>' : ''}
      </div>
    </div>
  `;
}

function renderOverview(nodes) {
  const container = document.getElementById('nodes-container');
  if (container) container.innerHTML = nodes.map(node => createNodeRow(node)).join('');
}

function refreshStatus() {
  fetch('/api/status', { cache: 'no-store', headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' } })
    .then(response => response.json())
    .then(data => {
      renderOverview(data.nodes || data);
      updateDelayHistories(data.nodes || data);
      renderDelayCharts(data.nodes || data);
      loadServerWeights(data.haproxy_weights);
      resetCountdown();
    })
    .catch(error => console.error('Error fetching status:', error));
}

// Load nodes data globally for other modules
function loadNodesData() {
  if (!window.nodesData) {
    fetch('/api/nodes')
      .then(response => response.json())
      .then(data => {
        if (data.ok && data.nodes) {
          window.nodesData = data.nodes;
        }
      })
      .catch(error => console.error('Error loading nodes:', error));
  }
}

// Initialize nodes data on page load
document.addEventListener('DOMContentLoaded', loadNodesData);

let countdownInterval;
function resetCountdown() {
  clearInterval(countdownInterval);
  let countdown = 30;
  document.getElementById('refresh-countdown').textContent = countdown;
  countdownInterval = setInterval(() => {
    countdown--;
    document.getElementById('refresh-countdown').textContent = countdown;
    if (countdown <= 0) refreshStatus();
  }, 1000);
}

function confirmRestart() {
  if (!confirm('Are you sure you want to restart HAProxy?')) return;
  fetch('/api/haproxy/restart', { method: 'POST' })
    .then(r => r.json())
    .then(res => {
      if (!res.ok) throw new Error(res.stderr || res.error || 'Failed');
      alert('HAProxy restarted successfully');
      refreshStatus();
    })
    .catch(err => alert('Restart failed: ' + err.message));
}

function hapEnable(host) {
  if (!confirm('Enable traffic to ' + host + ' in HAProxy?')) return;
  fetch('/api/haproxy/server/enable', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ host }) })
    .then(r => r.json())
    .then(res => { if (!res.ok) throw new Error(res.error || res.message || 'Failed'); refreshStatus(); })
    .catch(err => alert('Enable failed: ' + err.message));
}

function hapDisable(host) {
  if (!confirm('Disable traffic to ' + host + ' in HAProxy?')) return;
  fetch('/api/haproxy/server/disable', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ host }) })
    .then(r => r.json())
    .then(res => { if (!res.ok) throw new Error(res.error || res.message || 'Failed'); refreshStatus(); })
    .catch(err => alert('Disable failed: ' + err.message));
}

function showWeightModal(host, currentWeight) {
  $('#serverHost').val(host);
  $('#serverWeight').val(currentWeight);
  $('#weightModal').modal('show');
}

function showAlert(type, message) {
  // Remove any existing alerts
  $('.alert-notification').remove();
  
  // Create new alert
  const alertHtml = `
    <div class="alert alert-${type} alert-dismissible fade show alert-notification" role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>
  `;
  
  // Add to body
  $('body').append(alertHtml);
  
  // Auto-hide after 5 seconds
  setTimeout(() => {
    $('.alert-notification').alert('close');
  }, 5000);
}

function setServerWeight() {
  const host = $('#serverHost').val();
  const weight = parseInt($('#serverWeight').val());
  
  if (isNaN(weight) || weight < 0 || weight > 256) {
    showAlert('danger', 'Weight must be a number between 0 and 256');
    return;
  }
  
  $.ajax({
    url: '/api/haproxy/server/weight',
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      server_name: host,
      weight: weight
    })
  })
  .done(function(data) {
    if (data.success) {
      showAlert('success', `Server ${host} weight set to ${weight}`);
      $('#weightModal').modal('hide');
      // Update the weight display immediately
      $(`#weight-${safeId(host)}`).text(weight);
      refreshStatus();
    } else {
      showAlert('danger', `Failed to set server weight: ${data.error}`);
    }
  })
  .fail(function() {
    showAlert('danger', 'Failed to communicate with server');
  });
}

function loadServerWeights(weights) {
  if (weights) {
    // Update weight displays for each server
    Object.keys(weights).forEach(backend => {
      if (weights[backend]) {
        Object.keys(weights[backend]).forEach(server => {
          const weight = weights[backend][server];
          const weightElement = $(`#weight-${safeId(server)}`);
          if (weightElement.length > 0) {
            weightElement.text(weight);
            // Update the onclick handler with current weight
            const setWeightBtn = weightElement.closest('.instance-info').find('button[onclick*="showWeightModal"]');
            if (setWeightBtn.length > 0) {
              const host = server;
              setWeightBtn.attr('onclick', `showWeightModal('${host}', ${weight})`);
            }
          }
        });
      }
    });
  }
}

window.refreshStatus = refreshStatus;
window.confirmRestart = confirmRestart;
window.hapEnable = hapEnable;
window.hapDisable = hapDisable;
window.showWeightModal = showWeightModal;
window.setServerWeight = setServerWeight;
window.loadServerWeights = loadServerWeights;

