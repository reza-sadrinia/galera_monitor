from flask import request, jsonify
import mysql.connector
import yaml

def load_config():
    try:
        with open('config.yaml', 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print("Error: config.yaml not found")
        return {'nodes': []}
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        return {'nodes': []}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {'nodes': []}

def get_nodes_status():
    # This function is not used in database module, keeping as placeholder
    pass

def api_transactions():
    try:
        host = request.args.get('host')
        config = load_config()
        
        if not host:
            nodes = config.get('nodes', [])
            if not nodes:
                return jsonify({'ok': False, 'error': 'No nodes available'}), 404
            host = nodes[0]['host']
        
        # Find the specific node configuration
        node_config = None
        for node in config.get('nodes', []):
            if node['host'] == host:
                node_config = node
                break
        
        if not node_config:
            return jsonify({'ok': False, 'error': f'Node {host} not found in configuration'}), 404
        
        # Check for placeholder password
        if node_config['password'] in ['your_password_here', 'password', '']:
            return jsonify({'ok': False, 'error': f'Invalid password configuration for {host}. Please update config.yaml with actual credentials.'}), 500
        
        # Connect to database using node-specific configuration
        db_config = {
            'host': node_config['host'],
            'user': node_config['user'],
            'password': node_config['password'],
            'port': node_config.get('port', 3306),
            'database': 'information_schema',
            'connect_timeout': 5
        }
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get active transactions
            cursor.execute("""
                SELECT 
                    trx_id, 
                    trx_state, 
                    trx_started, 
                    trx_requested_lock_id, 
                    trx_wait_started, 
                    trx_mysql_thread_id, 
                    trx_query,
                    trx_operation_state,
                    trx_tables_in_use,
                    trx_tables_locked,
                    trx_rows_locked,
                    trx_rows_modified,
                    trx_concurrency_tickets,
                    trx_isolation_level,
                    trx_unique_checks,
                    trx_foreign_key_checks
                FROM information_schema.innodb_trx
                ORDER BY trx_started
            """)
            transactions = cursor.fetchall()
            
            # Convert dates to strings for JSON serialization
            for trx in transactions:
                if 'trx_started' in trx and trx['trx_started']:
                    trx['trx_started'] = trx['trx_started'].isoformat()
                if 'trx_wait_started' in trx and trx['trx_wait_started']:
                    trx['trx_wait_started'] = trx['trx_wait_started'].isoformat()
            
            # Get lock information
            cursor.execute("""
                SELECT 
                    lock_id,
                    lock_trx_id,
                    lock_mode,
                    lock_type,
                    lock_table,
                    lock_index,
                    lock_space,
                    lock_page,
                    lock_rec,
                    lock_data
                FROM information_schema.innodb_locks
            """)
            locks = cursor.fetchall()
            
            # Get lock wait information
            cursor.execute("""
                SELECT 
                    requesting_trx_id,
                    requested_lock_id,
                    blocking_trx_id,
                    blocking_lock_id
                FROM information_schema.innodb_lock_waits
            """)
            lock_waits = cursor.fetchall()
            
            # Get general InnoDB status information
            cursor.execute("""
                SHOW ENGINE INNODB STATUS
            """)
            innodb_status = cursor.fetchone()
            
            return jsonify({
                'ok': True,
                'host': host,
                'transactions': transactions,
                'locks': locks,
                'lock_waits': lock_waits,
                'innodb_status': innodb_status['Status'] if innodb_status and 'Status' in innodb_status else None
            })
            
        except mysql.connector.Error as err:
            return jsonify({'ok': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

def api_process_list():
    try:
        host = request.args.get('host')
        config = load_config()
        
        if not host:
            nodes = config.get('nodes', [])
            if not nodes:
                return jsonify({'ok': False, 'error': 'No nodes available'}), 404
            host = nodes[0]['host']
        
        # Find the specific node configuration
        node_config = None
        for node in config.get('nodes', []):
            if node['host'] == host:
                node_config = node
                break
        
        if not node_config:
            return jsonify({'ok': False, 'error': f'Node {host} not found in configuration'}), 404
        
        # Check for placeholder password
        if node_config['password'] in ['your_password_here', 'password', '']:
            return jsonify({'ok': False, 'error': f'Invalid password configuration for {host}. Please update config.yaml with actual credentials.'}), 500
        
        # Connect to database using node-specific configuration
        db_config = {
            'host': node_config['host'],
            'user': node_config['user'],
            'password': node_config['password'],
            'port': node_config.get('port', 3306),
            'database': 'information_schema',
            'connect_timeout': 5
        }
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get list of active processes
            cursor.execute("""
                SELECT 
                    ID as id,
                    USER as user,
                    HOST as host,
                    DB as db,
                    COMMAND as command,
                    TIME as time,
                    STATE as state,
                    INFO as info,
                    TIME_MS as time_ms
                FROM information_schema.PROCESSLIST
                ORDER BY TIME DESC
            """)
            processes = cursor.fetchall()
            
            return jsonify({
                'ok': True,
                'host': host,
                'processes': processes
            })
            
        except mysql.connector.Error as err:
            return jsonify({'ok': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

def api_kill_process():
    try:
        data = request.get_json()
        host = data.get('host') if data else None
        process_id = data.get('process_id') if data else None
        
        if not host or not process_id:
            return jsonify({'ok': False, 'error': 'Host and process_id parameters are required'}), 400
        
        config = load_config()
        
        # Find the specific node configuration
        node_config = None
        for node in config.get('nodes', []):
            if node['host'] == host:
                node_config = node
                break
        
        if not node_config:
            return jsonify({'ok': False, 'error': f'Node {host} not found in configuration'}), 404
        
        # Check for placeholder password
        if node_config['password'] in ['your_password_here', 'password', '']:
            return jsonify({'ok': False, 'error': f'Invalid password configuration for {host}. Please update config.yaml with actual credentials.'}), 500
        
        # Connect to database using node-specific configuration
        db_config = {
            'host': node_config['host'],
            'user': node_config['user'],
            'password': node_config['password'],
            'port': node_config.get('port', 3306),
            'connect_timeout': 5
        }
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        try:
            # Kill the process
            cursor.execute(f"KILL %s", (int(process_id),))
            
            return jsonify({
                'ok': True,
                'host': host,
                'process_id': process_id,
                'message': f'Process {process_id} killed successfully'
            })
            
        except mysql.connector.Error as err:
            return jsonify({'ok': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500