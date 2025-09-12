// Configuration Management

// Global variables
let currentNodeForConfig = null;
let currentCategory = 'all';

// Variable categories mapping
const variableCategories = {
  // Galera specific
  'wsrep_cluster_size': 'galera',
  'wsrep_cluster_status': 'galera',
  'wsrep_connected': 'galera',
  'wsrep_ready': 'galera',
  'wsrep_provider_options': 'galera',
  'wsrep_provider_version': 'galera',
  'wsrep_cluster_name': 'galera',
  'wsrep_node_name': 'galera',
  'wsrep_sst_method': 'galera',
  'wsrep_local_recv_queue': 'galera',
  'wsrep_local_send_queue': 'galera',
  'wsrep_evs_delayed': 'galera',
  'wsrep_flow_control_paused': 'galera',
  'wsrep_flow_control_sent': 'galera',
  'wsrep_flow_control_recv': 'galera',
  'wsrep_cert_deps_distance': 'galera',
  'wsrep_apply_window': 'galera',
  
  // Performance related
  'innodb_buffer_pool_size': 'performance',
  'innodb_log_file_size': 'performance',
  'max_connections': 'performance',
  'thread_cache_size': 'performance',
  'query_cache_size': 'performance',
  'query_cache_type': 'performance',
  'tmp_table_size': 'performance',
  'max_heap_table_size': 'performance',
  
  // Logging related
  'slow_query_log': 'logging',
  'long_query_time': 'logging',
  'log_output': 'logging',
  'general_log': 'logging',
  'general_log_file': 'logging',
  'slow_query_log_file': 'logging',
  
  // Replication related
  'binlog_format': 'replication',
  'sync_binlog': 'replication',
  'expire_logs_days': 'replication',
  
  // InnoDB related
  'innodb_flush_log_at_trx_commit': 'innodb',
  'innodb_flush_method': 'innodb',
  'innodb_file_per_table': 'innodb',
  'innodb_io_capacity': 'innodb'
};

// Editable variables
const editableVariables = [
  'slow_query_log', 'long_query_time', 'max_connections',
  'thread_cache_size', 'query_cache_size', 'query_cache_type',
  'tmp_table_size', 'max_heap_table_size', 'general_log',
  'sync_binlog', 'expire_logs_days', 'innodb_flush_log_at_trx_commit',
  'innodb_io_capacity'
];

// Initialize configuration tab
function initConfig() {
  // Populate node select dropdown
  populateConfigNodeSelect();
  
  // Add event listeners
  document.getElementById('refresh-config').addEventListener('click', fetchConfig);
  document.getElementById('config-node-select').addEventListener('change', function() {
    currentNodeForConfig = this.value;
    fetchConfig();
  });
  document.getElementById('config-category').addEventListener('change', function() {
    currentCategory = this.value;
    filterConfigByCategory();
  });
  
  // Create modal for editing variables
  createEditConfigModal();
  
  // Add tab change listener
  document.getElementById('config-tab').addEventListener('shown.bs.tab', function() {
    if (currentNodeForConfig) {
      fetchConfig();
    }
  });
}

// Populate node select dropdown
function populateConfigNodeSelect() {
  const nodeSelect = document.getElementById('config-node-select');
  nodeSelect.innerHTML = '';
  
  // Check if nodes data is available
  if (window.nodesData && window.nodesData.length > 0) {
    // Add option for each node
    for (const node of window.nodesData) {
      const option = document.createElement('option');
      option.value = node.host;
      option.textContent = `${node.host} (${node.name})`;
      nodeSelect.appendChild(option);
    }
    
    // Set current node if not set
    if (nodeSelect.options.length > 0 && !currentNodeForConfig) {
      currentNodeForConfig = nodeSelect.options[0].value;
    }
  } else {
    // Fallback: Load nodes from API
    fetch('/api/nodes')
      .then(response => response.json())
      .then(data => {
        if (data.ok && data.nodes) {
          window.nodesData = data.nodes;
          // Recursively call to populate with loaded data
          populateConfigNodeSelect();
        } else {
          console.error('Failed to load nodes:', data.error);
        }
      })
      .catch(error => {
        console.error('Error loading nodes:', error);
      });
  }
}

// Fetch configuration from server
function fetchConfig() {
  if (!currentNodeForConfig) return;
  
  const tbody = document.getElementById('config-tbody');
  
  // Show loading
  tbody.innerHTML = '<tr><td colspan="3" class="text-center">Loading configuration...</td></tr>';
  
  // Fetch data from API
  fetch(`/api/get_config?host=${encodeURIComponent(currentNodeForConfig)}`)
    .then(response => response.json())
    .then(data => {
      if (!data.ok) {
        showConfigStatus('error', data.error || 'Error fetching configuration');
        tbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">${data.error || 'Error fetching configuration'}</td></tr>`;
        return;
      }
      
      if (data.config) {
        renderConfig(data.config, data.status);
        hideConfigStatus();
      } else {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center">No configuration data found</td></tr>';
        showConfigStatus('info', 'No configuration data found');
      }
    })
    .catch(error => {
      console.error('Error fetching configuration:', error);
      tbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">Error fetching configuration</td></tr>`;
      showConfigStatus('error', 'Error fetching configuration');
    });
}

// Render configuration table
function renderConfig(config, status) {
  const tbody = document.getElementById('config-tbody');
  tbody.innerHTML = '';
  
  // Combine config and status data
  const allVariables = { ...config, ...status };
  
  // Sort variables by category and name
  const sortedVariables = Object.keys(allVariables).sort((a, b) => {
    const catA = variableCategories[a] || 'other';
    const catB = variableCategories[b] || 'other';
    if (catA !== catB) return catA.localeCompare(catB);
    return a.localeCompare(b);
  });
  
  for (const variable of sortedVariables) {
    const value = allVariables[variable];
    const category = variableCategories[variable] || 'other';
    
    // Skip if filtering by category and not matching
    if (currentCategory !== 'all' && category !== currentCategory) continue;
    
    const row = document.createElement('tr');
    
    // Variable name with category badge
    const nameCell = document.createElement('td');
    nameCell.innerHTML = `
      <span class="config-variable">${variable}</span>
      <span class="config-category ${category}">${category}</span>
    `;
    row.appendChild(nameCell);
    
    // Value (editable if allowed)
    const valueCell = document.createElement('td');
    if (editableVariables.includes(variable)) {
      valueCell.innerHTML = `<span class="config-value editable-value" data-variable="${variable}">${value}</span>`;
      valueCell.querySelector('.editable-value').addEventListener('click', function() {
        showEditConfigModal(variable, value);
      });
    } else {
      valueCell.innerHTML = `<span class="config-value">${value}</span>`;
    }
    row.appendChild(valueCell);
    
    // Actions
    const actionsCell = document.createElement('td');
    if (editableVariables.includes(variable)) {
      const editButton = document.createElement('button');
      editButton.className = 'btn btn-sm btn-outline-warning';
      editButton.textContent = 'Edit';
      editButton.addEventListener('click', function() {
        showEditConfigModal(variable, value);
      });
      actionsCell.appendChild(editButton);
    }
    row.appendChild(actionsCell);
    
    tbody.appendChild(row);
  }
}

// Filter configuration by category
function filterConfigByCategory() {
  const rows = document.querySelectorAll('#config-tbody tr');
  
  if (currentCategory === 'all') {
    // Show all rows
    rows.forEach(row => row.style.display = '');
    return;
  }
  
  // Show only rows with matching category
  rows.forEach(row => {
    const categorySpan = row.querySelector('.config-category');
    if (categorySpan && categorySpan.classList.contains(currentCategory)) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

// Show status message
function showConfigStatus(type, message) {
  const statusDiv = document.querySelector('.config-status');
  const statusText = document.getElementById('config-status-text');
  
  statusDiv.classList.remove('d-none', 'alert-info', 'alert-danger', 'alert-warning', 'alert-success');
  
  switch (type) {
    case 'error':
      statusDiv.classList.add('alert-danger');
      break;
    case 'warning':
      statusDiv.classList.add('alert-warning');
      break;
    case 'success':
      statusDiv.classList.add('alert-success');
      break;
    default:
      statusDiv.classList.add('alert-info');
  }
  
  statusText.textContent = message;
  statusDiv.classList.remove('d-none');
}

// Hide status message
function hideConfigStatus() {
  document.querySelector('.config-status').classList.add('d-none');
}

// Create modal for editing configuration
function createEditConfigModal() {
  // Create modal element if it doesn't exist
  if (!document.getElementById('edit-config-modal')) {
    const modalHtml = `
      <div class="modal fade" id="edit-config-modal" tabindex="-1" aria-labelledby="edit-config-modal-label" aria-hidden="true">
        <div class="modal-dialog">
          <div class="modal-content bg-dark text-light">
            <div class="modal-header">
              <h5 class="modal-title" id="edit-config-modal-label">Edit Configuration</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="mb-3">
                <label for="edit-config-variable" class="form-label">Variable:</label>
                <input type="text" class="form-control" id="edit-config-variable" readonly>
              </div>
              <div class="mb-3">
                <label for="edit-config-value" class="form-label">Value:</label>
                <input type="text" class="form-control" id="edit-config-value">
                <small class="text-muted" id="edit-config-help"></small>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-warning" id="confirm-edit-config">Update</button>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Append modal to body
    const modalContainer = document.createElement('div');
    modalContainer.innerHTML = modalHtml;
    document.body.appendChild(modalContainer);
    
    // Add event listener for update button
    document.getElementById('confirm-edit-config').addEventListener('click', updateConfig);
  }
}

// Show modal for editing configuration
function showEditConfigModal(variable, value) {
  document.getElementById('edit-config-variable').value = variable;
  document.getElementById('edit-config-value').value = value;
  
  // Set help text based on variable type
  const helpText = document.getElementById('edit-config-help');
  switch (variable) {
    case 'slow_query_log':
    case 'general_log':
      helpText.textContent = 'Enter 0 to disable or 1 to enable';
      break;
    case 'long_query_time':
      helpText.textContent = 'Enter time in seconds (e.g., 1.0)';
      break;
    case 'max_connections':
      helpText.textContent = 'Enter maximum number of connections';
      break;
    case 'expire_logs_days':
      helpText.textContent = 'Enter number of days to keep binary logs';
      break;
    default:
      helpText.textContent = '';
  }
  
  // Show modal
  const modal = new bootstrap.Modal(document.getElementById('edit-config-modal'));
  modal.show();
}

// Update configuration
function updateConfig() {
  const variable = document.getElementById('edit-config-variable').value;
  const value = document.getElementById('edit-config-value').value;
  
  if (!variable || !value) return;
  
  // Hide modal
  bootstrap.Modal.getInstance(document.getElementById('edit-config-modal')).hide();
  
  // Show loading status
  showConfigStatus('info', `Updating ${variable}...`);
  
  // Call API to update configuration
  fetch('/api/update_config', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      host: currentNodeForConfig,
      variable: variable,
      value: value
    })
  })
    .then(response => response.json())
    .then(data => {
      if (!data.ok) {
        showConfigStatus('error', data.error || `Error updating ${variable}`);
        return;
      }
      
      showConfigStatus('success', `${variable} updated successfully`);
      
      // Update the value in the table
      const valueElement = document.querySelector(`#config-tbody .editable-value[data-variable="${variable}"]`);
      if (valueElement) {
        valueElement.textContent = data.new_value;
      }
    })
    .catch(error => {
      console.error('Error updating configuration:', error);
      showConfigStatus('error', `Error updating ${variable}`);
    });
}

// Initialize on document load
document.addEventListener('DOMContentLoaded', initConfig);

// Expose functions globally
window.fetchConfig = fetchConfig;
window.updateConfig = updateConfig;