import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_DSN

_pool: pool.ThreadedConnectionPool = None


def init_pool(minconn: int = 2, maxconn: int = 10):
    global _pool
    _pool = pool.ThreadedConnectionPool(minconn, maxconn, DATABASE_DSN)


def get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        init_pool()
    return _pool


@contextmanager
def get_db():
    conn = get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        get_pool().putconn(conn)


def close_pool():
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
