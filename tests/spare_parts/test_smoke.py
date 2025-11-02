"""Smoke tests for the spare parts module."""

from io import BytesIO

from modules.spare_parts.models import Part


def _authenticate(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_login_page_available(client) -> None:
    response = client.get("/parts/login")
    assert response.status_code == 200


def test_add_part_flow(client, app, root_user) -> None:
    _authenticate(client, root_user.id)

    response = client.post(
        "/parts/add",
        data={
            "sap_code": "SAP-001",
            "part_number": "PN-001",
            "name": "Test Part",
            "description": "Test description",
            "category": "Test",
            "equipment_code": "EQ-1",
            "location": "Warehouse",
            "manufacturer": "ACME",
            "analog_group": "GroupA",
            "photo": (BytesIO(b"fake data"), "photo.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/parts/")

    with app.app_context():
        assert Part.query.filter_by(sap_code="SAP-001").one_or_none() is not None
