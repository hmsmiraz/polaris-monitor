import threading
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import register, heartbeat, metrics, alerts, nodes, status
from database.connection import init_pool, close_pool
from database.schema import create_tables
from services.node_service import mark_stale_nodes_offline

app = FastAPI(
    title="Polaris Master Agent",
    description="Server Monitoring & Node Management Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"
app.include_router(register.router, prefix=PREFIX, tags=["Registration"])
app.include_router(heartbeat.router, prefix=PREFIX, tags=["Heartbeat"])
app.include_router(metrics.router,   prefix=PREFIX, tags=["Metrics"])
app.include_router(alerts.router,    prefix=PREFIX, tags=["Alerts"])
app.include_router(nodes.router,     prefix=PREFIX, tags=["Nodes"])
app.include_router(status.router,    prefix=PREFIX, tags=["Status"])


def _offline_detector():
    from config import HEARTBEAT_TIMEOUT
    while True:
        try:
            count = mark_stale_nodes_offline(HEARTBEAT_TIMEOUT)
            if count:
                print(f"[offline-detector] Marked {count} node(s) offline")
        except Exception as e:
            print(f"[offline-detector] Error: {e}")
        time.sleep(30)


@app.on_event("startup")
def startup():
    init_pool()
    create_tables()
    t = threading.Thread(target=_offline_detector, daemon=True, name="offline-detector")
    t.start()
    print("[API] Polaris Master Agent started")


@app.on_event("shutdown")
def shutdown():
    close_pool()


@app.get("/")
def root():
    return {
        "service": "Polaris Master Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api/v1",
    }
