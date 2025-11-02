def _authenticate(client, user_id: int) -> None:
    with client.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True

def test_tooling_list_access(client, root_user):
    _authenticate(client, root_user.id)
    resp = client.get("/tooling/")
    assert resp.status_code in (200, 302, 303)

def test_tooling_creation(client, root_user):
    _authenticate(client, root_user.id)
    resp = client.post(
        "/tooling/new",
        data={
            "tool_code": "BATCH-001",
            "type_code": "GENERIC",
            "role": "IRONING",
            "position": "#1",
            "shift": "TOOL ROOM",
            "reason": "New",
            "dimension": "12.3",
        },
        follow_redirects=False,
    )
    # успешный POST обычно уводит на список
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith(("/tooling/", "/tooling/new"))
