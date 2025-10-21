# tooling/routes_tooling.py
# -*- coding: utf-8 -*-

from datetime import datetime
from decimal import Decimal, InvalidOperation
import io
import csv

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, make_response, session
)
from flask_login import login_required, current_user
from sqlalchemy import desc

from extensions import db
from maintenance_models import Equipment
from tooling.models_tooling import (
    Tooling, ToolType, ToolingEvent,
    ALLOWED_ACTIONS, ALLOWED_SHIFTS, ALLOWED_ROLES, ALLOWED_POSITIONS,
    install_tool, remove_tool, regrind_tool,
)
from permissions import role_required

# Глобальные шаблоны из /templates, поэтому без template_folder
tooling_bp = Blueprint("tooling", __name__)


# ----------------------------- ВСПОМОГАТЕЛЬНОЕ ----------------------------- #
def _parse_num(s: str | None):
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _remember_list_url():
    """
    Запоминаем последний URL списка, чтобы 'Назад' в карточке вел туда же
    (с теми же фильтрами/пагинацией, если они есть).
    """
    # request.full_path сохраняет query string
    session["tooling_back_url"] = request.full_path or request.url


def _get_back_url(default_endpoint="tooling.list_tooling"):
    return session.get("tooling_back_url") or url_for(default_endpoint)


# --------------------------------- СПИСОК ---------------------------------- #
@tooling_bp.route("/")
@login_required
def list_tooling():
    """Агрегированная витрина."""
    _remember_list_url()

    tools = Tooling.query.filter_by(is_active=True).order_by(desc(Tooling.updated_at)).all()

    rows = []
    for t in tools:
        a = t.last_aggregate()  # dict: BATCH #, LAST DATE, ...
        a["id"] = t.id          # для ссылки на карточку
        rows.append(a)

    return render_template("tooling/list_tooling.html", rows=rows)


# -------------------------------- КАРТОЧКА --------------------------------- #
@tooling_bp.route("/<int:tool_id>")
@login_required
def tooling_detail(tool_id: int):
    """Карточка BATCH # с историей + навигация Prev/Next/Back."""
    item = Tooling.query.get_or_404(tool_id)
    events = (ToolingEvent.query
              .filter_by(tool_id=tool_id)
              .order_by(ToolingEvent.happened_at.desc())
              .all())

    # порядок как в списке: updated_at desc
    ordered = Tooling.query.filter_by(is_active=True).order_by(desc(Tooling.updated_at)).all()
    ids = [t.id for t in ordered]
    idx = ids.index(tool_id) if tool_id in ids else -1
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if idx != -1 and idx < len(ids) - 1 else None

    back_url = _get_back_url()

    return render_template("tooling/tooling_detail.html",
                           item=item, events=events,
                           prev_id=prev_id, next_id=next_id,
                           back_url=back_url)


# ----------------------- СОЗДАНИЕ НОВОГО BATCH # --------------------------- #
@tooling_bp.route("/new", methods=["GET", "POST"])
@role_required(["admin", "root"])
def tooling_new():
    """
    Минимум: BATCH # (обяз.), ROLE (желательно), DIM (желательно).
    type_code — опц., если пусто — 'GENERIC'.
    """
    if request.method == "POST":
        code = (request.form.get("tool_code") or "").strip()             # BATCH #
        type_code = (request.form.get("type_code") or "GENERIC").strip() # опционально
        role = (request.form.get("role") or "").strip() or None
        dim = _parse_num(request.form.get("dimension"))

        if not code:
            flash("Укажи BATCH #.", "warning")
            return redirect(url_for("tooling.tooling_new"))

        # upsert типа
        ttype = ToolType.query.filter_by(code=type_code).first()
        if not ttype:
            ttype = ToolType(code=type_code, name=type_code)
            db.session.add(ttype)
            db.session.flush()

        # уникальность
        if Tooling.query.filter_by(tool_code=code).first():
            flash("Инструмент с таким BATCH # уже существует.", "warning")
            return redirect(url_for("tooling.tooling_new"))

        tool = Tooling(
            tool_code=code,
            tool_type_id=ttype.id,
            intended_role=role,
            current_diameter=float(dim) if dim is not None else None
        )
        db.session.add(tool)
        db.session.flush()  # чтобы tool.id уже был

        # событие CREATE (фиксируем стартовый DIM/ROLE)
        ev = ToolingEvent(
            user_name=getattr(current_user, "username", "system"),
            action="CREATE",
            to_status="STOCK",
            tool_id=tool.id,
            batch_no=tool.tool_code,
            happened_at=datetime.utcnow(),
            role=role,
            dimension=dim
        )
        db.session.add(ev)
        db.session.commit()

        flash("BATCH # создан.", "success")
        return redirect(url_for("tooling.list_tooling"))

    return render_template("tooling/tooling_new.html", roles=ALLOWED_ROLES)


# ----------------------- УНИВЕРСАЛЬНАЯ ФОРМА СОБЫТИЯ ----------------------- #
@tooling_bp.route("/event", methods=["GET", "POST"])
@login_required
def tooling_event():
    actions = ALLOWED_ACTIONS
    shifts = ALLOWED_SHIFTS
    roles = ALLOWED_ROLES
    positions = ALLOWED_POSITIONS
    machines = Equipment.query.order_by(Equipment.name.asc()).all()

    if request.method == "POST":
        batch = (request.form.get("batch_no") or "").strip()
        action = request.form.get("action")
        shift = request.form.get("shift") or None
        machine_id = request.form.get("machine_id")
        role = request.form.get("role") or None
        position = request.form.get("position") or None
        reason = request.form.get("reason") or None
        note = request.form.get("note") or None
        dim = _parse_num(request.form.get("dimension"))
        new_dim = _parse_num(request.form.get("new_dimension"))

        if not batch or action not in actions:
            flash("Укажи BATCH # и корректный ACTION.", "warning")
            return redirect(url_for("tooling.tooling_event"))

        tool = Tooling.query.filter_by(tool_code=batch).first()
        if not tool:
            flash("Такого BATCH # нет. Сначала создай его через «Новый BATCH #».", "warning")
            return redirect(url_for("tooling.tooling_new"))

        equipment = Equipment.query.get(int(machine_id)) if machine_id else None

        if action == "INSTALL":
            if not (equipment and role and position and reason):
                flash("Для INSTALL обязательны: MACHINE, ROLE, POSITION и REASON.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            install_tool(tool, equipment, role, position, shift, reason,
                         float(dim) if dim is not None else None)
            db.session.commit()
            flash("Установлено. Если слот был занят — старый инструмент снят автоматически.", "success")
            return redirect(url_for("tooling.list_tooling"))

        if action == "REMOVE":
            if not (equipment and role and position):
                flash("Для REMOVE обязательны: MACHINE, ROLE и POSITION.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            remove_tool(tool, equipment, role, position, reason or "REMOVE")
            db.session.commit()
            flash("Снято.", "success")
            return redirect(url_for("tooling.list_tooling"))

        if action == "REGRIND":
            regrind_tool(tool,
                         float(dim) if dim is not None else None,
                         float(new_dim) if new_dim is not None else None,
                         reason or "REGRIND", shift)
            db.session.commit()
            flash("Перешлифовка зафиксирована.", "success")
            return redirect(url_for("tooling.list_tooling"))

        # прочие сервисные события
        ev = ToolingEvent(
            user_name=getattr(current_user, "username", "user"),
            machine_id=equipment.id if equipment else None,
            machine_name=(getattr(equipment, "name", None) or getattr(equipment, "code", None)) if equipment else None,
            shift=shift,
            happened_at=datetime.utcnow(),
            action=action,
            reason=reason,
            note=note,
            role=role,
            position=position,
            slot_id=None,
            dimension=dim,
            new_dimension=new_dim,
            tool_id=tool.id,
            batch_no=tool.tool_code,
            from_status=None,
            to_status=("READY" if action == "MARK_READY"
                       else "DEFECTIVE" if action == "MARK_DEFECTIVE"
                       else "SCRAPPED" if action == "SCRAP"
                       else None),
        )
        if action == "SCRAP":
            tool.is_active = False
        db.session.add(ev)
        db.session.commit()
        flash(f"Событие {action} записано.", "success")
        return redirect(url_for("tooling.list_tooling"))

    return render_template("tooling/event_form.html",
                           actions=actions, shifts=shifts,
                           roles=roles, positions=positions, machines=machines)


# --------------------------- ROOT: РЕДАКТИРОВАНИЕ --------------------------- #
@tooling_bp.route("/<int:tool_id>/edit", methods=["POST"])
@role_required(["root"])
def edit_tool(tool_id: int):
    """Правка основных полей инструмента (root)."""
    tool = Tooling.query.get_or_404(tool_id)

    # Разрешенные поля
    tool.serial_number = (request.form.get("serial_number") or "").strip() or None
    tool.current_location = (request.form.get("current_location") or "").strip() or None
    tool.vendor = (request.form.get("vendor") or "").strip() or None
    tool.max_cycles_before_service = (request.form.get("max_cycles_before_service") or "").strip() or None
    tool.intended_role = (request.form.get("intended_role") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None
    tool.notes = notes

    tool.updated_at = datetime.utcnow()

    # Лог события EDIT
    ev = ToolingEvent(
        user_name=getattr(current_user, "username", "root"),
        action="EDIT",
        tool_id=tool.id,
        batch_no=tool.tool_code,
        happened_at=datetime.utcnow(),
        note="Edited by root",
    )
    db.session.add(ev)
    db.session.commit()

    flash("Изменения сохранены.", "success")
    back = _get_back_url()
    return redirect(url_for("tooling.tooling_detail", tool_id=tool.id, back=back))


# ------------------------------ ROOT: УДАЛЕНИЕ ------------------------------ #
@tooling_bp.route("/<int:tool_id>/delete", methods=["POST"])
@role_required(["root"])
def delete_tool(tool_id: int):
    """Soft delete инструмента (root)."""
    tool = Tooling.query.get_or_404(tool_id)
    reason = (request.form.get("details") or "").strip() or "Soft delete"

    tool.is_active = False
    tool.updated_at = datetime.utcnow()

    ev = ToolingEvent(
        user_name=getattr(current_user, "username", "root"),
        action="SOFT_DELETE",
        to_status="SCRAPPED",
        tool_id=tool.id,
        batch_no=tool.tool_code,
        happened_at=datetime.utcnow(),
        reason=reason
    )
    db.session.add(ev)
    db.session.commit()

    flash("Инструмент помечен как удалённый (soft delete).", "success")
    # После удаления логичнее вернуться в список
    return redirect(_get_back_url())


# -------------------------- ЭКСПОРТ CSV: ИСТОРИЯ --------------------------- #
@tooling_bp.route("/export/<int:tool_id>/history.csv")
@login_required
def export_history_csv(tool_id: int):
    """CSV-выгрузка истории для конкретного инструмента."""
    tool = Tooling.query.get_or_404(tool_id)
    events = (ToolingEvent.query
              .filter_by(tool_id=tool_id)
              .order_by(ToolingEvent.happened_at.asc())
              .all())

    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    header = ["BATCH #", "DATE/TIME", "USER", "ACTION", "STATUS_TO", "BM#", "ROLE", "POSITION",
              "DIM", "NEW DIM", "REASON", "NOTE"]
    w.writerow(header)
    for e in events:
        w.writerow([
            tool.tool_code,
            e.happened_at.isoformat(sep=" ") if e.happened_at else "",
            e.user_name or "",
            e.action or "",
            e.to_status or "",
            e.machine_name or "",
            e.role or "",
            e.position or "",
            f"{e.dimension}" if e.dimension is not None else "",
            f"{e.new_dimension}" if e.new_dimension is not None else "",
            e.reason or "",
            e.note or "",
        ])

    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=tool_{tool.tool_code}_history_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    )
    return resp


# -------------------------------- ЭКСПОРТ CSV ------------------------------- #
@tooling_bp.route("/export/csv")
@role_required(["admin", "root"])
def export_csv():
    tools = Tooling.query.filter_by(is_active=True).order_by(desc(Tooling.updated_at)).all()

    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    header = ["BATCH #", "LAST DATE", "LAST ACTION", "STATUS", "BM#", "ROLE", "POSITION", "DIM", "NEW DIM"]
    w.writerow(header)
    for t in tools:
        a = t.last_aggregate()
        w.writerow([
            a["BATCH #"] or "",
            a["LAST DATE"].isoformat(sep=" ") if a["LAST DATE"] else "",
            a["LAST ACTION"] or "",
            a["STATUS"] or "",
            a["BM#"] or "",
            a["ROLE"] or "",
            a["POSITION"] or "",
            a["DIM"] if a["DIM"] is not None else "",
            a["NEW DIM"] if a["NEW DIM"] is not None else "",
        ])

    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename=tooling_export_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return resp


# --------------------------------- ИМПОРТ ---------------------------------- #
@tooling_bp.route("/import", methods=["GET", "POST"])
@role_required(["admin", "root"])
def import_tooling():
    if request.method == "POST":
        flash("Импорт CSV появится в следующей итерации. Пока используйте «Новый BATCH #» и «События».", "warning")
        return redirect(url_for("tooling.list_tooling"))
    return render_template("tooling/import_placeholder.html")
