from database.connection import get_db

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS join_tokens (
    id          SERIAL PRIMARY KEY,
    token       VARCHAR(255) UNIQUE NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS nodes (
    id                  SERIAL PRIMARY KEY,
    agent_id            VARCHAR(64) UNIQUE NOT NULL,
    hostname            VARCHAR(255),
    private_ip          VARCHAR(50),
    public_ip           VARCHAR(50),
    os_info             VARCHAR(255),
    kernel_version      VARCHAR(255),
    node_exporter_port  INTEGER DEFAULT 9100,
    status              VARCHAR(20) DEFAULT 'offline',
    registered_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id          SERIAL PRIMARY KEY,
    agent_id    VARCHAR(64) REFERENCES nodes(agent_id) ON DELETE CASCADE,
    alert_type  VARCHAR(100),
    message     TEXT,
    severity    VARCHAR(20) DEFAULT 'warning',
    resolved    BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    agent_id    VARCHAR(64) REFERENCES nodes(agent_id) ON DELETE CASCADE,
    event_type  VARCHAR(100),
    message     TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metrics_summary (
    id              SERIAL PRIMARY KEY,
    agent_id        VARCHAR(64) REFERENCES nodes(agent_id) ON DELETE CASCADE,
    cpu_percent     FLOAT,
    memory_percent  FLOAT,
    disk_percent    FLOAT,
    load_avg_1      FLOAT,
    uptime_seconds  BIGINT,
    recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
CREATE INDEX IF NOT EXISTS idx_alerts_agent_id ON alerts(agent_id);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_metrics_agent_id ON metrics_summary(agent_id);
"""


def create_tables():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
    print("[OK] Database tables created")
