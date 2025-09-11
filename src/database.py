from flask import request, jsonify
import mysql.connector

def load_config():
    # This is a placeholder - the actual function will be imported from app.py
    pass

def get_nodes_status():
    # This is a placeholder - the actual function will be imported from app.py
    pass

def api_transactions():
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
            'database': 'information_schema'
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
        if not host:
            nodes_status = get_nodes_status()
            if not nodes_status or len(nodes_status) == 0:
                return jsonify({'ok': False, 'error': 'No nodes available'}), 404
            host = nodes_status[0]['host']
        
        # Connect to database
        config = load_config()
        db_config = {
            'host': host,
            'user': config.get('mysql', {}).get('user', 'root'),
            'password': config.get('mysql', {}).get('password', ''),
            'database': 'information_schema'
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
        host = request.args.get('host')
        process_id = request.args.get('process_id')
        
        if not host or not process_id:
            return jsonify({'ok': False, 'error': 'Host and process_id parameters are required'}), 400
        
        # Connect to database
        config = load_config()
        db_config = {
            'host': host,
            'user': config.get('mysql', {}).get('user', 'root'),
            'password': config.get('mysql', {}).get('password', ''),
            'database': 'information_schema'
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