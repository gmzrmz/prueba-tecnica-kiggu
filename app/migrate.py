"""Aplica en orden los archivos de migrations/ que falten. Corre antes de arrancar la API.

En la tabla schema_migrations anota cuáles ya aplicó, así que correrlo varias veces es seguro.
"""

from pathlib import Path

import psycopg

from app import config

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
LOCK_ID = 1  # número arbitrario que identifica el candado de migraciones


def main() -> None:
    with psycopg.connect(config.DATABASE_URL, autocommit=True, connect_timeout=2) as conn:
        # Candado: si dos instancias arrancan a la vez, la segunda espera aquí hasta que la primera termine.
        # Se libera solo al cerrar la conexión.
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))

        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version TEXT PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            # Cada migración va en su propia transacción: se aplica completa o no se aplica.
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            print(f"Migración aplicada: {path.name}")


if __name__ == "__main__":
    main()
