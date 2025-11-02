"""Smoke tests for the maintenance module."""

from modules.maintenance.models import Equipment


def _authenticate(client, user_id: int) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_equipment_list_access(client, root_user) -> None:
    _authenticate(client, root_user.id)

    response = client.get("/maintenance/equipment")
    assert response.status_code == 200


def test_equipment_creation(client, app, root_user) -> None:
    _authenticate(client, root_user.id)

    response = client.post(
        "/maintenance/equipment/add",
        data={
            "code": "EQ-001",
            "name": "Bodymaker",
            "category": "Category",
            "location": "Line A",
            "vendor": "Vendor",
            "model": "Model",
            "serial_number": "SN123",
            "sap_number": "SAP123",
            "notes": "Test equipment",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/maintenance/equipment")

    with app.app_context():
        assert Equipment.query.filter_by(code="EQ-001").one_or_none() is not None
