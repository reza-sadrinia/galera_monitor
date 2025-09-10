# Galera Cluster Monitor

A web-based monitoring tool for Galera MySQL clusters that displays real-time status and metrics for all nodes in the cluster.

## Features

- Real-time monitoring of Galera cluster nodes
- Beautiful web interface with Bootstrap 5
- Auto-refresh every 30 seconds
- Display of key Galera metrics:
  - Node State
  - Cluster Size
  - Node Index
  - Cluster Status
  - Flow Control Status
  - Queue Statistics
  - And more...

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your Galera nodes in `config.yaml`:
```yaml
nodes:
  - host: "node1.example.com"
    user: "root"
    password: "your_password"
    port: 3306
  # Add more nodes as needed
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to:
```
http://localhost:5000
```

## Security Notes

- Make sure to use strong passwords in the config file
- Consider using environment variables for sensitive data
- The application should be run behind a reverse proxy in production
- Enable SSL/TLS in production

## License

MIT License 

## Alerts (Telegram)

You can enable Telegram alerts for key events:

- Node leaves cluster / unsynced / not primary
- Flow control active or paused beyond a threshold
- QPS/WPS below or above thresholds
- HAProxy current connections above critical threshold

Add to your `config.yaml`:

```yaml
telegram:
  enabled: true
  bot_token: "123456789:ABCDEF_your_bot_token_here"
  chat_id: "-1001122334455"

alerts:
  enabled: true
  cooldown_seconds: 300
  node:
    offline: true
  flow_control:
    active: true
    paused_threshold: 0.05
  qps:
    min: 10
    max: 5000
  wps:
    min: 1
    max: 2000
  haproxy:
    connections_critical: 800
```

Notes:

- Cooldown prevents alert flooding per node/condition.
- `chat_id` can be a user, group, or channel ID. For groups, ensure the bot is added.
- Alerts are evaluated whenever `/api/status` is requested (UI refresh or API call).