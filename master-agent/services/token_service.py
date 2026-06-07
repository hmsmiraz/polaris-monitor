import secrets
import string
from datetime import datetime, timedelta
from database.connection import get_db


def generate_token(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_token(expires_in_days: int = None) -> str:
    token = generate_token()
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO join_tokens (token, expires_at, is_active)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (token) DO NOTHING
                """,
                (token, expires_at),
            )
    return token


def validate_token(token: str) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM join_tokens
                WHERE token = %s
                  AND is_active = TRUE
                  AND (expires_at IS NULL OR expires_at > NOW())
                """,
                (token,),
            )
            return cur.fetchone() is not None


def revoke_token(token: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE join_tokens SET is_active = FALSE WHERE token = %s",
                (token,),
            )


def get_active_tokens() -> list:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT token, created_at, expires_at
                FROM join_tokens
                WHERE is_active = TRUE
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()
            return [
                {"token": r[0], "created_at": r[1], "expires_at": r[2]}
                for r in rows
            ]
