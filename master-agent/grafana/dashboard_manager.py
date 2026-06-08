import time
import requests
from requests.auth import HTTPBasicAuth


def _get_grafana_auth():
    from config import GRAFANA_URL, GRAFANA_USER, GRAFANA_PASSWORD
    return GRAFANA_URL, HTTPBasicAuth(GRAFANA_USER, GRAFANA_PASSWORD)


def wait_for_grafana(timeout: int = 120) -> bool:
    url, auth = _get_grafana_auth()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{url}/api/health", auth=auth, timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def create_datasource() -> bool:
    from config import PROMETHEUS_HOST, PROMETHEUS_PORT
    url, auth = _get_grafana_auth()
    r = requests.get(f"{url}/api/datasources/name/Prometheus", auth=auth, timeout=10)
    if r.status_code == 200:
        return True
    payload = {
        "name": "Prometheus",
        "type": "prometheus",
        "url": f"http://{PROMETHEUS_HOST}:{PROMETHEUS_PORT}",
        "access": "proxy",
        "isDefault": True,
        "jsonData": {"timeInterval": "15s"},
    }
    r = requests.post(f"{url}/api/datasources", json=payload, auth=auth, timeout=10)
    return r.status_code in (200, 409)


def import_dashboard() -> bool:
    url, auth = _get_grafana_auth()
    payload = {
        "dashboard": _build_dashboard_json(),
        "overwrite": True,
        "folderId": 0,
    }
    r = requests.post(f"{url}/api/dashboards/db", json=payload, auth=auth, timeout=15)
    return r.status_code == 200


def _build_dashboard_json() -> dict:
    return {
        "id": None,
        "uid": "polaris-nodes",
        "title": "Polaris Monitor — Node Overview",
        "tags": ["polaris", "nodes"],
        "timezone": "browser",
        "schemaVersion": 38,
        "refresh": "30s",
        "templating": {
            "list": [
                {
                    "name": "instance",
                    "type": "query",
                    "datasource": {"type": "prometheus", "uid": ""},
                    "query": {
                        "query": 'label_values(up{job="node_exporter"}, instance)',
                        "refId": "StandardVariableQuery",
                    },
                    "refresh": 2,
                    "multi": True,
                    "includeAll": True,
                    "allValue": ".*",
                    "label": "Instance",
                }
            ]
        },
        "panels": [
            _stat_panel(1,  "Online Nodes",  'count(polaris_node_up == 1) or vector(0)',          0,  0, 4, 3, "green"),
            _stat_panel(2,  "Offline Nodes", 'count(polaris_node_up == 0) or vector(0)',          4,  0, 4, 3, "red"),
            _stat_panel(3,  "Total Nodes",   'count(polaris_node_up)',                            8,  0, 4, 3, "blue"),
            _timeseries_panel(4,  "CPU Usage %",          0,  3, 12, 8,
                '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle",instance=~"$instance"}[5m])) * 100)',
                "percent"),
            _timeseries_panel(5,  "Memory Usage %",       12, 3, 12, 8,
                '(1 - (node_memory_MemAvailable_bytes{instance=~"$instance"} / node_memory_MemTotal_bytes{instance=~"$instance"})) * 100',
                "percent"),
            _timeseries_panel(6,  "Disk Usage %",         0,  11, 12, 8,
                '(1 - (node_filesystem_avail_bytes{mountpoint="/",instance=~"$instance"} / node_filesystem_size_bytes{mountpoint="/",instance=~"$instance"})) * 100',
                "percent"),
            _timeseries_panel(7,  "Load Average (1m)",    12, 11, 12, 8,
                'node_load1{instance=~"$instance"}', "short"),
            _timeseries_panel(8,  "Network Receive",      0,  19, 12, 8,
                'rate(node_network_receive_bytes_total{instance=~"$instance",device!="lo"}[5m])',
                "bytes"),
            _timeseries_panel(9,  "Network Transmit",     12, 19, 12, 8,
                'rate(node_network_transmit_bytes_total{instance=~"$instance",device!="lo"}[5m])',
                "bytes"),
            _node_status_table(10, "Node Status",         0,  27, 24, 8),
            _ssh_table(11,         "SSH Check Status",    0,  35, 24, 8),
            _reboot_table(12,      "Reboot History",      0,  43, 24, 8),
        ],
    }


def _stat_panel(uid, title, expr, x, y, w, h, color):
    return {
        "id": uid, "type": "stat", "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{"datasource": {"type": "prometheus"}, "expr": expr, "instant": True, "refId": "A"}],
        "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "value", "graphMode": "none"},
        "fieldConfig": {"defaults": {"color": {"mode": "fixed", "fixedColor": color},
            "thresholds": {"mode": "absolute", "steps": [{"color": color, "value": None}]}}},
    }


def _timeseries_panel(uid, title, x, y, w, h, expr, unit):
    return {
        "id": uid, "type": "timeseries", "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{"datasource": {"type": "prometheus"}, "expr": expr,
                     "legendFormat": "{{instance}}", "refId": "A"}],
        "fieldConfig": {"defaults": {"unit": unit, "min": 0, "color": {"mode": "palette-classic"}}, "overrides": []},
        "options": {"tooltip": {"mode": "multi"}, "legend": {"displayMode": "list", "placement": "bottom"}},
    }


def _node_status_table(uid, title, x, y, w, h):
    return {
        "id": uid, "type": "table", "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [
            {"datasource": {"type": "prometheus"},
             "expr": "polaris_node_up", "instant": True, "refId": "A", "format": "table"},
        ],
        "transformations": [
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "__name__": True, "job": True, "instance": True},
                "renameByName": {"Value": "Status", "agent_id": "Agent ID",
                                 "hostname": "Hostname", "private_ip": "Private IP"},
            }},
        ],
        "fieldConfig": {"overrides": [{"matcher": {"id": "byName", "options": "Status"},
            "properties": [
                {"id": "mappings", "value": [{"options": {
                    "0": {"color": "red",   "text": "Offline"},
                    "1": {"color": "green", "text": "Online"}},
                    "type": "value"}]},
                {"id": "custom.displayMode", "value": "color-background"},
            ]}]},
    }


def _ssh_table(uid, title, x, y, w, h):
    return {
        "id": uid, "type": "table", "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [
            {"datasource": {"type": "prometheus"},
             "expr": "polaris_node_ssh", "instant": True, "refId": "A", "format": "table"},
        ],
        "transformations": [
            {"id": "organize", "options": {
                "excludeByName": {
                    "Time": True, "__name__": True, "job": True,
                    "instance": True, "private_ip": True,
                },
                "renameByName": {
                    "agent_id": "Agent ID",
                    "hostname": "Hostname",
                    "last_ssh_check": "Last SSH Check",
                    "last_seen": "Last Seen",
                    "Value": "SSH Status",
                },
            }},
        ],
        "fieldConfig": {
            "overrides": [
                {"matcher": {"id": "byName", "options": "SSH Status"},
                 "properties": [
                     {"id": "mappings", "value": [{"options": {
                         "-1": {"color": "yellow", "text": "Unknown"},
                         "0":  {"color": "red",    "text": "Failed"},
                         "1":  {"color": "green",  "text": "OK"}},
                         "type": "value"}]},
                     {"id": "custom.displayMode", "value": "color-background"},
                 ]},
            ],
        },
    }


def _reboot_table(uid, title, x, y, w, h):
    return {
        "id": uid, "type": "table", "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [
            {"datasource": {"type": "prometheus"},
             "expr": "polaris_node_reboot", "instant": True, "refId": "A", "format": "table"},
        ],
        "transformations": [
            {"id": "organize", "options": {
                "excludeByName": {
                    "Time": True, "__name__": True, "job": True,
                    "instance": True, "private_ip": True, "Value": True,
                },
                "renameByName": {
                    "agent_id": "Agent ID",
                    "hostname": "Hostname",
                    "last_boot": "Last Reboot",
                    "reason": "Reason",
                },
            }},
        ],
        "fieldConfig": {
            "overrides": [
                {"matcher": {"id": "byName", "options": "Reason"},
                 "properties": [
                     {"id": "mappings", "value": [{"options": {
                         "agent":   {"color": "orange", "text": "Agent Auto-Reboot"},
                         "manual":  {"color": "blue",   "text": "Manual"},
                         "system":  {"color": "red",    "text": "System / Crash"},
                         "unknown": {"color": "gray",   "text": "Unknown"}},
                         "type": "value"}]},
                     {"id": "custom.displayMode", "value": "color-background"},
                 ]},
            ],
        },
    }


def setup_grafana():
    print("  Waiting for Grafana to start...")
    if not wait_for_grafana():
        print("  [WARN] Grafana did not start in time — skipping auto-configuration")
        return False
    print("  Creating Prometheus datasource...")
    if create_datasource():
        print("  [OK] Datasource configured")
    print("  Importing dashboard...")
    if import_dashboard():
        print("  [OK] Dashboard imported")
    return True
