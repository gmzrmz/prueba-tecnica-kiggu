"""Clientes de PostgreSQL y Redis, compartidos por toda la API."""

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from redis import Redis

from app import config

# Pool de conexiones: reutiliza conexiones abiertas en vez de abrir una por petición.
# Se abre al arrancar la API (ver main.py).
pool = ConnectionPool(
    config.DATABASE_URL,
    min_size=1,
    max_size=5,
    timeout=2,  # segundos máximos esperando una conexión libre
    kwargs={"connect_timeout": 2, "row_factory": dict_row},  # filas como diccionarios
    open=False,
)

# Timeouts cortos: si Redis se cuelga, preferimos un error rápido a una espera larga.
redis_client = Redis.from_url(config.REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
