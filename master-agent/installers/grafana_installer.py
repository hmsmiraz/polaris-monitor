import subprocess


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)


def _detect_pkg_manager() -> str:
    for mgr in ("dnf", "yum", "apt-get", "zypper"):
        if run(f"which {mgr}", check=False).returncode == 0:
            return mgr
    return "apt-get"


def is_installed() -> bool:
    return run("which grafana-server", check=False).returncode == 0


def _install_deb():
    run("apt-get install -y -qq apt-transport-https software-properties-common wget")
    run("mkdir -p /etc/apt/keyrings")
    run(
        "wget -q -O - https://apt.grafana.com/gpg.key | "
        "gpg --dearmor | tee /etc/apt/keyrings/grafana.gpg > /dev/null"
    )
    run(
        "echo 'deb [signed-by=/etc/apt/keyrings/grafana.gpg] "
        "https://apt.grafana.com stable main' | "
        "tee /etc/apt/sources.list.d/grafana.list"
    )
    run("apt-get update -qq")
    run("apt-get install -y -qq grafana")


def _install_rpm(mgr: str):
    repo = """\
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
"""
    with open("/etc/yum.repos.d/grafana.repo", "w") as f:
        f.write(repo)
    run(f"{mgr} install -y grafana")


def _install_zypper():
    run(
        "zypper addrepo https://rpm.grafana.com grafana 2>/dev/null || true"
    )
    run("zypper install -y grafana")


def install_grafana():
    mgr = _detect_pkg_manager()
    print(f"  Installing Grafana via {mgr}...")
    if mgr == "apt-get":
        _install_deb()
    elif mgr in ("dnf", "yum"):
        _install_rpm(mgr)
    elif mgr == "zypper":
        _install_zypper()
    print("  [OK] Grafana installed")


def configure_grafana():
    config_path = "/etc/grafana/grafana.ini"
    additions = "\n[security]\nadmin_user = admin\nadmin_password = admin\n"
    try:
        with open(config_path) as f:
            content = f.read()
        if "admin_password" not in content:
            with open(config_path, "a") as f:
                f.write(additions)
    except FileNotFoundError:
        pass


def setup(skip_if_installed: bool = True):
    if skip_if_installed and is_installed():
        print("  [SKIP] Grafana already installed")
    else:
        install_grafana()
    configure_grafana()
    run("systemctl enable grafana-server")
    print("  [OK] Grafana service configured")
