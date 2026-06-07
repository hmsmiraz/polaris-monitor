import json
import os
from pathlib import Path
import threading

_lock = threading.Lock()


def _get_targets_file() -> Path:
    from config import PROMETHEUS_TARGETS_FILE
    return PROMETHEUS_TARGETS_FILE


def _read_targets() -> list:
    targets_file = _get_targets_file()
    if not targets_file.exists():
        return []
    with open(targets_file) as f:
        data = json.load(f)
    return data


def _write_targets(targets: list):
    targets_file = _get_targets_file()
    targets_file.parent.mkdir(parents=True, exist_ok=True)
    with open(targets_file, "w") as f:
        json.dump(targets, f, indent=2)


def add_target(agent_id: str, hostname: str, private_ip: str, port: int = 9100):
    with _lock:
        targets = _read_targets()
        address = f"{private_ip}:{port}"

        for entry in targets:
            if address in entry.get("targets", []):
                entry["labels"]["hostname"] = hostname
                entry["labels"]["agent_id"] = agent_id
                _write_targets(targets)
                return

        targets.append({
            "targets": [address],
            "labels": {
                "job": "node_exporter",
                "instance": hostname,
                "hostname": hostname,
                "agent_id": agent_id,
            },
        })
        _write_targets(targets)


def remove_target(private_ip: str, port: int = 9100):
    with _lock:
        targets = _read_targets()
        address = f"{private_ip}:{port}"
        updated = [t for t in targets if address not in t.get("targets", [])]
        _write_targets(updated)


def rebuild_targets_from_db():
    """Rebuild the full targets file from active database nodes."""
    from services.node_service import get_all_nodes
    nodes = get_all_nodes()

    with _lock:
        targets = []
        for node in nodes:
            if node["status"] == "online" and node["private_ip"]:
                address = f"{node['private_ip']}:{node['node_exporter_port']}"
                targets.append({
                    "targets": [address],
                    "labels": {
                        "job": "node_exporter",
                        "instance": node["hostname"] or node["agent_id"],
                        "hostname": node["hostname"] or "",
                        "agent_id": node["agent_id"],
                    },
                })
        _write_targets(targets)


def write_prometheus_config(config_path: str = None):
    from config import PROMETHEUS_CONFIG_FILE, PROMETHEUS_TARGETS_DIR
    path = Path(config_path) if config_path else PROMETHEUS_CONFIG_FILE

    config = f"""global:
  scrape_interval: 15s
  evaluation_interval: 15s
  scrape_timeout: 10s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node_exporter'
    file_sd_configs:
      - files:
          - '{PROMETHEUS_TARGETS_DIR}/*.json'
        refresh_interval: 30s
    relabel_configs:
      - source_labels: [instance]
        target_label: instance
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(config)
