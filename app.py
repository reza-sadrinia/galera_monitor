from flask import Flask, render_template, jsonify, request
import subprocess
import mysql.connector
from datetime import datetime, timedelta
import json
import re
import time
import os
from src.state import alert_state
from src.config_utils import load_config, get_alert_config, get_restart_command
from src.telegram import telegram_enabled, send_telegram_message, should_send_alert
from src.utils import calculate_rate
from src.haproxy import (
    get_haproxy_stats,
    get_haproxy_server_states,
    get_haproxy_admin_url_and_auth,
    haproxy_admin_server_action,
    get_haproxy_server_weights,
    haproxy_set_server_weight,
    get_haproxy_server_name_for_host,
    api_haproxy_restart,
    api_haproxy_set_weight
)
from src.cluster import read_node_status as _read_node_status, calculate_rates as _calc_rates, get_node_status, parse_wsrep_provider_options
from src.alerts import evaluate_alerts

from src.slow_queries import api_slow_queries
from src.transactions import handle_transactions, handle_process_list, handle_kill_process
from src.config import api_get_config, api_update_config

app = Flask(__name__)

# State moved to src/state (imported above)

# Configuration and utility functions moved to src/ modules

# HAProxy functions moved to src/haproxy.py



# Alert and telegram functions moved to src/ modules

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
        
        # Add HAProxy weights to the response
        try:
            haproxy_weights = get_haproxy_server_weights()
        except Exception as e:
            print(f"HAProxy weights error: {e}")
            haproxy_weights = {}
        
        response_data = {
            'nodes': nodes_status,
            'haproxy_weights': haproxy_weights
        }
        
        response = jsonify(response_data)
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
def route_api_haproxy_restart():
    return api_haproxy_restart()

@app.route('/api/haproxy/server/weight', methods=['POST'])
def route_api_haproxy_set_weight():
    return api_haproxy_set_weight()



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