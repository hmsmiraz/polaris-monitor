#!/usr/bin/env python3
import sys
import os
import signal
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _periodic(func, interval: float, stop_event: threading.Event, *args):
    while not stop_event.is_set():
        try:
            func(*args)
        except Exception as e:
            print(f"[{func.__name__}] Error: {e}")
        stop_event.wait(interval)


def run_agent():
    from config import (
        load_config, METRICS_INTERVAL, HEARTBEAT_INTERVAL, SSH_CHECK_INTERVAL
    )
    from heartbeat.heartbeat import send as send_heartbeat
    from collector.metrics_collector import send_metrics
    from alerts.alert_manager import check_and_alert
    from ssh_checker.ssh_checker import check as check_ssh

    cfg        = load_config()
    master_ip  = cfg["master_ip"]
    master_port = cfg["master_port"]
    agent_id   = cfg["agent_id"]

    print(f"[polaris-agent] Starting — ID={agent_id}, Master={master_ip}:{master_port}")

    stop = threading.Event()

    def _shutdown(signum, frame):
        print("[polaris-agent] Shutting down...")
        stop.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    threads = [
        threading.Thread(target=_periodic,
            args=(send_heartbeat, HEARTBEAT_INTERVAL, stop, master_ip, master_port, agent_id),
            name="heartbeat", daemon=True),
        threading.Thread(target=_periodic,
            args=(send_metrics, METRICS_INTERVAL, stop, master_ip, master_port, agent_id),
            name="metrics", daemon=True),
        threading.Thread(target=_periodic,
            args=(check_and_alert, METRICS_INTERVAL, stop, master_ip, master_port, agent_id),
            name="alerts", daemon=True),
        threading.Thread(target=_periodic,
            args=(check_ssh, SSH_CHECK_INTERVAL, stop, master_ip, master_port, agent_id),
            name="ssh-checker", daemon=True),
    ]

    for t in threads:
        t.start()

    print("[polaris-agent] All modules running.")
    while not stop.is_set():
        time.sleep(1)
    print("[polaris-agent] Stopped.")


if __name__ == "__main__":
    run_agent()
