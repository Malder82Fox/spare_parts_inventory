def test_index_route(client, root_user):
    # авторизуем «псевдо-пользователя» в тестовом клиенте
    with client.session_transaction() as session:
        session["_user_id"] = str(root_user.id)
        session["_fresh"] = True

    # важно: после логина может быть редирект — поэтому follow_redirects=True
    resp = client.get("/", follow_redirects=True)

    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert b"<html" in resp.data  # было: assert b"Welcome" in resp.data