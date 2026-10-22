"""Toda la configuración llega por variables de entorno: el mismo código corre en local y en producción."""

import os

# Obligatorias: si faltan, la API no arranca (mejor fallar al inicio que a mitad de una petición).
DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
