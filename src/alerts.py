from datetime import datetime
import requests

def get_alert_config(load_config):
    config = load_config()
    alerts_cfg = config.get('alerts', {}) or {}
    telegram_cfg = config.get('telegram', {}) or {}
    defaults = {
        'enabled': True,
        'cooldown_seconds': 300,
        'qps': {'min': None, 'max': None},
        'wps': {'min': None, 'max': None},
        'flow_control': {'active': True, 'paused_threshold': None},
        'haproxy': {'connections_critical': None},
        'node': {'offline': True}
    }
    def merge_dict(base, override):
        result = dict(base)
        for k, v in (override or {}).items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = merge_dict(result[k], v)
            else:
                result[k] = v
        return result
    return { 'alerts': merge_dict(defaults, alerts_cfg), 'telegram': telegram_cfg }

def telegram_enabled(telegram_cfg):
    return bool(telegram_cfg.get('enabled')) and bool(telegram_cfg.get('bot_token')) and bool(telegram_cfg.get('chat_id'))

def send_telegram_message(telegram_cfg, message):
    if not telegram_enabled(telegram_cfg):
        return False
    try:
        token = telegram_cfg['bot_token']
        chat_id = telegram_cfg['chat_id']
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = { 'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML', 'disable_web_page_preview': True }
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def should_send_alert(alert_state, node_key, alert_key, cooldown_seconds):
    now = datetime.now()
    node_state = alert_state.setdefault(node_key, {})
    last_times = node_state.setdefault('last_sent', {})
    last_time = last_times.get(alert_key)
    if last_time is None or (now - last_time).total_seconds() >= cooldown_seconds:
        last_times[alert_key] = now
        return True
    return False

def evaluate_alerts(load_config, alert_state, nodes_status):
    cfg = get_alert_config(load_config)
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
            if should_send_alert(alert_state, node_key, key, cooldown):
                msg = (f"<b>Galera Alert</b>\nNode: <code>{host}</code> appears <b>OFFLINE/UNSYNCED</b>\nReason: {reason}")
                send_telegram_message(telegram_cfg, msg)
        if alerts_cfg.get('flow_control', {}).get('active'):
            fc_active = str(status.get('wsrep_flow_control_active', '')).lower() == 'true'
            if fc_active and should_send_alert(alert_state, node_key, 'flow_control_active', cooldown):
                send_telegram_message(telegram_cfg, f"<b>Galera Alert</b>\nNode: <code>{host}</code> flow control is <b>ACTIVE</b>")
        paused_threshold = alerts_cfg.get('flow_control', {}).get('paused_threshold')
        if paused_threshold is not None:
            try:
                paused = float(status.get('wsrep_flow_control_paused', 0) or 0)
                if paused >= float(paused_threshold):
                    if should_send_alert(alert_state, node_key, 'flow_control_paused', cooldown):
                        send_telegram_message(telegram_cfg, f"<b>Galera Alert</b>\nNode: <code>{host}</code> flow_control_paused={paused} ≥ threshold={paused_threshold}")
            except Exception:
                pass
        try:
            qps_cfg = alerts_cfg.get('qps', {})
            qps = float(status.get('queries_per_second', 0) or 0)
            if qps_cfg.get('min') is not None and qps < float(qps_cfg['min']):
                if should_send_alert(alert_state, node_key, 'qps_low', cooldown):
                    send_telegram_message(telegram_cfg, f"<b>Galera Alert</b>\nNode: <code>{host}</code> QPS low: {qps} < {qps_cfg['min']}")
            if qps_cfg.get('max') is not None and qps > float(qps_cfg['max']):
                if should_send_alert(alert_state, node_key, 'qps_high', cooldown):
                    send_telegram_message(telegram_cfg, f"<b>Galera Alert</b>\nNode: <code>{host}</code> QPS high: {qps} > {qps_cfg['max']}")
        except Exception:
            pass
        try:
            wps_cfg = alerts_cfg.get('wps', {})
            wps = float(status.get('writes_per_second', 0) or 0)
            if wps_cfg.get('min') is not None and wps < float(wps_cfg['min']):
                if should_send_alert(alert_state, node_key, 'wps_low', cooldown):
                    send_telegram_message(telegram_cfg, f"<b>Galera Alert</b>\nNode: <code>{host}</code> WPS low: {wps} < {wps_cfg['min']}")
            if wps_cfg.get('max') is not None and wps > float(wps_cfg['max']):
                if should_send_alert(alert_state, node_key, 'wps_high', cooldown):
                    send_telegram_message(telegram_cfg, f"<b>Galera Alert</b>\nNode: <code>{host}</code> WPS high: {wps} > {wps_cfg['max']}")
        except Exception:
            pass
        hap_crit = alerts_cfg.get('haproxy', {}).get('connections_critical')
        if hap_crit is not None:
            try:
                cur = int(status.get('haproxy_current', 0) or 0)
                if cur >= int(hap_crit):
                    if should_send_alert(alert_state, node_key, 'haproxy_conn_critical', cooldown):
                        send_telegram_message(telegram_cfg, f"<b>Galera Alert</b>\nNode: <code>{host}</code> HAProxy current connections {cur} ≥ {hap_crit}")
            except Exception:
                pass

