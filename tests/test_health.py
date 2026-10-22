def test_health_ok_con_todo_arriba(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"postgres": "ok", "redis": "ok"}
