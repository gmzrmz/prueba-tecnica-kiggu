import pytest

MISSING_ID = 999_999_999


def create_note(client, title="Título", content="Contenido") -> dict:
    response = client.post("/notes", json={"title": title, "content": content})
    assert response.status_code == 201
    return response.json()


def test_crear_y_leer(client):
    note = create_note(client, "Compras", "pan y leche")

    response = client.get(f"/notes/{note['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Compras"
    assert response.json()["content"] == "pan y leche"


def test_reemplazar(client):
    note = create_note(client)

    response = client.put(f"/notes/{note['id']}", json={"title": "Nuevo", "content": "otro"})

    assert response.status_code == 200
    assert response.json()["title"] == "Nuevo"
    assert response.json()["updated_at"] > note["updated_at"]


def test_borrar(client):
    note = create_note(client)

    assert client.delete(f"/notes/{note['id']}").status_code == 204
    assert client.get(f"/notes/{note['id']}").status_code == 404


def test_listar_respeta_limit(client):
    create_note(client)
    create_note(client)

    response = client.get("/notes", params={"limit": 1})

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("GET", f"/notes/{MISSING_ID}", None),
        ("PUT", f"/notes/{MISSING_ID}", {"title": "x"}),
        ("DELETE", f"/notes/{MISSING_ID}", None),
    ],
)
def test_nota_inexistente_da_404(client, method, path, body):
    response = client.request(method, path, json=body)

    assert response.status_code == 404
    assert response.json() == {"detail": "Nota no encontrada"}


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("POST", "/notes", {"title": ""}),  # título vacío
        ("POST", "/notes", {"title": "x" * 201}),  # título demasiado largo
        ("POST", "/notes", {"content": "sin título"}),  # falta el título
        ("GET", "/notes?limit=101", None),  # más de 100 por página
        ("GET", "/notes/abc", None),  # el id no es un número
    ],
)
def test_entrada_invalida_da_422(client, method, path, body):
    response = client.request(method, path, json=body)

    assert response.status_code == 422
