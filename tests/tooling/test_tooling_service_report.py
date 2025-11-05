from __future__ import annotations

from decimal import Decimal

import pytest

from extensions import db
from modules.maintenance.models import Equipment
from modules.tooling.models import ToolType, Tooling, ToolingEvent


@pytest.fixture()
def tooling_objects(app):
    with app.app_context():
        equipment = Equipment(code="BM-001", name="BM-001")
        tool_type = ToolType(code="GENERIC", name="Generic")
        db.session.add_all([equipment, tool_type])
        db.session.flush()

        tool_a = Tooling(
            tool_code="BATCH-A",
            tool_type_id=tool_type.id,
            intended_role="IRONING",
            current_diameter=Decimal("63.100"),
        )
        tool_b = Tooling(
            tool_code="BATCH-B",
            tool_type_id=tool_type.id,
            intended_role="IRONING",
            current_diameter=Decimal("63.050"),
        )
        db.session.add_all([tool_a, tool_b])
        db.session.commit()

        return {
            "equipment_id": equipment.id,
            "tool_a_id": tool_a.id,
            "tool_b_id": tool_b.id,
            "tool_a_batch": tool_a.tool_code,
            "tool_b_batch": tool_b.tool_code,
        }


def _post_install(client, equipment_id: int, batch: str, reason: str, *, dim: str = "63.100"):
    return client.post(
        "/tooling/event",
        data={
            "batch_no": batch,
            "action": "INSTALL",
            "machine_id": str(equipment_id),
            "shift": "A",
            "role": "IRONING",
            "position": "#1",
            "reason": reason,
            "dimension": dim,
        },
        follow_redirects=False,
    )


def _post_service_action(
    client,
    batch: str,
    action: str,
    *,
    back: str | None = None,
    reason: str | None = None,
    dimension: str | None = None,
    new_dimension: str | None = None,
):
    data = {
        "batch_no": batch,
        "action": action,
    }
    if back:
        data["back"] = back
    if reason:
        data["reason"] = reason
    if dimension is not None:
        data["dimension"] = dimension
    if new_dimension is not None:
        data["new_dimension"] = new_dimension
    return client.post(
        "/tooling/event",
        data=data,
        query_string={"back": back} if back else None,
        follow_redirects=False,
    )


def _prepare_need_service(client, objs):
    resp = _post_install(client, objs["equipment_id"], objs["tool_a_batch"], "Trial")
    assert resp.status_code in (302, 303)
    resp = _post_install(
        client,
        objs["equipment_id"],
        objs["tool_b_batch"],
        "Top wall oversize",
        dim="63.040",
    )
    assert resp.status_code in (302, 303)


def test_auto_remove_reason_and_service_report(client, app, tooling_objects):
    _prepare_need_service(client, tooling_objects)

    with app.app_context():
        tool_a = Tooling.query.get(tooling_objects["tool_a_id"])
        assert tool_a is not None
        last_event = tool_a.last_event
        assert last_event is not None
        assert last_event.action == "REMOVE"
        assert last_event.to_status == "NEED_SERVICE"
        assert last_event.reason == "Top wall oversize"
        agg = tool_a.last_aggregate()
        assert agg["REASON"] == "Top wall oversize"

        install_event = (
            ToolingEvent.query.filter_by(tool_id=tooling_objects["tool_a_id"], action="INSTALL")
            .order_by(ToolingEvent.happened_at.asc())
            .first()
        )
        assert install_event is not None
        assert install_event.reason == "Trial"

        tool_b_event = Tooling.query.get(tooling_objects["tool_b_id"]).last_event
        assert tool_b_event is not None
        assert tool_b_event.action == "INSTALL"
        assert tool_b_event.reason is None

    report = client.get("/tooling/report/service")
    assert report.status_code == 200
    body = report.get_data(as_text=True)
    assert tooling_objects["tool_a_batch"] in body
    assert "Top wall oversize" in body
    assert tooling_objects["tool_b_batch"] not in body


def test_service_actions_move_to_stock_and_redirect_back(client, app, tooling_objects):
    _prepare_need_service(client, tooling_objects)

    resp = _post_service_action(
        client,
        tooling_objects["tool_a_batch"],
        "WASH",
        back="service_report",
        reason="Cleaned",
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith("/tooling/report/service")

    with app.app_context():
        tool_a = Tooling.query.get(tooling_objects["tool_a_id"])
        assert tool_a is not None
        last_event = tool_a.last_event
        assert last_event.action == "WASH"
        assert last_event.to_status == "STOCK"
        assert last_event.reason == "Cleaned"
        assert tool_a.last_aggregate()["STATUS"] == "STOCK"

    report = client.get("/tooling/report/service")
    body = report.get_data(as_text=True)
    assert tooling_objects["tool_a_batch"] not in body


def test_regrind_respects_back_and_updates_dimension(client, app, tooling_objects):
    _prepare_need_service(client, tooling_objects)

    resp = _post_service_action(
        client,
        tooling_objects["tool_a_batch"],
        "REGRIND",
        back="service_report",
        reason="Regrind complete",
        dimension="63.000",
        new_dimension="62.950",
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["Location"].endswith("/tooling/report/service")

    with app.app_context():
        tool_a = Tooling.query.get(tooling_objects["tool_a_id"])
        assert tool_a is not None
        last_event = tool_a.last_event
        assert last_event.action == "REGRIND"
        assert last_event.to_status == "STOCK"
        assert last_event.new_dimension == Decimal("62.950")
        assert tool_a.current_diameter == Decimal("62.950")
        assert tool_a.last_aggregate()["STATUS"] == "STOCK"

    report = client.get("/tooling/report/service")
    body = report.get_data(as_text=True)
    assert tooling_objects["tool_a_batch"] not in body
