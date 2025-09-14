import yaml

def load_config():
    """Load configuration from config.yaml file"""
    try:
        with open('config.yaml', 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print("Error: config.yaml file not found. Please copy config-example.yaml to config.yaml and configure it.")
        return {'nodes': []}
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        return {'nodes': []}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {'nodes': []}

def get_alert_config():
    """Get alert configuration with defaults"""
    config = load_config()
    alerts_cfg = config.get('alerts', {}) or {}
    telegram_cfg = config.get('telegram', {}) or {}
    # Defaults
    defaults = {
        'enabled': True,
        'cooldown_seconds': 300,
        'qps': {
            'min': None,
            'max': None
        },
        'wps': {
            'min': None,
            'max': None
        },
        'flow_control': {
            'active': True,
            'paused_threshold': None
        },
        'haproxy': {
            'connections_critical': None
        },
        'node': {
            'offline': True,  # when node not synced/primary
        }
    }
    # Merge shallowly
    def merge_dict(base, override):
        result = dict(base)
        for k, v in (override or {}).items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = merge_dict(result[k], v)
            else:
                result[k] = v
        return result
    return {
        'alerts': merge_dict(defaults, alerts_cfg),
        'telegram': telegram_cfg
    }

def get_restart_command():
    """Get HAProxy restart command from config or default"""
    cfg = load_config()
    # Allow override via config.yaml → haproxy.restart_command
    cmd = (cfg.get('haproxy', {}) or {}).get('restart_command')
    if cmd:
        return cmd
    # sensible default for most Linux distros
    return 'systemctl restart haproxy'