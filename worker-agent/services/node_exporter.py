"""
Installs and manages the metrics exporter for the current OS:
  Linux  → prometheus/node_exporter
  Windows → prometheus-community/windows_exporter
"""
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

NODE_EXPORTER_VERSION   = "1.7.0"
WIN_EXPORTER_VERSION    = "0.25.1"
NODE_EXPORTER_USER      = "node_exporter"
BIN_DIR                 = Path("/usr/local/bin")          # Linux
WIN_INSTALL_DIR         = Path("C:/Program Files/Polaris") # Windows


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)


# ── OS detection ───────────────────────────────────────────────────────────────

def _is_windows() -> bool:
    return sys.platform == "win32"


def _linux_arch() -> str:
    import platform
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine.startswith("aarch64") or machine.startswith("arm64"):
        return "arm64"
    return "amd64"


# ── Linux installation ─────────────────────────────────────────────────────────

def _linux_bin() -> Path:
    return BIN_DIR / "node_exporter"


def _is_installed_linux() -> bool:
    return _linux_bin().exists()


def _install_linux(port: int = 9100):
    arch     = _linux_arch()
    filename = f"node_exporter-{NODE_EXPORTER_VERSION}.linux-{arch}"
    url      = (
        f"https://github.com/prometheus/node_exporter/releases/download/"
        f"v{NODE_EXPORTER_VERSION}/{filename}.tar.gz"
    )
    print(f"  Downloading Node Exporter {NODE_EXPORTER_VERSION} ({arch})...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tarball = os.path.join(tmpdir, f"{filename}.tar.gz")
        urllib.request.urlretrieve(url, tarball)
        with tarfile.open(tarball) as tar:
            tar.extractall(tmpdir)
        binary = os.path.join(tmpdir, filename, "node_exporter")
        run(f"cp {binary} {_linux_bin()}")
        run(f"chmod +x {_linux_bin()}")

    # Create dedicated system user
    run(f"id -u {NODE_EXPORTER_USER} >/dev/null 2>&1 || "
        f"useradd --system --no-create-home --shell /bin/false {NODE_EXPORTER_USER}")

    _write_linux_service(port)
    run("systemctl daemon-reload")
    run("systemctl enable node-exporter")
    run("systemctl start node-exporter")
    print("  [OK] Node Exporter installed and started")


def _write_linux_service(port: int = 9100):
    service = f"""\
[Unit]
Description=Polaris Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User={NODE_EXPORTER_USER}
Group={NODE_EXPORTER_USER}
Type=simple
ExecStart={_linux_bin()} --web.listen-address=0.0.0.0:{port}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/node-exporter.service", "w") as f:
        f.write(service)


# ── Windows installation ───────────────────────────────────────────────────────

def _win_exe() -> Path:
    return WIN_INSTALL_DIR / "windows_exporter.exe"


def _is_installed_windows() -> bool:
    return _win_exe().exists()


def _install_windows(port: int = 9100):
    url = (
        f"https://github.com/prometheus-community/windows_exporter/releases/download/"
        f"v{WIN_EXPORTER_VERSION}/windows_exporter-{WIN_EXPORTER_VERSION}-amd64.exe"
    )
    print(f"  Downloading Windows Exporter {WIN_EXPORTER_VERSION}...")
    WIN_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, str(_win_exe()))
    print("  [OK] Windows Exporter downloaded")

    # Install as Windows Service via NSSM if available, otherwise sc.exe
    nssm = _find_nssm()
    if nssm:
        run(f'"{nssm}" install polaris-node-exporter "{_win_exe()}" '
            f'--web.listen-address=0.0.0.0:{port} '
            f'--collectors.enabled cpu,cs,logical_disk,net,os,system,time', check=False)
        run(f'"{nssm}" start polaris-node-exporter', check=False)
    else:
        # Fallback: windows_exporter can self-install as a service
        run(f'"{_win_exe()}" --service install '
            f'--web.listen-address=0.0.0.0:{port}', check=False)
        run('sc start windows_exporter', check=False)

    print(f"  [OK] Windows Exporter service installed (port {port})")


def _find_nssm() -> str:
    for loc in [r"C:\nssm\nssm.exe", r"C:\Windows\System32\nssm.exe",
                r"C:\ProgramData\chocolatey\bin\nssm.exe"]:
        if Path(loc).exists():
            return loc
    r = run("where nssm", check=False)
    if r.returncode == 0:
        return r.stdout.strip().splitlines()[0]
    return ""


# ── Public interface ───────────────────────────────────────────────────────────

def is_installed() -> bool:
    return _is_installed_windows() if _is_windows() else _is_installed_linux()


def setup(port: int = 9100, skip_if_installed: bool = True):
    if skip_if_installed and is_installed():
        print("  [SKIP] Exporter already installed")
        if not _is_windows():
            _write_linux_service(port)
            run("systemctl daemon-reload")
            run("systemctl enable node-exporter")
            run("systemctl restart node-exporter", check=False)
        return

    if _is_windows():
        _install_windows(port)
    else:
        _install_linux(port)
