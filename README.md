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