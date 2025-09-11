// Server Logs Management
let selectedLogPath = null;

// Fetch available log files
function fetchAvailableLogs() {
    fetch('/api/available_logs')
        .then(response => response.json())
        .then(data => {
            if (!data.ok) {
                console.error('Error fetching available logs:', data.error);
                return;
            }
            
            const logSelect = document.getElementById('log-file-select');
            logSelect.innerHTML = '';
            
            if (data.logs.length === 0) {
                logSelect.innerHTML = '<option value="">No log files found</option>';
                return;
            }
            
            // Add options to select
            data.logs.forEach(log => {
                const option = document.createElement('option');
                option.value = log.path;
                
                // Display filename instead of full path
                const pathParts = log.path.split('/');
                const fileName = pathParts[pathParts.length - 1];
                const dirName = pathParts[pathParts.length - 2];
                
                // Convert size to readable format
                const sizeInKB = Math.round(log.size / 1024);
                let sizeStr = sizeInKB + ' KB';
                if (sizeInKB > 1024) {
                    sizeStr = (sizeInKB / 1024).toFixed(2) + ' MB';
                }
                
                // Convert time to readable format
                const date = new Date(log.modified * 1000);
                const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                
                option.textContent = `${dirName}/${fileName} (${sizeStr}, ${dateStr})`;
                logSelect.appendChild(option);
            });
            
            // Select first option and display its logs
            if (data.logs.length > 0) {
                selectedLogPath = data.logs[0].path;
                fetchServerLogs();
            }
        })
        .catch(error => {
            console.error('Error fetching available logs:', error);
            document.getElementById('log-file-select').innerHTML = '<option value="">Error loading logs</option>';
        });
}

// Fetch log file content
function fetchServerLogs() {
    const logPath = document.getElementById('log-file-select').value || selectedLogPath;
    const lines = document.getElementById('log-lines').value;
    
    if (!logPath) {
        document.getElementById('logs-content').textContent = 'No log file selected';
        return;
    }
    
    selectedLogPath = logPath;
    document.getElementById('logs-content').textContent = 'Loading logs...';
    
    fetch(`/api/server_logs?log_path=${encodeURIComponent(logPath)}&lines=${lines}`)
        .then(response => response.json())
        .then(data => {
            if (!data.ok) {
                document.getElementById('logs-content').textContent = `Error: ${data.error}`;
                return;
            }
            
            const logsContent = document.getElementById('logs-content');
            logsContent.innerHTML = '';
            
            // Display log lines with appropriate coloring
            data.lines.forEach(line => {
                const lineElement = document.createElement('div');
                
                // Color based on log type
                if (line.toLowerCase().includes('error')) {
                    lineElement.className = 'log-error';
                } else if (line.toLowerCase().includes('warning') || line.toLowerCase().includes('warn')) {
                    lineElement.className = 'log-warning';
                } else if (line.toLowerCase().includes('info') || line.toLowerCase().includes('notice')) {
                    lineElement.className = 'log-info';
                }
                
                lineElement.textContent = line;
                logsContent.appendChild(lineElement);
            });
            
            // Scroll to the end of logs
            logsContent.scrollTop = logsContent.scrollHeight;
        })
        .catch(error => {
            console.error('Error fetching server logs:', error);
            document.getElementById('logs-content').textContent = `Error loading logs: ${error.message}`;
        });
}

// Add event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Fetch log files list when page loads
    fetchAvailableLogs();
    
    // Log file change event
    document.getElementById('log-file-select').addEventListener('change', fetchServerLogs);
    
    // Number of lines change event
    document.getElementById('log-lines').addEventListener('change', fetchServerLogs);
    
    // رویداد کلیک دکمه رفرش
    document.getElementById('refresh-logs').addEventListener('click', fetchServerLogs);
    
    // رویداد نمایش تب لاگ‌ها
    document.getElementById('logs-tab').addEventListener('shown.bs.tab', function() {
        fetchServerLogs();
    });
});