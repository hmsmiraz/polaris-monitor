import os
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

PROMETHEUS_VERSION = "2.50.1"
PROMETHEUS_USER = "prometheus"
PROMETHEUS_BIN_DIR = Path("/usr/local/bin")
PROMETHEUS_DATA_DIR = Path("/var/lib/prometheus")
PROMETHEUS_CONFIG_DIR = Path("/etc/prometheus")


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)


def is_installed() -> bool:
    return (PROMETHEUS_BIN_DIR / "prometheus").exists()


def install_prometheus():
    print(f"  Downloading Prometheus {PROMETHEUS_VERSION}...")
    arch = "amd64"
    filename = f"prometheus-{PROMETHEUS_VERSION}.linux-{arch}"
    url = (
        f"https://github.com/prometheus/prometheus/releases/download/"
        f"v{PROMETHEUS_VERSION}/{filename}.tar.gz"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        tarball = os.path.join(tmpdir, f"{filename}.tar.gz")
        urllib.request.urlretrieve(url, tarball)
        with tarfile.open(tarball) as tar:
            tar.extractall(tmpdir)
        extracted = os.path.join(tmpdir, filename)
        run(f"cp {extracted}/prometheus {PROMETHEUS_BIN_DIR}/")
        run(f"cp {extracted}/promtool {PROMETHEUS_BIN_DIR}/")
        run(f"cp -r {extracted}/consoles {PROMETHEUS_CONFIG_DIR}/ 2>/dev/null || true")
        run(f"cp -r {extracted}/console_libraries {PROMETHEUS_CONFIG_DIR}/ 2>/dev/null || true")

    run(f"id -u {PROMETHEUS_USER} &>/dev/null || "
        f"useradd --no-create-home --shell /bin/false {PROMETHEUS_USER}")

    for d in [PROMETHEUS_DATA_DIR, PROMETHEUS_CONFIG_DIR,
              Path("/etc/prometheus/file_sd")]:
        d.mkdir(parents=True, exist_ok=True)
        run(f"chown {PROMETHEUS_USER}:{PROMETHEUS_USER} {d}")

    for bin_path in [PROMETHEUS_BIN_DIR / "prometheus", PROMETHEUS_BIN_DIR / "promtool"]:
        run(f"chown {PROMETHEUS_USER}:{PROMETHEUS_USER} {bin_path}")

    print("  [OK] Prometheus binary installed")


def write_service():
    service = """\
[Unit]
Description=Prometheus Monitoring
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \\
    --config.file=/etc/prometheus/prometheus.yml \\
    --storage.tsdb.path=/var/lib/prometheus/ \\
    --web.console.templates=/etc/prometheus/consoles \\
    --web.console.libraries=/etc/prometheus/console_libraries \\
    --web.listen-address=0.0.0.0:9090 \\
    --web.enable-lifecycle \\
    --storage.tsdb.retention.time=15d
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/prometheus.service", "w") as f:
        f.write(service)
    run("systemctl daemon-reload")


def setup(skip_if_installed: bool = True):
    if skip_if_installed and is_installed():
        print("  [SKIP] Prometheus already installed")
        write_service()
        return
    install_prometheus()
    write_service()
    print("  [OK] Prometheus service configured")
