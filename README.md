# Galera Cluster Monitor

Web-based monitoring and lightweight control panel for Galera (MySQL) clusters. Shows real-time status, HAProxy connection stats, and includes optional Telegram alerts. The UI auto-refreshes and charts replication delay over time.

## Features

- **Real-time node status**: `SHOW GLOBAL STATUS` and key Galera `wsrep_*` fields
- **Auto refresh**: every 30 seconds (manual refresh button available)
- **Charts**: replication delay (`wsrep_local_recv_queue`) with axis starting at 0 and integer tx values
- **HAProxy integration**:
  - Read stats (current connections, server status)
  - Enable/disable specific backend servers via HAProxy admin
  - Optional local HAProxy restart from UI
- **Telegram alerts (optional)** for: node offline/unsynced, flow control, QPS/WPS thresholds, HAProxy current connections
- **Modern UI**: Bootstrap 5 + Plotly

## Requirements

- Python 3.9+
- Access from the app host to:
  - Each MySQL node (host, user, password, port)
  - HAProxy stats HTTP endpoint (if HAProxy features are used)

Install dependencies:
```bash
pip install -r requirements.txt
```

## Quick start

1) Create `config.yaml` (copy the example and edit):
```bash
cp config-example.yaml config.yaml
```

2) Edit `config.yaml` with your nodes and (optionally) HAProxy / alerts / Telegram.

3) Run the app:
```bash
python app.py
```

4) Open the UI: `http://localhost:5000`

## Configuration reference (`config.yaml`)

Minimal nodes configuration:
```yaml
nodes:
  - host: "node1.example.com"
    user: "root"
    password: "your_password"
    port: 3306
```

Recommended full example (matches `config-example.yaml`):
```yaml
nodes:
  - host: "node1.example.com"
    user: "root"
    password: "your_password"
    port: 3306
    haproxy_server: "node1"   # optional explicit HAProxy server name
  - host: "node2.example.com"
    user: "root"
    password: "your_password"
    port: 3306
    haproxy_server: "node2"
  - host: "node3.example.com"
    user: "root"
    password: "your_password"
    port: 3306
    haproxy_server: "node3"

haproxy:
  host: "haproxy.example.com"
  stats_port: 8404
  stats_path: "/stats;csv"      # CSV view required for stats parsing
  stats_user: "admin"
  stats_password: "your_password"
  backend_name: "galera_cluster_backend"
  # restart_command: "systemctl restart haproxy"  # optional override used by /api/haproxy/restart

telegram:
  enabled: false
  bot_token: "123456789:ABCDEF_your_bot_token_here"
  chat_id: "-1001122334455"  # channel/group/user ID

alerts:
  enabled: true
  cooldown_seconds: 300  # avoid alert flooding
  node:
    offline: true  # alert if node error/unsynced/not primary/not ready
  flow_control:
    active: true           # alert if wsrep_flow_control_active == true
    paused_threshold: 0.05 # alert if wsrep_flow_control_paused >= this
  qps:
    min: null              # numbers enable thresholding
    max: null
  wps:
    min: null
    max: null
  haproxy:
    connections_critical: null  # e.g., 800
```

Notes
- If a node lacks `haproxy_server`, the UI maps by order as `node1`, `node2`, ...
- `stats_path` for HAProxy should include `;csv` for stats parsing. Admin actions will use the same path without `;csv`.
- To change the restart command, set `haproxy.restart_command`. If not set, defaults to `systemctl restart haproxy`.

## UI and metrics

- Overview shows: `wsrep_local_state_comment`, `wsrep_cluster_status`, flow control flags, queues, thread counts, cert failures, HAProxy current connections, and computed rates: `queries_per_second`, `writes_per_second`, `reads_per_second`.
- Charts tab renders replication delay history per node. Y-axis starts at 0 and values are whole-number transactions ("tx").
- If HAProxy marks a server as MAINT/DOWN, per-second rates are displayed as 0 for clarity.

## API

- `GET /api/status` → list of nodes with computed metrics. Also evaluates alerts (non-blocking; errors are swallowed).
- `POST /api/haproxy/server/<action>` where `<action>` is `enable` or `disable`
  - JSON body: `{ host: "10.0.0.10" }` or `{ server: "node1", backend: "galera_cluster_backend" }`
  - Resolves `server` from `host` using `nodes[].haproxy_server` or position fallback
- `POST /api/haproxy/restart` → runs local restart command returned by config/default

## HAProxy requirements

- HAProxy stats endpoint must be reachable and protected with basic auth.
- Enable admin actions on the stats page if you intend to use enable/disable controls.
- The app requests `http://<host>:<stats_port><stats_path>` and removes `;csv` internally for admin actions.

## Alerts (Telegram)

The app can send Telegram messages when:
- Node is offline/unsynced/not primary/not ready
- Flow control active, or `wsrep_flow_control_paused` ≥ threshold
- QPS/WPS below/above thresholds
- HAProxy current connections ≥ critical threshold

Add to `config.yaml` as shown in the example above. Details:
- `cooldown_seconds` deduplicates per-node alert keys to avoid flooding.
- `chat_id` can be a user, group, or channel ID (add the bot to the group/channel).
- Alerts are evaluated whenever the UI fetches `/api/status`.

## Security

- Do not expose admin endpoints publicly. Protect the app behind a reverse proxy with auth.
- The HAProxy restart endpoint executes a shell command. Disable it by omitting `haproxy.restart_command` or restrict access at the proxy.
- Use strong DB credentials and network ACLs. Consider secrets management for sensitive values.
- Prefer HTTPS in production.

## Development

Project layout:
```
app.py                # Flask app and routes
src/cluster.py        # MySQL status fetch + rate calculations
src/haproxy.py        # HAProxy CSV stats + admin actions
src/alerts.py         # Alert evaluation + Telegram sender
src/state.py          # In-memory state for rate/alert cooldowns
templates/index.html  # UI
static/js/*.js        # UI logic and charts (Plotly)
static/css/style.css  # Styles
```

Run in debug:
```bash
python app.py
```

## License

MIT License