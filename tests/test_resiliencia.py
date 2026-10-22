"""Pruebas que alteran el entorno. Cada fixture lo deja como estaba, aunque la prueba falle."""

import pytest

RATE_LIMIT_PER_MINUTE = 100  # el mismo valor que compose.yaml


@pytest.fixture
def redis_stopped(compose):
    compose("stop", "redis")
    yield
    compose("up", "--wait")  # vuelve a levantarlo y espera a que todo esté sano


@pytest.fixture
def postgres_stopped(compose):
    compose("stop", "postgres")
    yield
    compose("up", "--wait")


def test_rate_limit_responde_429(client):
    # Pedimos hasta ver un 429. El tope es el doble del límite porque, si el minuto cambia
    # a mitad de la prueba, el contador vuelve a empezar.
    for _ in range(2 * RATE_LIMIT_PER_MINUTE + 1):
        status = client.get("/notes").status_code
        if status == 429:
            break

    assert status == 429
    assert client.get("/health").status_code == 200  # /health no tiene rate limit


def test_sin_redis_la_api_sigue_atendiendo(client, redis_stopped):
    health = client.get("/health")

    assert health.status_code == 503
    assert health.json() == {"postgres": "ok", "redis": "error"}
    assert client.get("/notes").status_code == 200  # fail-open


def test_sin_postgres_responde_503(client, postgres_stopped):
    assert client.get("/health").status_code == 503
    assert client.get("/notes").json() == {"detail": "Base de datos no disponible"}
