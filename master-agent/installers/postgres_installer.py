import subprocess
import time


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)


def _detect_pkg_manager() -> str:
    for mgr in ("dnf", "yum", "apt-get", "zypper"):
        r = run(f"which {mgr}", check=False)
        if r.returncode == 0:
            return mgr
    return "apt-get"


def _is_rhel_family(mgr: str) -> bool:
    return mgr in ("dnf", "yum")


def is_installed() -> bool:
    return run("which psql", check=False).returncode == 0


def install_postgres():
    mgr = _detect_pkg_manager()
    print(f"  Installing PostgreSQL via {mgr}...")

    if mgr == "apt-get":
        run("apt-get update -qq")
        run("apt-get install -y -qq postgresql postgresql-contrib")

    elif _is_rhel_family(mgr):
        run(f"{mgr} install -y postgresql-server postgresql-contrib")
        # RHEL requires explicit initdb
        r = run("postgresql-setup --initdb", check=False)
        if r.returncode != 0:
            run("postgresql-setup initdb", check=False)

    elif mgr == "zypper":
        run("zypper install -y postgresql-server")
        run("postgresql-setup --initdb", check=False)

    run("systemctl enable postgresql")
    run("systemctl start postgresql")
    time.sleep(3)
    print("  [OK] PostgreSQL installed")


def setup_database():
    from config import DB_NAME, DB_USER, DB_PASSWORD

    print(f"  Creating database '{DB_NAME}' and user '{DB_USER}'...")

    # Allow local connections for RHEL (pg_hba.conf uses 'ident' by default)
    _patch_pg_hba()

    run(
        f"sudo -u postgres psql -c \""
        f"DO \\$\\$ BEGIN "
        f"IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{DB_USER}') THEN "
        f"CREATE ROLE {DB_USER} LOGIN PASSWORD '{DB_PASSWORD}'; "
        f"END IF; END \\$\\$;\""
    )

    result = run(
        f"sudo -u postgres psql -tc "
        f"\"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'\"",
        check=False,
    )
    if "1" not in result.stdout:
        run(f"sudo -u postgres psql -c \"CREATE DATABASE {DB_NAME} OWNER {DB_USER}\"")

    run(
        f"sudo -u postgres psql -c "
        f"\"GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER}\""
    )
    print("  [OK] Database ready")


def _patch_pg_hba():
    """Ensure md5/scram auth for local connections on RHEL which defaults to ident."""
    import glob, os
    patterns = [
        "/etc/postgresql/*/main/pg_hba.conf",
        "/var/lib/pgsql/data/pg_hba.conf",
        "/var/lib/pgsql/*/data/pg_hba.conf",
    ]
    for pattern in patterns:
        for path in glob.glob(pattern):
            with open(path) as f:
                content = f.read()
            # If ident is the only method, switch to md5
            if "ident" in content and "md5" not in content:
                content = content.replace(
                    "host    all             all             127.0.0.1/32            ident",
                    "host    all             all             127.0.0.1/32            md5",
                ).replace(
                    "host    all             all             ::1/128                 ident",
                    "host    all             all             ::1/128                 md5",
                )
                with open(path, "w") as f:
                    f.write(content)
                run("systemctl reload postgresql", check=False)
            break


def setup(skip_if_installed: bool = True):
    if skip_if_installed and is_installed():
        print("  [SKIP] PostgreSQL already installed")
        setup_database()
        return
    install_postgres()
    setup_database()
