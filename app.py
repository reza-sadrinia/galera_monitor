from flask import Flask, render_template, jsonify, request
import subprocess
import mysql.connector
import yaml
from datetime import datetime, timedelta
import json
import re
import time
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# Store previous readings for each node
previous_readings = {}

# Store alert state (e.g., last sent timestamps) to prevent alert flooding
alert_state = {}

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
    config = load_config()
    haproxy_config = config.get('haproxy', {})
    
    if not haproxy_config:
        return {}
    
    try:
        url = f"http://{haproxy_config['host']}:{haproxy_config['stats_port']}{haproxy_config['stats_path']}"
        response = requests.get(
            url,
            auth=HTTPBasicAuth(haproxy_config['stats_user'], haproxy_config['stats_password']),
            timeout=5
        )
        
        if response.status_code != 200:
            return {}
        
        # Parse CSV response
        lines = response.text.strip().split('\n')
        headers = lines[0].split(',')
        current_by_server = {}
        
        # Create server mapping from config
        nodes = config.get('nodes', [])
        server_mapping = {
            f"node{i+1}": node['host'] 
            for i, node in enumerate(nodes)
        }
        
        # Get backend name from config or use default
        backend_name = haproxy_config.get('backend_name', 'galera_cluster_backend')
        
        for line in lines[1:]:
            fields = line.split(',')
            if len(fields) >= len(headers):
                data = dict(zip(headers, fields))
                # Process galera cluster backend servers
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

def get_haproxy_admin_url_and_auth():
    """Derive HAProxy admin URL (HTML endpoint) and auth from config.
    We reuse stats credentials. If stats_path ends with ';csv', we strip it for admin actions.
    """
    config = load_config()
    haproxy_config = config.get('haproxy', {})
    if not haproxy_config:
        return None, None
    path = str(haproxy_config.get('stats_path') or '/stats')
    # Strip CSV suffix if present
    path_admin = path.replace(';csv', '')
    url = f"http://{haproxy_config['host']}:{haproxy_config['stats_port']}{path_admin}"
    auth = HTTPBasicAuth(haproxy_config['stats_user'], haproxy_config['stats_password'])
    return url, auth

def haproxy_admin_server_action(backend_name, server_name, action):
    """Perform enable/disable on a backend server via HAProxy stats admin HTTP.

    action: 'enable' or 'disable'
    Returns (ok: bool, message: str)
    """
    url, auth = get_haproxy_admin_url_and_auth()
    if not url:
        return False, 'HAProxy config not found'
    if action not in ['enable', 'disable']:
        return False, 'Unsupported action'
    try:
        # First try the common form: action=enable|disable
        resp = requests.post(
            url,
            data={'b': backend_name, 's': server_name, 'action': action},
            auth=auth,
            timeout=5
        )
        if resp.status_code in [200, 303, 302]:
            return True, 'OK'
        # Fallback older form: action="enable server"|"disable server"
        resp2 = requests.post(
            url,
            data={'b': backend_name, 's': server_name, 'action': f'{action} server'},
            auth=auth,
            timeout=5
        )
        if resp2.status_code in [200, 303, 302]:
            return True, 'OK'
        return False, f"HTTP {resp.status_code}/{resp2.status_code}"
    except Exception as e:
        return False, str(e)

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
        haproxy_stats = get_haproxy_stats()
        
        conn = mysql.connector.connect(
            host=node_config['host'],
            user=node_config['user'],
            password=node_config['password'],
            port=node_config['port']
        )
        cursor = conn.cursor(dictionary=True)
        
        # Get all global status variables
        cursor.execute("SHOW GLOBAL STATUS")
        global_status = {row['Variable_name']: row['Value'] for row in cursor.fetchall()}
        
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
            
        # Add HAProxy current connections
        status['haproxy_current'] = haproxy_stats.get(node_config['host'], 0)
        
        # Get wsrep_provider_options
        cursor.execute("SHOW VARIABLES LIKE 'wsrep_provider_options'")
        provider_options = cursor.fetchone()
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
        if node_key in previous_readings:
            prev = previous_readings[node_key]
            time_diff = (current_time - prev['time']).total_seconds()
            
            if time_diff > 0:
                writes_diff = total_writes - prev['writes']
                reads_diff = total_reads - prev['reads']
                queries_diff = total_queries - prev['queries']
                
                status['writes_per_second'] = round(writes_diff / time_diff, 2)
                status['reads_per_second'] = round(reads_diff / time_diff, 2)
                status['queries_per_second'] = round(queries_diff / time_diff, 2)
            else:
                status['writes_per_second'] = 0
                status['reads_per_second'] = 0
                status['queries_per_second'] = 0
        else:
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
        
        cursor.close()
        conn.close()
        
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
    cfg = get_alert_config()
    alerts_cfg = cfg['alerts']
    telegram_cfg = cfg['telegram']
    if not alerts_cfg.get('enabled'):
        return
    cooldown = int(alerts_cfg.get('cooldown_seconds', 300) or 300)

    for node in nodes_status:
        host = node.get('host')
        status = (node.get('status') or {})
        error = node.get('error')
        node_key = host

        # Node offline / not synced / error
        offline_triggered = False
        if error:
            offline_triggered = True
            reason = f"error: {error}"
        else:
            state_comment = str(status.get('wsrep_local_state_comment') or '')
            cluster_status = str(status.get('wsrep_cluster_status') or '')
            wsrep_ready = str(status.get('wsrep_ready') or '')
            if state_comment.lower() != 'synced' or cluster_status.lower() != 'primary' or wsrep_ready.lower() not in ['on', 'ready', '1']:
                offline_triggered = True
                reason = f"state={state_comment}, cluster={cluster_status}, ready={wsrep_ready}"
        if alerts_cfg['node'].get('offline') and offline_triggered:
            key = 'node_offline'
            if should_send_alert(node_key, key, cooldown):
                msg = (
                    f"<b>Galera Alert</b>\n"
                    f"Node: <code>{host}</code> appears <b>OFFLINE/UNSYNCED</b>\n"
                    f"Reason: {reason}"
                )
                send_telegram_message(telegram_cfg, msg)

        # Flow control alerts
        if alerts_cfg.get('flow_control', {}).get('active'):
            fc_active = str(status.get('wsrep_flow_control_active', '')).lower() == 'true'
            if fc_active and should_send_alert(node_key, 'flow_control_active', cooldown):
                msg = (
                    f"<b>Galera Alert</b>\n"
                    f"Node: <code>{host}</code> flow control is <b>ACTIVE</b>"
                )
                send_telegram_message(telegram_cfg, msg)
        paused_threshold = alerts_cfg.get('flow_control', {}).get('paused_threshold')
        if paused_threshold is not None:
            try:
                paused = float(status.get('wsrep_flow_control_paused', 0) or 0)
                if paused >= float(paused_threshold):
                    if should_send_alert(node_key, 'flow_control_paused', cooldown):
                        msg = (
                            f"<b>Galera Alert</b>\n"
                            f"Node: <code>{host}</code> flow_control_paused={paused} ≥ threshold={paused_threshold}"
                        )
                        send_telegram_message(telegram_cfg, msg)
            except Exception:
                pass

        # QPS/WPS thresholds
        qps_cfg = alerts_cfg.get('qps', {})
        wps_cfg = alerts_cfg.get('wps', {})
        try:
            qps = float(status.get('queries_per_second', 0) or 0)
            if qps_cfg.get('min') is not None and qps < float(qps_cfg['min']):
                if should_send_alert(node_key, 'qps_low', cooldown):
                    send_telegram_message(
                        telegram_cfg,
                        f"<b>Galera Alert</b>\nNode: <code>{host}</code> QPS low: {qps} < {qps_cfg['min']}"
                    )
            if qps_cfg.get('max') is not None and qps > float(qps_cfg['max']):
                if should_send_alert(node_key, 'qps_high', cooldown):
                    send_telegram_message(
                        telegram_cfg,
                        f"<b>Galera Alert</b>\nNode: <code>{host}</code> QPS high: {qps} > {qps_cfg['max']}"
                    )
        except Exception:
            pass
        try:
            wps = float(status.get('writes_per_second', 0) or 0)
            if wps_cfg.get('min') is not None and wps < float(wps_cfg['min']):
                if should_send_alert(node_key, 'wps_low', cooldown):
                    send_telegram_message(
                        telegram_cfg,
                        f"<b>Galera Alert</b>\nNode: <code>{host}</code> WPS low: {wps} < {wps_cfg['min']}"
                    )
            if wps_cfg.get('max') is not None and wps > float(wps_cfg['max']):
                if should_send_alert(node_key, 'wps_high', cooldown):
                    send_telegram_message(
                        telegram_cfg,
                        f"<b>Galera Alert</b>\nNode: <code>{host}</code> WPS high: {wps} > {wps_cfg['max']}"
                    )
        except Exception:
            pass

        # HAProxy connections
        hap_crit = alerts_cfg.get('haproxy', {}).get('connections_critical')
        if hap_crit is not None:
            try:
                cur = int(status.get('haproxy_current', 0) or 0)
                if cur >= int(hap_crit):
                    if should_send_alert(node_key, 'haproxy_conn_critical', cooldown):
                        send_telegram_message(
                            telegram_cfg,
                            f"<b>Galera Alert</b>\nNode: <code>{host}</code> HAProxy current connections {cur} ≥ {hap_crit}"
                        )
            except Exception:
                pass

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)