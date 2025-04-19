from flask import Flask, render_template, jsonify
import mysql.connector
import yaml
from datetime import datetime
import json
import re
import time
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# Store previous readings for each node
previous_readings = {}

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_cluster_status():
    config = load_config()
    nodes_status = [get_node_status(node) for node in config['nodes']]
    response = jsonify(nodes_status)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)