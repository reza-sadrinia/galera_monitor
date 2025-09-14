from datetime import datetime
import mysql.connector
from src.state import previous_readings

def calculate_rates(previous_readings, node_key, current_time, total_writes, total_reads, total_queries):
    if node_key in previous_readings:
        prev = previous_readings[node_key]
        time_diff = (current_time - prev['time']).total_seconds()
        if time_diff > 0:
            writes_diff = total_writes - prev['writes']
            reads_diff = total_reads - prev['reads']
            queries_diff = total_queries - prev['queries']
            return (
                round(writes_diff / time_diff, 2),
                round(reads_diff / time_diff, 2),
                round(queries_diff / time_diff, 2)
            )
    return (0, 0, 0)

def read_node_status(node_config):
    try:
        # Check for placeholder values
        if node_config['password'] in ['your_password_here', 'password', '']:
            raise Exception(f"Invalid password configuration for {node_config['host']}. Please update config.yaml with actual credentials.")
        
        conn = mysql.connector.connect(
            host=node_config['host'],
            user=node_config['user'],
            password=node_config['password'],
            port=node_config['port'],
            connect_timeout=5,
            autocommit=True
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW GLOBAL STATUS")
        global_status = {row['Variable_name']: row['Value'] for row in cursor.fetchall()}
        cursor.execute("SHOW VARIABLES LIKE 'wsrep_provider_options'")
        provider_options = cursor.fetchone()
        cursor.close()
        conn.close()
        return global_status, provider_options
    except mysql.connector.Error as e:
        raise Exception(f"MySQL connection failed for {node_config['host']}: {str(e)}")
    except Exception as e:
        raise Exception(f"Error reading node status for {node_config['host']}: {str(e)}")

def parse_wsrep_provider_options(options_str):
    """Parse wsrep_provider_options string into a dictionary"""
    options = {}
    if options_str:
        for option in options_str.split(';'):
            if '=' in option:
                key, value = option.split('=', 1)
                options[key.strip()] = value.strip()
    return options

def get_node_status(node_config):
    """Get comprehensive status for a single node"""
    try:
        current_time = datetime.now()
        node_key = node_config['host']
        
        # Import here to avoid circular imports
        from src.haproxy import get_haproxy_server_states
        import yaml
        
        # Load config locally to avoid circular imports
        def load_config():
            try:
                with open('config.yaml', 'r') as file:
                    return yaml.safe_load(file)
            except:
                return {'nodes': []}
        
        # Get HAProxy stats first
        haproxy_states = get_haproxy_server_states()
        
        # Get all global status variables
        global_status, provider_options = read_node_status(node_config)
        
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
        wps, rps, qps = calculate_rates(previous_readings, node_key, current_time, total_writes, total_reads, total_queries)
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

