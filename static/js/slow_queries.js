// Slow Queries Management

// Global variables
let currentNodeForSlowQueries = null;
let slowQueryThreshold = 1; // Default threshold in seconds

// Initialize slow queries tab
function initSlowQueries() {
  // Populate node select dropdown
  populateSlowQueryNodeSelect();
  
  // Add event listeners
  document.getElementById('refresh-slow-queries').addEventListener('click', fetchSlowQueries);
  document.getElementById('slow-query-node-select').addEventListener('change', function() {
    currentNodeForSlowQueries = this.value;
    fetchSlowQueries();
  });
  
  // Add tab change listener
  document.getElementById('slow-queries-tab').addEventListener('shown.bs.tab', function() {
    if (currentNodeForSlowQueries) {
      fetchSlowQueries();
    }
  });
}

// Populate node select dropdown
function populateSlowQueryNodeSelect() {
  const nodeSelect = document.getElementById('slow-query-node-select');
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
    if (nodeSelect.options.length > 0 && !currentNodeForSlowQueries) {
      currentNodeForSlowQueries = nodeSelect.options[0].value;
    }
  } else {
    // Fallback: Load nodes from API
    fetch('/api/nodes')
      .then(response => response.json())
      .then(data => {
        if (data.ok && data.nodes) {
          window.nodesData = data.nodes;
          // Recursively call to populate with loaded data
          populateSlowQueryNodeSelect();
        } else {
          console.error('Failed to load nodes:', data.error);
        }
      })
      .catch(error => {
        console.error('Error loading nodes:', error);
      });
  }
}

// Fetch slow queries from server
function fetchSlowQueries() {
  if (!currentNodeForSlowQueries) return;
  
  const limit = document.getElementById('slow-query-limit').value;
  const tbody = document.getElementById('slow-queries-tbody');
  
  // Show loading
  tbody.innerHTML = '<tr><td colspan="6" class="text-center">Loading slow queries...</td></tr>';
  
  // Fetch data from API
  fetch(`/api/slow_queries?host=${encodeURIComponent(currentNodeForSlowQueries)}&limit=${limit}`)
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        showSlowQueryStatus('error', data.error);
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">${data.error}</td></tr>`;
        return;
      }
      
      if (data.slow_queries && data.slow_queries.length > 0) {
        renderSlowQueries(data.slow_queries);
        hideSlowQueryStatus();
      } else {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">No slow queries found</td></tr>';
        showSlowQueryStatus('info', 'No slow queries found.');
      }
    })
    .catch(error => {
      console.error('Error fetching slow queries:', error);
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Error fetching slow queries</td></tr>`;
      showSlowQueryStatus('error', 'Error fetching slow queries');
    });
}

// Render slow queries table
function renderSlowQueries(queries) {
  const tbody = document.getElementById('slow-queries-tbody');
  tbody.innerHTML = '';
  
  for (const query of queries) {
    const row = document.createElement('tr');
    
    // Format time
    const timeCell = document.createElement('td');
    timeCell.textContent = query.start_time;
    row.appendChild(timeCell);
    
    // Format query time with color coding
    const queryTimeCell = document.createElement('td');
    queryTimeCell.textContent = query.query_time + 's';
    queryTimeCell.className = 'slow-query-time';
    
    // Color code based on query time
    if (query.query_time < 1) {
      queryTimeCell.classList.add('normal');
    } else if (query.query_time < 5) {
      queryTimeCell.classList.add('warning');
    }
    row.appendChild(queryTimeCell);
    
    // Lock time
    const lockTimeCell = document.createElement('td');
    lockTimeCell.textContent = query.lock_time + 's';
    row.appendChild(lockTimeCell);
    
    // Rows examined/sent
    const rowsCell = document.createElement('td');
    rowsCell.textContent = query.rows_examined;
    row.appendChild(rowsCell);
    
    // Database
    const dbCell = document.createElement('td');
    dbCell.textContent = query.db || '-';
    row.appendChild(dbCell);
    
    // Query with truncation
    const queryCell = document.createElement('td');
    queryCell.className = 'query-cell';
    queryCell.textContent = query.sql_text || '-';
    row.appendChild(queryCell);
    
    tbody.appendChild(row);
  }
}

// Show status message
function showSlowQueryStatus(type, message) {
  const statusDiv = document.querySelector('.slow-queries-status');
  const statusText = document.getElementById('slow-queries-status-text');
  
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
function hideSlowQueryStatus() {
  document.querySelector('.slow-queries-status').classList.add('d-none');
}

// Create modal for enabling slow log


// Initialize on document load
document.addEventListener('DOMContentLoaded', initSlowQueries);

// Expose functions globally
window.fetchSlowQueries = fetchSlowQueries;