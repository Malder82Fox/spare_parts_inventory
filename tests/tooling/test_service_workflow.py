import pytest

from extensions import db
from modules.maintenance.models import Equipment
from modules.tooling.models import (
    Tooling,
    ToolType,
    ToolingEvent,
    install_tool,
)


@pytest.fixture()
def tool_type(app):
    with app.app_context():
        existing = ToolType.query.filter_by(code="GENERIC").first()
        if existing:
            return existing
        ttype = ToolType(code="GENERIC", name="Generic")
        db.session.add(ttype)
        db.session.commit()
        return ttype


@pytest.fixture()
def equipment(app):
    with app.app_context():
        eq = Equipment(code="BM-01", name="BM-01")
        db.session.add(eq)
        db.session.commit()
        return eq


def _create_tool(tool_code: str, tool_type_id: int, dim: float | None = None) -> Tooling:
    tool = Tooling(tool_code=tool_code, tool_type_id=tool_type_id, current_diameter=dim)
    db.session.add(tool)
    db.session.commit()
    return tool


def _setup_need_service_tool(
    tool_type_id: int,
    equipment: Equipment,
    *,
    initial_dim: float = 63.0,
    prefix: str = "BATCH",
) -> Tooling:
    tool_old = _create_tool(f"{prefix}-OLD", tool_type_id, dim=initial_dim)
    tool_new = _create_tool(f"{prefix}-NEW", tool_type_id, dim=initial_dim)
    install_tool(tool=tool_old, equipment=equipment, role="IRONING", position="#1", shift="A", reason="NEW", dim=initial_dim)
    db.session.commit()
    install_tool(tool=tool_new, equipment=equipment, role="IRONING", position="#1", shift="A", reason="Top wall variation", dim=initial_dim)
    db.session.commit()
    return Tooling.query.get(tool_old.id)


def test_service_report_includes_auto_removed_tool(client, app, tool_type, equipment):
    with app.app_context():
        tool = _setup_need_service_tool(tool_type.id, equipment, prefix="SR")
        resp = client.get("/tooling/report/service")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "SR-OLD" in body
        assert "Top wall variation" in body
        assert "SR-NEW" not in body

        last_event = tool.last_event
        assert last_event.action == "REMOVE"
        assert last_event.to_status == "NEED_SERVICE"
        assert last_event.reason == "Top wall variation"


def test_service_action_inspect_restores_tool(client, app, tool_type, equipment):
    with app.app_context():
        tool = _setup_need_service_tool(tool_type.id, equipment, prefix="INSP")

    response = client.post(f"/tooling/service/{tool.id}/action", data={"action": "INSPECT", "note": "Checked"})
    assert response.status_code in (302, 303)

    with app.app_context():
        updated_tool = Tooling.query.get(tool.id)
        last_event = updated_tool.last_event
        assert last_event.action == "INSPECT"
        assert last_event.to_status == "STOCK"
        assert last_event.new_dimension is None
        assert pytest.approx(float(last_event.dimension)) == pytest.approx(63.0)
        assert pytest.approx(updated_tool.current_dim or 0.0) == pytest.approx(63.0)

        report_html = client.get("/tooling/report/service").get_data(as_text=True)
        assert "INSP-OLD" not in report_html


def test_service_action_regrind_updates_dimension(client, app, tool_type, equipment):
    with app.app_context():
        tool = _setup_need_service_tool(tool_type.id, equipment, initial_dim=62.5, prefix="RGR")
        initial_event_count = ToolingEvent.query.filter_by(tool_id=tool.id).count()

    missing_dim_resp = client.post(f"/tooling/service/{tool.id}/action", data={"action": "REGRIND", "note": "Need precise size"})
    assert missing_dim_resp.status_code in (302, 303)

    with app.app_context():
        assert ToolingEvent.query.filter_by(tool_id=tool.id).count() == initial_event_count

    response = client.post(
        f"/tooling/service/{tool.id}/action",
        data={"action": "REGRIND", "note": "Resharpened", "new_dim": "63,750"},
    )
    assert response.status_code in (302, 303)

    with app.app_context():
        refreshed_tool = Tooling.query.get(tool.id)
        last_event = refreshed_tool.last_event
        assert last_event.action == "REGRIND"
        assert last_event.to_status == "STOCK"
        assert last_event.reason == "Regrind"
        assert pytest.approx(float(last_event.dimension)) == pytest.approx(62.5)
        assert pytest.approx(float(last_event.new_dimension)) == pytest.approx(63.75)
        assert pytest.approx(refreshed_tool.current_dim or 0.0) == pytest.approx(63.75)
        assert refreshed_tool.regrind_count == 1

        history = refreshed_tool.dim_history()
        assert len(history) == 1
        assert pytest.approx(history[0]["before"] or 0.0) == pytest.approx(62.5)
        assert pytest.approx(history[0]["after"] or 0.0) == pytest.approx(63.75)

        # second regrind to check ordering
        refreshed_tool.mark_serviced(action="REGRIND", new_dim=64.0, note="Second pass")
        db.session.commit()
        history = refreshed_tool.dim_history()
        assert len(history) == 2
        assert history[0]["after"] < history[1]["after"]


def test_service_pages_show_back_links(client, app, tool_type, equipment):
    with app.app_context():
        tool = _setup_need_service_tool(tool_type.id, equipment, prefix="BACK")

    detail_resp = client.get(f"/tooling/{tool.id}?from_service=1")
    assert "Назад к отчёту по сервису" in detail_resp.get_data(as_text=True)

    event_resp = client.get("/tooling/event?from_service=1")
    html = event_resp.get_data(as_text=True)
    assert "Назад к отчёту по сервису" in html
    assert 'name="from_service" value="1"' in html


def test_install_requires_all_fields(client, app, tool_type, equipment):
    with app.app_context():
        _create_tool("BATCH-INSTALL", tool_type.id, dim=63.0)

    response = client.post(
        "/tooling/event",
        data={
            "batch_no": "BATCH-INSTALL",
            "action": "INSTALL",
            "machine_id": str(equipment.id),
            "role": "IRONING",
            "position": "#1",
            "reason": "New",
            "dimension": "63.0",
        },
        follow_redirects=False,
    )
    # отсутствует SHIFT → возврат на форму
    assert response.status_code in (302, 303)
    assert response.headers["Location"].endswith("/tooling/event")

    response_with_shift = client.post(
        "/tooling/event",
        data={
            "batch_no": "BATCH-INSTALL",
            "action": "INSTALL",
            "machine_id": str(equipment.id),
            "role": "IRONING",
            "position": "#1",
            "reason": "New",
            "dimension": "63.0",
            "shift": "A",
        },
        follow_redirects=False,
    )
    assert response_with_shift.status_code in (302, 303)
    assert response_with_shift.headers["Location"].endswith("/tooling/")
