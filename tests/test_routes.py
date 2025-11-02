def test_index_route(client, root_user):
    with client.session_transaction() as session:
        session["_user_id"] = str(root_user.id)
        session["_fresh"] = True

    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome" in response.data  # Предполагается, что на главной странице есть слово "Welcome"
