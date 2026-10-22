"""Consultas SQL de las notas. Siempre con parámetros (%s), nunca concatenando texto: así no hay inyección SQL."""

from app.db import pool


def create_note(title: str, content: str) -> dict:
    with pool.connection() as conn:
        return conn.execute(
            "INSERT INTO notes (title, content) VALUES (%s, %s)"
            " RETURNING id, title, content, created_at, updated_at",
            (title, content),
        ).fetchone()


def list_notes(limit: int, offset: int) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes"
            " ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        ).fetchall()


def get_note(note_id: int) -> dict | None:
    with pool.connection() as conn:
        return conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = %s",
            (note_id,),
        ).fetchone()


def update_note(note_id: int, title: str, content: str) -> dict | None:
    with pool.connection() as conn:
        return conn.execute(
            "UPDATE notes SET title = %s, content = %s, updated_at = now() WHERE id = %s"
            " RETURNING id, title, content, created_at, updated_at",
            (title, content, note_id),
        ).fetchone()


def delete_note(note_id: int) -> bool:
    with pool.connection() as conn:
        return conn.execute("DELETE FROM notes WHERE id = %s", (note_id,)).rowcount == 1
