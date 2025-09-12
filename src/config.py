from flask import request, jsonify
import mysql.connector
import yaml

def load_config():
    with open('config.yaml', 'r') as file:
        return yaml.safe_load(file)

def get_nodes_status():
    # This function is not used in config module, keeping as placeholder
    pass

def api_get_config():
    try:
        host = request.args.get('host')
        if not host:
            config = load_config()
            nodes = config.get('nodes', [])
            if not nodes:
                return jsonify({'ok': False, 'error': 'No nodes available'}), 404
            host = nodes[0]['host']
        
        # Connect to database
        config = load_config()
        db_config = {
            'host': host,
            'user': config.get('mysql', {}).get('user', 'root'),
            'password': config.get('mysql', {}).get('password', ''),
            'database': 'mysql'
        }
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get important MySQL configuration variables
            variables = [
                # Galera specific
                'wsrep_cluster_size', 'wsrep_cluster_status', 'wsrep_connected',
                'wsrep_ready', 'wsrep_provider', 'wsrep_provider_options',
                
                # General MySQL
                'version', 'version_comment', 'innodb_version',
                'max_connections', 'max_user_connections', 'max_connect_errors',
                'connect_timeout', 'wait_timeout', 'interactive_timeout',
                
                # Query cache
                'query_cache_type', 'query_cache_size', 'query_cache_limit',
                
                # Buffers and memory
                'innodb_buffer_pool_size', 'innodb_buffer_pool_instances',
                'innodb_log_buffer_size', 'innodb_log_file_size',
                'key_buffer_size', 'max_allowed_packet',
                
                # Slow query log
                'slow_query_log', 'long_query_time', 'slow_query_log_file',
                
                # Replication
                'server_id', 'log_bin', 'binlog_format',
                'sync_binlog', 'expire_logs_days',
                
                # InnoDB settings
                'innodb_flush_log_at_trx_commit', 'innodb_flush_method',
                'innodb_file_per_table', 'innodb_io_capacity',
                'innodb_read_io_threads', 'innodb_write_io_threads'
            ]
            
            # Build query to get variables
            placeholders = ', '.join(['%s'] * len(variables))
            cursor.execute(f"SHOW VARIABLES WHERE Variable_name IN ({placeholders})", variables)
            config_data = {row['Variable_name']: row['Value'] for row in cursor.fetchall()}
            
            # Get some status variables
            status_vars = [
                'wsrep_local_recv_queue', 'wsrep_local_send_queue',
                'wsrep_flow_control_paused', 'wsrep_flow_control_paused_ns',
                'wsrep_flow_control_sent', 'wsrep_flow_control_recv',
                'wsrep_cert_deps_distance', 'wsrep_apply_oooe',
                'wsrep_apply_oool', 'wsrep_commit_oooe', 'wsrep_commit_oool',
                'uptime', 'threads_connected', 'threads_running',
                'max_used_connections', 'queries', 'questions',
                'slow_queries', 'opened_tables', 'innodb_buffer_pool_read_requests',
                'innodb_buffer_pool_reads', 'innodb_row_lock_current_waits',
                'innodb_row_lock_time', 'innodb_row_lock_waits'
            ]
            
            placeholders = ', '.join(['%s'] * len(status_vars))
            cursor.execute(f"SHOW GLOBAL STATUS WHERE Variable_name IN ({placeholders})", status_vars)
            status_data = {row['Variable_name']: row['Value'] for row in cursor.fetchall()}
            
            return jsonify({
                'ok': True,
                'host': host,
                'config': config_data,
                'status': status_data
            })
            
        except mysql.connector.Error as err:
            return jsonify({'ok': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

def api_update_config():
    try:
        data = request.get_json()
        host = data.get('host')
        variable = data.get('variable')
        value = data.get('value')
        
        if not host or not variable or value is None:
            return jsonify({'ok': False, 'error': 'Host, variable and value parameters are required'}), 400
        
        # List of variables that can be changed dynamically
        allowed_variables = [
            'slow_query_log', 'long_query_time', 'max_connections',
            'max_user_connections', 'connect_timeout', 'wait_timeout',
            'interactive_timeout', 'query_cache_type', 'query_cache_size',
            'query_cache_limit', 'max_allowed_packet', 'expire_logs_days'
        ]
        
        if variable not in allowed_variables:
            return jsonify({'ok': False, 'error': f'Variable {variable} cannot be modified dynamically or is not allowed'}), 400
        
        # Connect to database
        config = load_config()
        db_config = {
            'host': host,
            'user': config.get('mysql', {}).get('user', 'root'),
            'password': config.get('mysql', {}).get('password', ''),
            'database': 'mysql'
        }
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        try:
            # Get current value
            cursor.execute(f"SELECT @@{variable}")
            old_value = cursor.fetchone()[0]
            
            # Update variable
            cursor.execute(f"SET GLOBAL {variable} = %s", (value,))
            
            # Confirm change
            cursor.execute(f"SELECT @@{variable}")
            new_value = cursor.fetchone()[0]
            
            return jsonify({
                'ok': True,
                'host': host,
                'variable': variable,
                'old_value': old_value,
                'new_value': new_value
            })
            
        except mysql.connector.Error as err:
            return jsonify({'ok': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500