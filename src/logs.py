from flask import request, jsonify
import os
import glob
import time

def api_available_logs():
    try:
        # Only look for galera-error.log file
        galera_error_log_path = '/var/log/mariadb/galera-error.log'
        
        available_logs = []
        
        # Check if galera-error.log exists
        if os.path.exists(galera_error_log_path):
            try:
                stat = os.stat(galera_error_log_path)
                available_logs.append({
                    'path': galera_error_log_path,
                    'name': os.path.basename(galera_error_log_path),
                    'size': stat.st_size,
                    'modified': stat.st_mtime
                })
            except Exception:
                pass
        
        return jsonify({
            'ok': True,
            'logs': available_logs
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

def api_server_logs():
    try:
        # Number of log lines to return
        lines = request.args.get('lines', default=100, type=int)
        
        # Log file path
        log_file = request.args.get('file', default=None, type=str)
        
        if not log_file or not os.path.exists(log_file):
            return jsonify({'ok': False, 'error': 'Log file not found'}), 404
        
        # Read the last N lines from the log file
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                # Read all lines and take the last 'lines' number
                all_lines = f.readlines()
                log_lines = all_lines[-lines:] if lines < len(all_lines) else all_lines
                
                # Get file stats
                stat = os.stat(log_file)
                
                return jsonify({
                    'ok': True,
                    'file': log_file,
                    'name': os.path.basename(log_file),
                    'size': stat.st_size,
                    'modified': time.ctime(stat.st_mtime),
                    'lines': log_lines
                })
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500