"""Las pruebas hablan con la API levantada por HTTP, igual que un cliente, contra PostgreSQL y Redis reales.

Requieren el entorno arriba: docker compose up --build --wait
"""

import os
import subprocess
from pathlib import Path

import httpx
import pytest

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
PROJECT_DIR = Path(__file__).resolve().parent.parent


def run_compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=PROJECT_DIR, check=True, capture_output=True)


@pytest.fixture
def compose():
    """Permite a una prueba manejar los servicios: compose("stop", "redis")."""
    return run_compose


@pytest.fixture(autouse=True)
def fresh_counters():
    # Cada prueba empieza sin contadores, así ninguna recibe un 429 por culpa de otra.
    # Vaciar Redis es seguro: solo guarda los contadores del rate limit.
    run_compose("exec", "-T", "redis", "redis-cli", "FLUSHALL")


@pytest.fixture
def client():
    with httpx.Client(base_url=API_URL, timeout=10) as http:
        yield http
