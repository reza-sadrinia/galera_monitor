from flask import Flask, render_template, jsonify, request
import subprocess
import mysql.connector
import yaml
from datetime import datetime, timedelta
import json
import re
import time
import os
import requests
from requests.auth import HTTPBasicAuth
from src.state import alert_state
from src.haproxy import (
    get_haproxy_stats as _hap_stats,
    get_haproxy_server_states as _hap_states,
    get_haproxy_admin_url_and_auth as _hap_admin_url_auth,
    haproxy_admin_server_action as _hap_admin_action,
    get_haproxy_server_weights as _hap_weights,
    haproxy_set_server_weight as _hap_set_weight
)
from src.cluster import read_node_status as _read_node_status, calculate_rates as _calc_rates, get_node_status, parse_wsrep_provider_options
from src.alerts import evaluate_alerts as _evaluate_alerts

from src.slow_queries import api_slow_queries
from src.transactions import handle_transactions, handle_process_list, handle_kill_process
from src.config import api_get_config, api_update_config

app = Flask(__name__)

# State moved to src/state (imported above)

def load_config():
    try:
        with open('config.yaml', 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print("Error: config.yaml file not found. Please copy config-example.yaml to config.yaml and configure it.")
        return {'nodes': []}
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        return {'nodes': []}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {'nodes': []}



def calculate_rate(current_value, previous_value, current_time, previous_time):
    if previous_value is None or previous_time is None:
        return 0
    
    value_diff = current_value - previous_value
    time_diff = (current_time - previous_time).total_seconds()
    
    if time_diff <= 0:
        return 0
        
    return round(value_diff / time_diff, 2)

def get_haproxy_stats():
    # delegate to src.haproxy without changing behavior
    return _hap_stats(load_config)

def get_haproxy_server_states():
    # delegate to src.haproxy without changing behavior
    return _hap_states(load_config)

def get_haproxy_admin_url_and_auth():
    return _hap_admin_url_auth(load_config)

def haproxy_admin_server_action(backend_name, server_name, action):
    """Perform enable/disable on a backend server via HAProxy stats admin HTTP.

    action: 'enable' or 'disable'
    Returns (ok: bool, message: str)
    """
    # delegate to src.haproxy without changing behavior
    return _hap_admin_action(load_config, backend_name, server_name, action)

def get_haproxy_server_weights():
    """Get current weights of all servers in the backend"""
    return _hap_weights(load_config)

def haproxy_set_server_weight(backend_name, server_name, weight):
    """Set weight for a specific server in HAProxy backend"""
    return _hap_set_weight(load_config, backend_name, server_name, weight)

def get_haproxy_server_name_for_host(host: str) -> str:
    """Resolve HAProxy server name given node host.
    - If node has 'haproxy_server' in config, use it.
    - Else default to node{i+1} by order in nodes list.
    If no match, return the original host.
    """
    try:
        cfg = load_config()
        nodes = cfg.get('nodes') or []
        for idx, node in enumerate(nodes):
            if str(node.get('host')) == str(host):
                if node.get('haproxy_server'):
                    return str(node['haproxy_server'])
                return f"node{idx+1}"
    except Exception:
        pass
    return host



def get_alert_config():
    config = load_config()
    alerts_cfg = config.get('alerts', {}) or {}
    telegram_cfg = config.get('telegram', {}) or {}
    # Defaults
    defaults = {
        'enabled': True,
        'cooldown_seconds': 300,
        'qps': {
            'min': None,
            'max': None
        },
        'wps': {
            'min': None,
            'max': None
        },
        'flow_control': {
            'active': True,
            'paused_threshold': None
        },
        'haproxy': {
            'connections_critical': None
        },
        'node': {
            'offline': True,  # when node not synced/primary
        }
    }
    # Merge shallowly
    def merge_dict(base, override):
        result = dict(base)
        for k, v in (override or {}).items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = merge_dict(result[k], v)
            else:
                result[k] = v
        return result
    return {
        'alerts': merge_dict(defaults, alerts_cfg),
        'telegram': telegram_cfg
    }

def get_restart_command():
    cfg = load_config()
    # Allow override via config.yaml → haproxy.restart_command
    cmd = (cfg.get('haproxy', {}) or {}).get('restart_command')
    if cmd:
        return cmd
    # sensible default for most Linux distros
    return 'systemctl restart haproxy'

def telegram_enabled(telegram_cfg):
    return bool(telegram_cfg.get('enabled')) and bool(telegram_cfg.get('bot_token')) and bool(telegram_cfg.get('chat_id'))

def send_telegram_message(telegram_cfg, message):
    if not telegram_enabled(telegram_cfg):
        return False
    try:
        token = telegram_cfg['bot_token']
        chat_id = telegram_cfg['chat_id']
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def should_send_alert(node_key, alert_key, cooldown_seconds):
    now = datetime.now()
    node_state = alert_state.setdefault(node_key, {})
    last_times = node_state.setdefault('last_sent', {})
    last_time = last_times.get(alert_key)
    if last_time is None or (now - last_time).total_seconds() >= cooldown_seconds:
        last_times[alert_key] = now
        return True
    return False

def evaluate_alerts(nodes_status):
    # delegate to src.alerts without changing behavior
    _evaluate_alerts(load_config, alert_state, nodes_status)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_cluster_status():
    try:
        config = load_config()
        if not config or 'nodes' not in config:
            print("Error: No nodes found in config")
            return jsonify({'error': 'No nodes configured'}), 500
        
        nodes_status = []
        for node in config['nodes']:
            status = get_node_status(node)
            nodes_status.append(status)
            if status.get('error'):
                print(f"Error for node {node.get('host')}: {status['error']}")
        
        # Evaluate alerts based on current snapshot
        try:
            evaluate_alerts(nodes_status)
        except Exception as e:
            print(f"Alert evaluation error: {e}")
            # Never let alert evaluation break the API response
            pass
        
        response = jsonify(nodes_status)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f"Critical error in get_cluster_status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/haproxy/server/<action>', methods=['POST'])
def api_haproxy_server_action(action):
    try:
        body = request.get_json(silent=True) or {}
        backend = body.get('backend') or load_config().get('haproxy', {}).get('backend_name', 'galera_cluster_backend')
        server = body.get('server')
        host = body.get('host')
        if not server:
            if not host:
                return jsonify({'ok': False, 'error': 'server or host is required'}), 400
            server = get_haproxy_server_name_for_host(host)
        ok, msg = haproxy_admin_server_action(backend, server, action)
        return jsonify({'ok': ok, 'message': msg}), (200 if ok else 500)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/haproxy/restart', methods=['POST'])
def api_haproxy_restart():
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

@app.route('/api/haproxy/weights', methods=['GET'])
def api_haproxy_get_weights():
    """Get current weights of all servers"""
    try:
        weights = get_haproxy_server_weights()
        return jsonify({'ok': True, 'weights': weights}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/haproxy/server/weight', methods=['POST'])
def api_haproxy_set_weight():
    """Set weight for a specific server"""
    try:
        body = request.get_json(silent=True) or {}
        backend = body.get('backend') or load_config().get('haproxy', {}).get('backend_name', 'galera_cluster_backend')
        server = body.get('server')
        host = body.get('host')
        weight = body.get('weight')
        
        if not server:
            if not host:
                return jsonify({'ok': False, 'error': 'server or host is required'}), 400
            server = get_haproxy_server_name_for_host(host)
        
        if weight is None:
            return jsonify({'ok': False, 'error': 'weight is required'}), 400
            
        ok, msg = haproxy_set_server_weight(backend, server, weight)
        return jsonify({'ok': ok, 'message': msg}), (200 if ok else 500)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500



@app.route('/api/slow_queries', methods=['GET'])
def route_api_slow_queries():
    # Fix dependency injection
    from src.slow_queries import get_nodes_status, load_config
    globals()['get_nodes_status'] = get_nodes_status
    globals()['load_config'] = load_config
    return api_slow_queries()


@app.route('/api/get_config', methods=['GET'])
def route_api_get_config():
    return api_get_config()

@app.route('/api/update_config', methods=['POST'])
def route_api_update_config():
    return api_update_config()

@app.route('/api/transactions', methods=['GET'])
def route_api_transactions():
    return handle_transactions()

@app.route('/api/process_list', methods=['GET'])
def route_api_process_list():
    return handle_process_list()

@app.route('/api/kill_process', methods=['POST'])
def route_api_kill_process():
    return handle_kill_process()

@app.route('/api/nodes', methods=['GET'])
def api_nodes():
    try:
        config = load_config()
        nodes = config.get('nodes', [])
        
        # Format nodes data for frontend
        formatted_nodes = []
        for i, node in enumerate(nodes):
            formatted_nodes.append({
                'host': node.get('host'),
                'name': node.get('name', f'Node {i+1}'),
                'port': node.get('port', 3306)
            })
        
        return jsonify({
            'ok': True,
            'nodes': formatted_nodes
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)