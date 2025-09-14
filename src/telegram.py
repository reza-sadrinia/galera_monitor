import requests
from datetime import datetime
from src.state import alert_state

def telegram_enabled(telegram_cfg):
    """Check if telegram is enabled and properly configured"""
    return bool(telegram_cfg.get('enabled')) and bool(telegram_cfg.get('bot_token')) and bool(telegram_cfg.get('chat_id'))

def send_telegram_message(telegram_cfg, message):
    """Send message to telegram bot"""
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
    """Check if alert should be sent based on cooldown period"""
    now = datetime.now()
    node_state = alert_state.setdefault(node_key, {})
    last_times = node_state.setdefault('last_sent', {})
    last_time = last_times.get(alert_key)
    if last_time is None or (now - last_time).total_seconds() >= cooldown_seconds:
        last_times[alert_key] = now
        return True
    return False