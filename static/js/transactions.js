// Transactions Monitoring

// Global variables
let selectedTransactionsNode = null;
let transactionsData = null;

// Initialize transactions tab
function initTransactionsTab() {
    // Populate node selection
    populateTransactionsNodeSelect();
    
    // Add event listeners
    document.getElementById('transactions-node-select').addEventListener('change', function() {
        selectedTransactionsNode = this.value;
        fetchTransactions();
    });
    
    document.getElementById('transactions-limit').addEventListener('change', function() {
        if (selectedTransactionsNode) {
            fetchTransactions();
        }
    });
    
    document.getElementById('refresh-transactions').addEventListener('click', function() {
        if (selectedTransactionsNode) {
            fetchTransactions();
        } else {
            showTransactionsStatus('Please select a node first', 'warning');
        }
    });
    
    // Add event listener for tab switch to refresh data
    document.getElementById('transactions-tab').addEventListener('shown.bs.tab', function() {
        if (selectedTransactionsNode) {
            fetchTransactions();
        }
    });
    
    // Add event listener for processes tab
    document.getElementById('processes-tab').addEventListener('shown.bs.tab', function() {
        if (selectedTransactionsNode) {
            fetchProcesses();
        }
    });
    
    // Note: refresh-processes button not present in HTML
}

// Populate node selection dropdown
function populateTransactionsNodeSelect() {
    const nodeSelect = document.getElementById('transactions-node-select');
    nodeSelect.innerHTML = '';
    
    // Check if nodes data is available
    if (window.nodesData && window.nodesData.length > 0) {
        // No default option - directly show nodes
        
        // Add option for each node
        for (let i = 0; i < window.nodesData.length; i++) {
            const node = window.nodesData[i];
            const option = document.createElement('option');
            option.value = node.host;
            option.textContent = `${node.name} (${node.host})`;
            if (i === 0) {
                option.selected = true;
            }
            nodeSelect.appendChild(option);
        }
        
        // Automatically select the first node
        if (window.nodesData.length > 0) {
            nodeSelect.value = window.nodesData[0].host;
            selectedTransactionsNode = window.nodesData[0].host;
            fetchTransactions();
        }
    } else {
        // Fallback: Load nodes from API
        fetch('/api/nodes')
            .then(response => response.json())
            .then(data => {
                if (data.ok && data.nodes) {
                    window.nodesData = data.nodes;
                    // Recursively call to populate with loaded data
                    populateTransactionsNodeSelect();
                } else {
                    showTransactionsStatus('Failed to load nodes: ' + (data.error || 'Unknown error'), 'danger');
                }
            })
            .catch(error => {
                showTransactionsStatus('Failed to load nodes: ' + error, 'danger');
            });
    }
}

// Fetch transactions data
function fetchTransactions() {
    if (!selectedTransactionsNode) return;
    
    const limit = document.getElementById('transactions-limit').value || '50';
    
    // Show loading status
    document.getElementById('transactions-tbody').innerHTML = '<tr><td colspan="5" class="text-center">Loading transactions...</td></tr>';
    document.getElementById('locks-tbody').innerHTML = '<tr><td colspan="5" class="text-center">Loading locks...</td></tr>';
    
    fetch(`/api/transactions?host=${encodeURIComponent(selectedTransactionsNode)}&limit=${limit}`)
        .then(response => response.json())
        .then(data => {
            if (data.ok) {
                transactionsData = data;
                renderTransactions(data.transactions);
                renderLocks(data.locks);
                hideTransactionsStatus();
            } else {
                showTransactionsStatus('Failed to load transactions: ' + (data.error || 'Unknown error'), 'danger');
                document.getElementById('transactions-tbody').innerHTML = '<tr><td colspan="5" class="text-center">Failed to load transactions</td></tr>';
                document.getElementById('locks-tbody').innerHTML = '<tr><td colspan="5" class="text-center">Failed to load locks</td></tr>';
            }
        })
        .catch(error => {
            showTransactionsStatus('Failed to load transactions: ' + error.message, 'danger');
            document.getElementById('transactions-tbody').innerHTML = '<tr><td colspan="5" class="text-center">Failed to load transactions</td></tr>';
            document.getElementById('locks-tbody').innerHTML = '<tr><td colspan="5" class="text-center">Failed to load locks</td></tr>';
        });
}

// Fetch processes data
function fetchProcesses() {
    if (!selectedTransactionsNode) return;
    
    // Show loading status
    document.getElementById('processes-tbody').innerHTML = '<tr><td colspan="8" class="text-center">Loading processes...</td></tr>';
    
    fetch(`/api/process_list?host=${encodeURIComponent(selectedTransactionsNode)}`)
        .then(response => response.json())
        .then(data => {
            if (data.ok) {
                renderProcesses(data.processes);
                hideTransactionsStatus();
            } else {
                showTransactionsStatus('Failed to load processes: ' + (data.error || 'Unknown error'), 'danger');
                document.getElementById('processes-tbody').innerHTML = '<tr><td colspan="8" class="text-center">Failed to load processes</td></tr>';
            }
        })
        .catch(error => {
            showTransactionsStatus('Failed to load processes: ' + error.message, 'danger');
            document.getElementById('processes-tbody').innerHTML = '<tr><td colspan="8" class="text-center">Failed to load processes</td></tr>';
        });
}

// Render transactions table
function renderTransactions(transactions) {
    const tbody = document.getElementById('transactions-tbody');
    tbody.innerHTML = '';
    
    if (!transactions || transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No active transactions</td></tr>';
        return;
    }
    
    transactions.forEach(trx => {
        // Determine state class
        let stateClass = 'transaction-state-active';
        if (trx.trx_wait_started) {
            stateClass = 'transaction-state-waiting';
        }
        
        // Format query for display
        const query = trx.trx_query || 'No query';
        const shortQuery = query.length > 100 ? query.substring(0, 100) + '...' : query;
        
        // Create row
        const row = `
            <tr>
                <td>${trx.trx_id}</td>
                <td class="${stateClass}">${trx.trx_state}</td>
                <td>${formatDate(trx.trx_started)}</td>
                <td>${trx.trx_mysql_thread_id}</td>
                <td title="${escapeHtml(query)}">${escapeHtml(shortQuery)}</td>
            </tr>
        `;
        
        tbody.innerHTML += row;
    });
}

// Render locks table
function renderLocks(locks) {
    const tbody = document.getElementById('locks-tbody');
    tbody.innerHTML = '';
    
    if (!locks || locks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No active locks</td></tr>';
        return;
    }
    
    locks.forEach(lock => {
        // Create row
        const row = `
            <tr>
                <td>${lock.lock_id}</td>
                <td>${lock.lock_trx_id}</td>
                <td>${lock.lock_mode}</td>
                <td>${lock.lock_type}</td>
                <td>${lock.lock_table}</td>
            </tr>
        `;
        
        tbody.innerHTML += row;
    });
}

// Render processes table
function renderProcesses(processes) {
    const tbody = document.getElementById('processes-tbody');
    tbody.innerHTML = '';
    
    if (!processes || processes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">No active processes</td></tr>';
        return;
    }
    
    processes.forEach(process => {
        // Determine time class
        let timeClass = 'transaction-time-short';
        if (process.TIME > 60) {
            timeClass = 'transaction-time-medium';
        }
        if (process.TIME > 300) {
            timeClass = 'transaction-time-long';
        }
        
        // Format query for display
        const info = process.INFO || 'No query';
        const shortInfo = info.length > 100 ? info.substring(0, 100) + '...' : info;
        
        // Create row with kill button for non-system processes
        const killButton = process.COMMAND !== 'Daemon' ? 
            `<button class="btn btn-sm btn-danger kill-process" data-process-id="${process.ID}">Kill</button>` : 
            '';
        
        const row = `
            <tr>
                <td>${process.ID}</td>
                <td>${process.USER}</td>
                <td>${process.HOST}</td>
                <td>${process.DB || '-'}</td>
                <td>${process.COMMAND}</td>
                <td class="${timeClass}">${formatTime(process.TIME)}</td>
                <td>${process.STATE || '-'}</td>
                <td title="${escapeHtml(info)}">${escapeHtml(shortInfo)}</td>
                <td>${killButton}</td>
            </tr>
        `;
        
        tbody.innerHTML += row;
    });
    
    // Add event listeners for kill buttons
    document.querySelectorAll('.kill-process').forEach(button => {
        button.addEventListener('click', function() {
            const processId = this.getAttribute('data-process-id');
            killProcess(processId);
        });
    });
}

// Kill a process
function killProcess(processId) {
    if (!confirm(`Are you sure you want to kill process ${processId}?`)) {
        return;
    }
    
    fetch('/api/kill_process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            host: selectedTransactionsNode,
            process_id: processId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.ok) {
            showTransactionsStatus(`Process ${processId} killed successfully`, 'success');
            // Refresh processes list
            fetchProcesses();
        } else {
            showTransactionsStatus('Failed to kill process: ' + (data.error || 'Unknown error'), 'danger');
        }
    })
    .catch(error => {
        showTransactionsStatus('Failed to kill process: ' + error.message, 'danger');
    });
}

// Show status message
function showTransactionsStatus(message, type) {
    const status = document.querySelector('.transactions-status');
    status.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-warning', 'alert-danger');
    status.classList.add(`alert-${type}`);
    document.getElementById('transactions-status-text').textContent = message;
    status.style.display = 'block';
}

// Hide status message
function hideTransactionsStatus() {
    document.querySelector('.transactions-status').classList.add('d-none');
}

// Format date for display
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

// Format time in seconds to readable format
function formatTime(seconds) {
    if (seconds < 60) {
        return `${seconds}s`;
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}m ${remainingSeconds}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const remainingMinutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${remainingMinutes}m`;
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    initTransactionsTab();
});