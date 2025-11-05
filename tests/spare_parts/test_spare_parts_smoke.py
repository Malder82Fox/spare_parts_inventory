from uuid import uuid4
from io import BytesIO

def _authenticate(client, user_id: int) -> None:
    with client.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True

def test_add_part_flow(client, root_user):
    _authenticate(client, root_user.id)
    uniq = uuid4().hex[:6]
    resp = client.post(
        "/parts/add",
        data={
            "sap_code": f"SAP-{uniq}",
            "part_number": f"PN-{uniq}",
            "name": "Test Part",
            "description": "Test description",
            "category": "Test",
            "equipment_code": "EQ-1",
            "location": "Warehouse",
            "manufacturer": "ACME",
            "analog_group": "GroupA",
            "photo": (BytesIO(b"fake"), "photo.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
