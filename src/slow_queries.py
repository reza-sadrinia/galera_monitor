from flask import request, jsonify
import mysql.connector
import yaml

def load_config():
    with open('config.yaml', 'r') as file:
        return yaml.safe_load(file)

def get_nodes_status():
    # This function is not used in slow_queries module, keeping as placeholder
    pass

def api_slow_queries():
    try:
        # Get parameters from query string
        limit = request.args.get('limit', default=100, type=int)
        host = request.args.get('host', default=None, type=str)
        
        # If host is not specified, use the first node
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
            'database': 'mysql'
        }
        
        # Query to get slow queries
        slow_query_sql = """
        SELECT 
            start_time, 
            user_host, 
            query_time, 
            lock_time, 
            rows_sent, 
            rows_examined, 
            db, 
            last_insert_id, 
            insert_id, 
            server_id, 
            sql_text,
            thread_id
        FROM slow_log
        ORDER BY start_time DESC
        LIMIT %s
        """
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute(slow_query_sql, (limit,))
            slow_queries = cursor.fetchall()
            
            # Convert dates to serializable format
            for query in slow_queries:
                if 'start_time' in query and query['start_time']:
                    query['start_time'] = query['start_time'].isoformat()
                    
                # Convert numbers to readable format
                if 'query_time' in query and query['query_time']:
                    query['query_time_seconds'] = float(query['query_time'].total_seconds())
                    query['query_time'] = str(query['query_time'])
                    
                if 'lock_time' in query and query['lock_time']:
                    query['lock_time_seconds'] = float(query['lock_time'].total_seconds())
                    query['lock_time'] = str(query['lock_time'])
            
            return jsonify({
                'ok': True,
                'host': host,
                'slow_queries': slow_queries
            })
            
        except mysql.connector.Error as err:
            # If slow_log table doesn't exist, show appropriate message
            if err.errno == 1146:  # Table doesn't exist
                return jsonify({
                    'ok': False, 
                    'error': 'Slow query log table not found. Slow query logging may not be enabled on this server.',
                    'help': 'To enable slow query logging, run: SET GLOBAL slow_query_log = 1; SET GLOBAL long_query_time = 1;'
                }), 404
            else:
                return jsonify({'ok': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

def api_enable_slow_log():
    try:
        # Get parameters from request body
        data = request.get_json()
        host = data.get('host')
        enable = data.get('enable', True)
        query_time = data.get('query_time', 1)  # time in seconds
        
        # If host is not specified, use the first node
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
            'database': 'mysql'
        }
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        try:
            # Configure slow query log
            cursor.execute(f"SET GLOBAL slow_query_log = {'ON' if enable else 'OFF'};")
            cursor.execute(f"SET GLOBAL long_query_time = {query_time};")
            
            # Check current status
            cursor.execute("SHOW GLOBAL VARIABLES LIKE 'slow_query_log';")
            slow_log_status = cursor.fetchone()[1]
            
            cursor.execute("SHOW GLOBAL VARIABLES LIKE 'long_query_time';")
            long_query_time = cursor.fetchone()[1]
            
            cursor.execute("SHOW GLOBAL VARIABLES LIKE 'slow_query_log_file';")
            slow_log_file = cursor.fetchone()[1]
            
            return jsonify({
                'ok': True,
                'host': host,
                'slow_query_log': slow_log_status,
                'long_query_time': long_query_time,
                'slow_query_log_file': slow_log_file
            })
            
        except mysql.connector.Error as err:
            return jsonify({'ok': False, 'error': str(err)}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500