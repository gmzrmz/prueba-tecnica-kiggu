"""/health comprueba las dependencias reales: responde 200 si PostgreSQL y Redis están bien, 503 si alguno falla."""

import psycopg
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.db import pool, redis_client

router = APIRouter(tags=["health"])


def check_postgres() -> str:
    try:
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        return "ok"
    except psycopg.Error:
        return "error"


def check_redis() -> str:
    try:
        redis_client.ping()
        return "ok"
    except RedisError:
        return "error"


@router.get("/health")
def health():
    checks = {"postgres": check_postgres(), "redis": check_redis()}
    healthy = all(status == "ok" for status in checks.values())
    return JSONResponse(checks, status_code=200 if healthy else 503)
