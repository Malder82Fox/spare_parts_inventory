"""Smoke tests for the tooling module."""

from modules.tooling.models import Tooling


def _authenticate(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_tooling_list_access(client, root_user) -> None:
    _authenticate(client, root_user.id)

    response = client.get("/tooling/")
    assert response.status_code == 200


def test_tooling_creation(client, app, root_user) -> None:
    _authenticate(client, root_user.id)

    response = client.post(
        "/tooling/new",
        data={
            "tool_code": "BATCH-001",
            "type_code": "GENERIC",
            "role": "IRONING",
            "dimension": "12.3",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/tooling/")

    with app.app_context():
        assert Tooling.query.filter_by(tool_code="BATCH-001").one_or_none() is not None
