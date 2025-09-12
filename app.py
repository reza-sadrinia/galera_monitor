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
from src.state import previous_readings, alert_state
from src.haproxy import (
    get_haproxy_stats as _hap_stats,
    get_haproxy_server_states as _hap_states,
    get_haproxy_admin_url_and_auth as _hap_admin_url_auth,
    haproxy_admin_server_action as _hap_admin_action
)
from src.cluster import read_node_status as _read_node_status, calculate_rates as _calc_rates
from src.alerts import evaluate_alerts as _evaluate_alerts
from src.logs import api_available_logs, api_server_logs
from src.slow_queries import api_slow_queries, api_enable_slow_log
from src.database import api_transactions, api_process_list, api_kill_process
from src.config import api_get_config, api_update_config

app = Flask(__name__)

# State moved to src/state (imported above)

def load_config():
    with open('config.yaml', 'r') as file:
        return yaml.safe_load(file)

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

def get_node_status(node_config):
    try:
        current_time = datetime.now()
        node_key = node_config['host']
        
        # Get HAProxy stats first
        haproxy_states = get_haproxy_server_states()
        
        # Get all global status variables
        global_status, provider_options = _read_node_status(node_config)
        
        # Get Galera specific status
        galera_vars = [
            'wsrep_local_state_comment',
            'wsrep_cluster_size',
            'wsrep_local_index',
            'wsrep_cluster_status',
            'wsrep_flow_control_active',
            'wsrep_flow_control_recv',
            'wsrep_flow_control_sent',
            'wsrep_flow_control_paused',
            'wsrep_local_cert_failures',
            'wsrep_local_recv_queue',
            'wsrep_local_send_queue',
            'wsrep_cert_deps_distance',
            'wsrep_last_committed',
            'wsrep_provider_version',
            'wsrep_thread_count',
            'wsrep_cluster_conf_id',
            'wsrep_cluster_size',
            'wsrep_cluster_state_uuid',
            'wsrep_local_state',
            'wsrep_ready',
            'wsrep_applier_thread_count',
            'wsrep_rollbacker_thread_count'
        ]
        
        status = {var: global_status.get(var, '-') for var in galera_vars}
        
        # Add additional server metrics
        server_metrics = [
            'Com_lock_tables',
            'Threads_running',
            'Memory_used',
            'Slave_connections',
            'Slaves_connected'
        ]
        
        for metric in server_metrics:
            status[metric] = global_status.get(metric, '0')
            
        # Add HAProxy current connections and state
        hap_state = haproxy_states.get(node_config['host'], {})
        status['haproxy_current'] = hap_state.get('current', 0)
        status['haproxy_status'] = hap_state.get('status', '-')
        
        # Get wsrep_provider_options
        if provider_options and 'Value' in provider_options:
            options = parse_wsrep_provider_options(provider_options['Value'])
            status['gcache.page_size'] = options.get('gcache.page_size', '-')
            status['gcache.size'] = options.get('gcache.size', '-')
            status['gcs.fc_limit'] = options.get('gcs.fc_limit', '-')
        
        # Calculate metrics based on SHOW GLOBAL STATUS
        total_writes = (
            int(global_status.get('Com_insert', 0)) +
            int(global_status.get('Com_insert_select', 0)) +
            int(global_status.get('Com_update', 0)) +
            int(global_status.get('Com_update_multi', 0))
        )
        
        total_reads = int(global_status.get('Com_select', 0))
        total_queries = int(global_status.get('Queries', 0))
        
        # Calculate rates based on previous readings
        wps, rps, qps = _calc_rates(previous_readings, node_key, current_time, total_writes, total_reads, total_queries)
        status['writes_per_second'] = wps
        status['reads_per_second'] = rps
        status['queries_per_second'] = qps

        # If HAProxy marks server as MAINT/DOWN, zero out rates for UI clarity
        hap_stat_str = str(status.get('haproxy_status') or '').upper()
        if any(x in hap_stat_str for x in ['MAINT', 'DOWN']):
            status['writes_per_second'] = 0
            status['reads_per_second'] = 0
            status['queries_per_second'] = 0
        
        # Store current readings for next calculation
        previous_readings[node_key] = {
            'writes': total_writes,
            'reads': total_reads,
            'queries': total_queries,
            'time': current_time
        }
        
        # DB resources were closed inside _read_node_status
        
        return {
            'host': node_config['host'],
            'status': status,
            'timestamp': current_time.isoformat(),
            'error': None
        }
    except Exception as e:
        return {
            'host': node_config['host'],
            'status': None,
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }

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
    config = load_config()
    nodes_status = [get_node_status(node) for node in config['nodes']]
    # Evaluate alerts based on current snapshot
    try:
        evaluate_alerts(nodes_status)
    except Exception:
        # Never let alert evaluation break the API response
        pass
    response = jsonify(nodes_status)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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

@app.route('/api/server_logs', methods=['GET'])
def route_api_server_logs():
    return api_server_logs()

@app.route('/api/available_logs', methods=['GET'])
def route_api_available_logs():
    return api_available_logs()

@app.route('/api/slow_queries', methods=['GET'])
def route_api_slow_queries():
    # Fix dependency injection
    from src.slow_queries import get_nodes_status, load_config
    globals()['get_nodes_status'] = get_nodes_status
    globals()['load_config'] = load_config
    return api_slow_queries()

@app.route('/api/enable_slow_log', methods=['POST'])
def route_api_enable_slow_log():
    return api_enable_slow_log()

@app.route('/api/get_config', methods=['GET'])
def route_api_get_config():
    return api_get_config()

@app.route('/api/update_config', methods=['POST'])
def route_api_update_config():
    return api_update_config()

@app.route('/api/transactions', methods=['GET'])
def route_api_transactions():
    return api_transactions()

@app.route('/api/process_list', methods=['GET'])
def route_api_process_list():
    return api_process_list()

@app.route('/api/kill_process', methods=['POST'])
def route_api_kill_process():
    return api_kill_process()

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