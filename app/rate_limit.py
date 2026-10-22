"""Rate limiting por IP con ventana fija de un minuto, guardado en Redis para que lo compartan todas las instancias."""

import logging
import time

from fastapi import HTTPException, Request
from redis.exceptions import RedisError

from app import config
from app.db import redis_client

logger = logging.getLogger(__name__)


def rate_limit(request: Request) -> None:
    # Una clave por IP y por minuto: cada minuto empieza un contador nuevo.
    minute = int(time.time() // 60)
    key = f"rl:{request.client.host}:{minute}"

    try:
        # El pipeline envía INCR y EXPIRE juntos, en una transacción: se ejecutan los dos o ninguno.
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 60)
        count, _ = pipe.execute()
    except RedisError:
        # Fail-open: si Redis falla, dejamos pasar la petición. /health reporta el problema.
        logger.warning("Redis no responde; la petición pasa sin rate limit")
        return

    if count > config.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Demasiadas peticiones; intenta de nuevo en un minuto")
