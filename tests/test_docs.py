def test_openapi_describe_todos_los_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths) == {"/notes", "/notes/{note_id}", "/health"}


def test_swagger_ui_disponible(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text
