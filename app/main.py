"""Punto de entrada de la API: crea la app, registra las rutas y abre o cierra las conexiones."""

from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import health, notes
from app.db import pool, redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()
    redis_client.close()


app = FastAPI(title="Notes API", version="1.0.0", lifespan=lifespan)
app.include_router(notes.router)
app.include_router(health.router)


# Si PostgreSQL no responde, devolvemos un 503 claro en vez de un 500 genérico.
@app.exception_handler(psycopg.OperationalError)
def database_unavailable(request: Request, exc: psycopg.OperationalError) -> JSONResponse:
    return JSONResponse({"detail": "Base de datos no disponible"}, status_code=503)
