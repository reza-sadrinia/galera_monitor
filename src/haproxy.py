from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import subprocess
from flask import jsonify, request
from src.config_utils import load_config, get_restart_command

def parse_wsrep_provider_options(options_str):
    if not options_str:
        return {}
    result = {}
    pairs = options_str.split(';')
    for pair in pairs:
        if '=' in pair:
            key, value = pair.strip().split('=', 1)
            result[key.strip()] = value.strip()
    return result

def get_haproxy_stats():
    config = load_config()
    haproxy_config = config.get('haproxy', {})
    if not haproxy_config:
        return {}
    try:
        url = f"http://{haproxy_config['host']}:{haproxy_config['stats_port']}{haproxy_config['stats_path']}"
        response = requests.get(url, auth=HTTPBasicAuth(haproxy_config['stats_user'], haproxy_config['stats_password']), timeout=5)
        if response.status_code != 200:
            return {}
        lines = response.text.strip().split('\n')
        headers = lines[0].split(',')
        current_by_server = {}
        nodes = config.get('nodes', [])
        server_mapping = { f"node{i+1}": node['host'] for i, node in enumerate(nodes) }
        backend_name = haproxy_config.get('backend_name', 'galera_cluster_backend')
        for line in lines[1:]:
            fields = line.split(',')
            if len(fields) >= len(headers):
                data = dict(zip(headers, fields))
                if data['# pxname'] == backend_name and data['svname'] not in ['FRONTEND', 'BACKEND']:
                    server_name = data['svname']
                    if server_name in server_mapping:
                        server_ip = server_mapping[server_name]
                        try:
                            current_by_server[server_ip] = int(data.get('scur', 0))
                        except ValueError:
                            pass
        return current_by_server
    except Exception:
        return {}

def get_haproxy_server_states():
    config = load_config()
    haproxy_config = config.get('haproxy', {})
    if not haproxy_config:
        print("Warning: No HAProxy configuration found")
        return {}
    
    # Check for placeholder values
    if (haproxy_config.get('host') == 'haproxy.example.com' or 
        haproxy_config.get('stats_password') in ['your_password', 'password', ''] or
        haproxy_config.get('stats_port') == 'port_number'):
        print("Warning: HAProxy configuration contains placeholder values. Please update config.yaml")
        return {}
    
    try:
        url = f"http://{haproxy_config['host']}:{haproxy_config['stats_port']}{haproxy_config['stats_path']}"
        response = requests.get(url, auth=HTTPBasicAuth(haproxy_config['stats_user'], haproxy_config['stats_password']), timeout=5)
        if response.status_code != 200:
            print(f"Warning: HAProxy stats returned status {response.status_code}")
            return {}
        lines = response.text.strip().split('\n')
        headers = lines[0].split(',')
        result = {}
        nodes = config.get('nodes', [])
        server_mapping = { f"node{i+1}": node['host'] for i, node in enumerate(nodes) }
        backend_name = haproxy_config.get('backend_name', 'galera_cluster_backend')
        for line in lines[1:]:
            fields = line.split(',')
            if len(fields) >= len(headers):
                data = dict(zip(headers, fields))
                if data['# pxname'] == backend_name and data['svname'] not in ['FRONTEND', 'BACKEND']:
                    server_name = data['svname']
                    if server_name in server_mapping:
                        server_ip = server_mapping[server_name]
                        try:
                            cur = int(data.get('scur', 0))
                        except ValueError:
                            cur = 0
                        result[server_ip] = { 'current': cur, 'status': data.get('status', '') }
        return result
    except Exception as e:
        print(f"Warning: HAProxy connection failed: {str(e)}")
        return {}

def get_haproxy_admin_url_and_auth():
    config = load_config()
    haproxy_config = config.get('haproxy', {})
    if not haproxy_config:
        return None, None
    
    # Get admin path from config, fallback to stats_path without ;csv
    admin_path = haproxy_config.get('admin_path')
    if not admin_path:
        stats_path = str(haproxy_config.get('stats_path') or '/stats')
        admin_path = stats_path.replace(';csv', '')
        # If stats_path doesn't have admin interface, try common patterns
        if not any(x in admin_path for x in ['/admin', '?admin', '&admin']):
            if admin_path.endswith('/'):
                admin_path += 'admin'
            else:
                admin_path += '/admin'
    
    url = f"http://{haproxy_config['host']}:{haproxy_config['stats_port']}{admin_path}"
    auth = HTTPBasicAuth(haproxy_config['stats_user'], haproxy_config['stats_password'])
    return url, auth

def get_haproxy_server_weights():
    """Get current weight of all servers in the backend"""
    config = load_config()
    haproxy_config = config.get('haproxy', {})
    if not haproxy_config:
        return {}
    
    try:
        url = f"http://{haproxy_config['host']}:{haproxy_config['stats_port']}{haproxy_config['stats_path']}"
        response = requests.get(url, auth=HTTPBasicAuth(haproxy_config['stats_user'], haproxy_config['stats_password']), timeout=5)
        if response.status_code != 200:
            return {}
        
        lines = response.text.strip().split('\n')
        headers = lines[0].split(',')
        nodes = config.get('nodes', [])
        server_mapping = { f"node{i+1}": node['host'] for i, node in enumerate(nodes) }
        backend_name = haproxy_config.get('backend_name', 'galera_cluster_backend')
        
        result = {backend_name: {}}
        
        for line in lines[1:]:
            fields = line.split(',')
            if len(fields) >= len(headers):
                data = dict(zip(headers, fields))
                if data['# pxname'] == backend_name and data['svname'] not in ['FRONTEND', 'BACKEND']:
                    server_name = data['svname']
                    if server_name in server_mapping:
                        server_ip = server_mapping[server_name]
                        try:
                            weight = int(data.get('weight', 1))
                        except ValueError:
                            weight = 1
                        result[backend_name][server_ip] = weight
        return result
    except Exception:
        return {}

def get_haproxy_server_name_for_host(host_ip):
    """Convert host IP to HAProxy server name"""
    config = load_config()
    nodes = config.get('nodes', [])
    for i, node in enumerate(nodes):
        if node['host'] == host_ip:
            return f"node{i+1}"
    return host_ip

def haproxy_set_server_weight(backend_name, server_name, weight):
    """Set weight for a specific server in HAProxy backend using admin socket"""
    config = load_config()
    haproxy_config = config.get('haproxy', {})
    
    socket_host = haproxy_config.get('admin_socket_host', '127.0.0.1')
    socket_port = haproxy_config.get('admin_socket_port')
    
    if not socket_port:
        return False, 'HAProxy admin socket port not configured'
    
    try:
        weight = int(weight)
        if weight < 0 or weight > 256:
            return False, 'Weight must be between 0 and 256'
    except ValueError:
        return False, 'Invalid weight value'
    
    try:
        import subprocess
        
        # Construct the HAProxy admin command
        command = f"set weight {backend_name}/{server_name} {weight}"
        
        # Use socat to send command to HAProxy admin socket
        socat_command = [
            'socat', 'stdio', f'tcp:{socket_host}:{socket_port}'
        ]
        
        # Execute the command
        process = subprocess.Popen(
            socat_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=command + '\n', timeout=10)
        
        if process.returncode == 0:
            # Check if the response indicates success
            if "Backend not found" in stdout or "No such server" in stdout:
                return False, f"HAProxy error: {stdout.strip()}"
            else:
                return True, "Weight updated successfully"
        else:
            return False, f"Socket communication failed: {stderr.strip()}"
        
    except subprocess.TimeoutExpired:
        return False, "Timeout communicating with HAProxy socket"
    except FileNotFoundError:
        return False, "socat command not found. Please install socat."
    except Exception as e:
        return False, str(e)

def haproxy_admin_server_action(backend_name, server_name, action):
    url, auth = get_haproxy_admin_url_and_auth()
    if not url:
        return False, 'HAProxy config not found'
    if action not in ['enable', 'disable']:
        return False, 'Unsupported action'
    try:
        resp = requests.post(url, data={'b': backend_name, 's': server_name, 'action': action}, auth=auth, timeout=5)
        if resp.status_code in [200, 303, 302]:
            return True, 'OK'
        resp2 = requests.post(url, data={'b': backend_name, 's': server_name, 'action': f'{action} server'}, auth=auth, timeout=5)
        if resp2.status_code in [200, 303, 302]:
            return True, 'OK'
        return False, f"HTTP {resp.status_code}/{resp2.status_code}"
    except Exception as e:
        return False, str(e)

def api_haproxy_restart():
    """API endpoint for HAProxy restart"""
    try:
        cmd = get_restart_command()
        # Execute the restart command locally. SECURITY: In production, protect this endpoint!
        completed = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        ok = completed.returncode == 0
        return jsonify({
            'ok': ok,
            'returncode': completed.returncode,
            'stdout': completed.stdout,
            'stderr': completed.stderr
        }), (200 if ok else 500)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

def api_haproxy_set_weight():
    """API endpoint for setting HAProxy server weight"""
    try:
        body = request.get_json(silent=True) or {}
        config = load_config()
        backend_name = body.get('backend_name') or config.get('haproxy', {}).get('backend_name', 'galera_cluster_backend')
        server_host = body.get('server_name')  # This is actually the host IP
        weight = body.get('weight')
        
        if not server_host:
            return jsonify({'success': False, 'error': 'server_name is required'}), 400
        
        if weight is None:
            return jsonify({'success': False, 'error': 'weight is required'}), 400
            
        # Convert host IP to HAProxy server name
        server_name = get_haproxy_server_name_for_host(server_host)
        
        success, msg = haproxy_set_server_weight(backend_name, server_name, weight)
        return jsonify({'success': success, 'message': msg}), (200 if success else 500)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

