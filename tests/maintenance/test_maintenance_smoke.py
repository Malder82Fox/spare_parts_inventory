from uuid import uuid4

def _authenticate(client, user_id: int) -> None:
    with client.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True

def test_equipment_list_access(client, root_user):
    _authenticate(client, root_user.id)
    resp = client.get("/maintenance/equipment")
    assert resp.status_code in (200, 302, 303)

def test_equipment_creation(client, root_user):
    _authenticate(client, root_user.id)
    uniq = uuid4().hex[:6]
    resp = client.post(
        "/maintenance/equipment/add",
        data={
            "code": f"EQ-{uniq}",
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
    assert resp.status_code in (302, 303)
