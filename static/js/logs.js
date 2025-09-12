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
            
            // Set the galera-error.log path directly
            if (data.logs.length > 0) {
                selectedLogPath = data.logs[0].path;
                fetchServerLogs();
            } else {
                document.getElementById('logs-content').textContent = 'galera-error.log file not found';
            }
        })
        .catch(error => {
            console.error('Error fetching available logs:', error);
            document.getElementById('logs-content').textContent = 'Error loading galera-error.log';
        });
}

// Fetch log file content
function fetchServerLogs() {
    const logPath = selectedLogPath;
    const lines = document.getElementById('log-lines').value;
    
    if (!logPath) {
        document.getElementById('logs-content').textContent = 'galera-error.log not available';
        return;
    }
    
    document.getElementById('logs-content').textContent = 'Loading galera-error.log...';
    
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
    
    // Number of lines change event
    document.getElementById('log-lines').addEventListener('change', fetchServerLogs);
    
    // رویداد کلیک دکمه رفرش
    document.getElementById('refresh-logs').addEventListener('click', fetchServerLogs);
    
    // رویداد نمایش تب لاگ‌ها
    document.getElementById('logs-tab').addEventListener('shown.bs.tab', function() {
        fetchServerLogs();
    });
});