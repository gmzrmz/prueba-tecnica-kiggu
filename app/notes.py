"""Endpoints del CRUD de notas. Pydantic valida lo que entra; si algo no cumple, FastAPI responde 422."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app import repository
from app.rate_limit import rate_limit

router = APIRouter(prefix="/notes", tags=["notes"], dependencies=[Depends(rate_limit)])


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=10_000)


class Note(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Nota no encontrada")


@router.post("", status_code=201, response_model=Note)
def create_note(note: NoteIn):
    return repository.create_note(note.title, note.content)


@router.get("", response_model=list[Note])
def list_notes(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    return repository.list_notes(limit, offset)


@router.get("/{note_id}", response_model=Note)
def get_note(note_id: int):
    note = repository.get_note(note_id)
    if note is None:
        raise not_found()
    return note


@router.put("/{note_id}", response_model=Note)
def update_note(note_id: int, note: NoteIn):
    updated = repository.update_note(note_id, note.title, note.content)
    if updated is None:
        raise not_found()
    return updated


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int) -> None:
    if not repository.delete_note(note_id):
        raise not_found()
