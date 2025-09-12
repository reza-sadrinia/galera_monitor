from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

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

def get_haproxy_stats(load_config):
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

def get_haproxy_server_states(load_config):
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

def get_haproxy_admin_url_and_auth(load_config):
    config = load_config()
    haproxy_config = config.get('haproxy', {})
    if not haproxy_config:
        return None, None
    path = str(haproxy_config.get('stats_path') or '/stats')
    path_admin = path.replace(';csv', '')
    url = f"http://{haproxy_config['host']}:{haproxy_config['stats_port']}{path_admin}"
    auth = HTTPBasicAuth(haproxy_config['stats_user'], haproxy_config['stats_password'])
    return url, auth

def haproxy_admin_server_action(load_config, backend_name, server_name, action):
    url, auth = get_haproxy_admin_url_and_auth(load_config)
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

