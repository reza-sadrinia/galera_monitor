from datetime import datetime
import mysql.connector

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
    conn = mysql.connector.connect(
        host=node_config['host'],
        user=node_config['user'],
        password=node_config['password'],
        port=node_config['port']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SHOW GLOBAL STATUS")
    global_status = {row['Variable_name']: row['Value'] for row in cursor.fetchall()}
    cursor.execute("SHOW VARIABLES LIKE 'wsrep_provider_options'")
    provider_options = cursor.fetchone()
    cursor.close()
    conn.close()
    return global_status, provider_options

