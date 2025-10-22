# tooling/routes_tooling.py
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import io
import csv

from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from extensions import db
from maintenance_models import Equipment
from tooling.models_tooling import (
    Tooling, ToolType, ToolingEvent,
    ALLOWED_ACTIONS, ALLOWED_SHIFTS, ALLOWED_ROLES, ALLOWED_POSITIONS,
    install_tool, remove_tool, regrind_tool,
)
from permissions import role_required

tooling_bp = Blueprint("tooling", __name__)


# ----------------------------- helpers ------------------------------------- #
def _parse_num(s: str | None):
    """Принимает '63,075' или '63.075' -> Decimal | None"""
    if not s:
        return None
    s = str(s).strip().replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, AttributeError):
        return None


def _dt(s: str | None):
    """Поддержка 'YYYY-MM-DD HH:MM:SS' или 'YYYY-MM-DD'."""
    if not s:
        return None
    s = s.strip().replace("T", " ")
    try:
        if len(s) <= 10:
            return datetime.strptime(s, "%Y-%m-%d")
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


# --------------------------------- LIST ------------------------------------ #
@tooling_bp.route("/")
@login_required
def list_tooling():
    tools = Tooling.query.filter_by(is_active=True).order_by(desc(Tooling.updated_at)).all()
    rows = []
    for t in tools:
        a = t.last_aggregate()  # dict: BATCH #, LAST DATE, LAST ACTION, STATUS, BM#, ROLE, POSITION, DIM, NEW DIM
        a["id"] = t.id          # для ссылки на карточку
        rows.append(a)
    return render_template("tooling/list_tooling.html", rows=rows)


# -------------------------------- DETAIL ----------------------------------- #
@tooling_bp.route("/<int:tool_id>")
@login_required
def tooling_detail(tool_id: int):
    item = Tooling.query.get_or_404(tool_id)
    events = (ToolingEvent.query
              .filter_by(tool_id=tool_id)
              .order_by(ToolingEvent.happened_at.desc())
              .all())

    ordered = Tooling.query.filter_by(is_active=True).order_by(Tooling.updated_at.desc()).all()
    ids = [t.id for t in ordered]
    idx = ids.index(tool_id) if tool_id in ids else -1
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if idx != -1 and idx < len(ids) - 1 else None

    return render_template("tooling/tooling_detail.html",
                           item=item, events=events,
                           prev_id=prev_id, next_id=next_id)


# --------------------------- NEW BATCH FORM -------------------------------- #
@tooling_bp.route("/new", methods=["GET", "POST"])
@role_required(["admin", "root"])
def tooling_new():
    """
    Минимум: BATCH # (обяз.), ROLE (желательно), DIM (желательно).
    type_code — опц., если пусто — 'GENERIC'.
    """
    if request.method == "POST":
        code = (request.form.get("tool_code") or "").strip()
        type_code = (request.form.get("type_code") or "GENERIC").strip()
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


# ------------------------------- EVENT FORM -------------------------------- #
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

        # Прочие сервисные события
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


# ------------------------------ EXPORT (grid) ------------------------------- #
@tooling_bp.route("/export/csv")
@login_required
def export_csv():
    """Экспорт текущей витрины (агрегат)."""
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


# --------------------------- CSV TEMPLATES (download) ---------------------- #
@tooling_bp.route("/export/template.csv")
@role_required(["admin", "root"])
def export_template_csv():
    """Шаблон 'friendly' (как в таблице): ACTION,ROLE,POSITION,REASON,DIM,BATCH #"""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["ACTION", "ROLE", "POSITION", "REASON", "DIM", "BATCH #"])
    # примеры:
    w.writerow(["CREATE", "IRONING", "#3", "New", "63.075", "IH-1"])
    w.writerow(["CREATE", "IRONING", "",   "New", "",       "IH-2"])
    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=tooling_template_friendly.csv"
    return resp


@tooling_bp.route("/export/template_events.csv")
@role_required(["admin", "root"])
def export_template_events_csv():
    """Шаблон 'events' (журнал событий)."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow([
        "batch_no","happened_at","action","user","shift",
        "machine_code","role","position","reason","dimension","new_dimension","note"
    ])
    w.writerow(["IH-1","2025-10-21 10:00:00","CREATE","import","A","",
                "IRONING","","New","63.075","",""])
    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=tooling_template_events.csv"
    return resp


# ------------------------------ EXPORT events ------------------------------ #
@tooling_bp.route("/<int:tool_id>/export/events.csv")
@login_required
def export_tool_events(tool_id: int):
    """Экспорт полной истории события по одному инструменту."""
    tool = Tooling.query.get_or_404(tool_id)
    events = (ToolingEvent.query
              .filter_by(tool_id=tool.id)
              .order_by(ToolingEvent.happened_at.asc())
              .all())

    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    headers = [
        "batch_no","happened_at","action","user","shift",
        "machine_code","role","position","reason","dimension","new_dimension","note"
    ]
    w.writerow(headers)
    for e in events:
        w.writerow([
            e.batch_no,
            e.happened_at.strftime("%Y-%m-%d %H:%M:%S") if e.happened_at else "",
            e.action or "",
            e.user_name or "",
            e.shift or "",
            e.machine_name or "",
            e.role or "",
            e.position or "",
            e.reason or "",
            e.dimension if e.dimension is not None else "",
            e.new_dimension if e.new_dimension is not None else "",
            e.note or "",
        ])

    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename=tool_{tool.tool_code}_events.csv"
    return resp


@tooling_bp.route("/export/events.csv")
@role_required(["admin", "root"])
def export_all_events_csv():
    """Экспорт всей истории по всем инструментам."""
    events = ToolingEvent.query.order_by(ToolingEvent.happened_at.asc()).all()
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    headers = [
        "batch_no","happened_at","action","user","shift",
        "machine_code","role","position","reason","dimension","new_dimension","note"
    ]
    w.writerow(headers)
    for e in events:
        w.writerow([
            e.batch_no,
            e.happened_at.strftime("%Y-%m-%d %H:%M:%S") if e.happened_at else "",
            e.action or "",
            e.user_name or "",
            e.shift or "",
            e.machine_name or "",
            e.role or "",
            e.position or "",
            e.reason or "",
            e.dimension if e.dimension is not None else "",
            e.new_dimension if e.new_dimension is not None else "",
            e.note or "",
        ])

    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=tooling_events_all.csv"
    return resp


# --------------------------------- IMPORT ---------------------------------- #
@tooling_bp.route("/import", methods=["GET", "POST"])
@role_required(["admin", "root"])
def import_tooling():
    """
    Поддерживаем 2 заголовка:
    1) friendly: ACTION,ROLE,POSITION,REASON,DIM,BATCH #
    2) events:   batch_no,happened_at,action,user,shift,machine_code,role,position,reason,dimension,new_dimension,note
    """
    report = None

    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename.lower().endswith(".csv"):
            flash("Выбери CSV файл.", "warning")
            return redirect(url_for("tooling.import_tooling"))

        raw = file.read()
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        headers = [h.strip() for h in (reader.fieldnames or [])]
        lowered = [h.lower() for h in headers]

        mode = None
        if {"batch #", "action", "role", "position", "reason", "dim"} <= set(h.lower() for h in headers):
            mode = "friendly"
        elif "batch_no" in lowered and "action" in lowered:
            mode = "events"

        if not mode:
            flash("Не распознан формат CSV. Проверь заголовки.", "danger")
            return redirect(url_for("tooling.import_tooling"))

        created_tools, updated_tools, events_written, errors = [], [], 0, []

        # для генерации времени по friendly
        start_dt = datetime.utcnow().replace(microsecond=0)
        minute = 0

        for idx, row in enumerate(reader, start=2):
            try:
                if mode == "friendly":
                    action = (row.get("ACTION") or row.get("Action") or "").strip().upper()
                    role = (row.get("ROLE") or "").strip() or None
                    position = (row.get("POSITION") or "").strip() or None
                    reason = (row.get("REASON") or "").strip() or None
                    dim = _parse_num(row.get("DIM"))
                    batch = (row.get("BATCH #") or row.get("BATCH") or "").strip()
                    if not batch or not action:
                        raise ValueError("Поля BATCH # и ACTION обязательны")
                    if action != "CREATE":
                        raise ValueError(f"В friendly-формате поддержан только CREATE, получено {action}")

                    tool = Tooling.query.filter_by(tool_code=batch).first()
                    if not tool:
                        ttype = ToolType.query.filter_by(code="GENERIC").first()
                        if not ttype:
                            ttype = ToolType(code="GENERIC", name="GENERIC")
                            db.session.add(ttype)
                            db.session.flush()

                        tool = Tooling(
                            tool_code=batch,
                            tool_type_id=ttype.id,
                            intended_role=role,
                            current_diameter=float(dim) if dim is not None else None
                        )
                        db.session.add(tool)
                        db.session.flush()
                        created_tools.append(batch)
                    else:
                        changed = False
                        if role and role != tool.intended_role:
                            tool.intended_role = role
                            changed = True
                        if dim is not None:
                            tool.current_diameter = float(dim)
                            changed = True
                        if changed:
                            updated_tools.append(batch)

                    if batch in created_tools:
                        ev_dt = start_dt + timedelta(minutes=minute); minute += 1
                        ev = ToolingEvent(
                            user_name=getattr(current_user, "username", "import"),
                            action="CREATE",
                            to_status="STOCK",
                            tool_id=tool.id,
                            batch_no=tool.tool_code,
                            happened_at=ev_dt,
                            role=role,
                            position=position,
                            reason=reason,
                            dimension=dim
                        )
                        db.session.add(ev); events_written += 1

                else:  # mode == "events"
                    batch = (row.get("batch_no") or "").strip()
                    action = (row.get("action") or "").strip().upper()
                    when = _dt(row.get("happened_at")) or (start_dt + timedelta(minutes=minute))
                    minute += 1
                    user = (row.get("user") or "import").strip()
                    shift = (row.get("shift") or None)
                    machine_code = (row.get("machine_code") or "").strip()
                    role = (row.get("role") or "").strip() or None
                    position = (row.get("position") or "").strip() or None
                    reason = (row.get("reason") or "").strip() or None
                    dim = _parse_num(row.get("dimension"))
                    new_dim = _parse_num(row.get("new_dimension"))
                    note = (row.get("note") or "").strip() or None

                    if not batch or action not in ALLOWED_ACTIONS:
                        raise ValueError("Поля batch_no и корректный action обязательны")

                    tool = Tooling.query.filter_by(tool_code=batch).first()
                    if not tool:
                        ttype = ToolType.query.filter_by(code="GENERIC").first()
                        if not ttype:
                            ttype = ToolType(code="GENERIC", name="GENERIC")
                            db.session.add(ttype)
                            db.session.flush()
                        tool = Tooling(tool_code=batch, tool_type_id=ttype.id, intended_role=role)
                        db.session.add(tool)
                        db.session.flush()
                        created_tools.append(batch)

                    equipment = None
                    if machine_code:
                        equipment = Equipment.query.filter(
                            or_(Equipment.code == machine_code, Equipment.name == machine_code)
                        ).first()

                    if action == "INSTALL":
                        if not (equipment and role and position):
                            raise ValueError("INSTALL требует machine_code, role, position")
                        install_tool(tool, equipment, role, position, shift, reason,
                                     float(dim) if dim is not None else None,
                                     when=when, user_name=user)
                        events_written += 1
                    elif action == "REMOVE":
                        if not (equipment and role and position):
                            raise ValueError("REMOVE требует machine_code, role, position")
                        remove_tool(tool, equipment, role, position, reason or "REMOVE",
                                    when=when, user_name=user)
                        events_written += 1
                    elif action == "REGRIND":
                        regrind_tool(tool,
                                     float(dim) if dim is not None else None,
                                     float(new_dim) if new_dim is not None else None,
                                     reason or "REGRIND", shift,
                                     when=when, user_name=user)
                        events_written += 1
                    else:
                        ev = ToolingEvent(
                            user_name=user,
                            machine_id=equipment.id if equipment else None,
                            machine_name=(getattr(equipment, "name", None) or getattr(equipment, "code", None))
                                         if equipment else None,
                            shift=shift,
                            happened_at=when,
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
                        events_written += 1

            except Exception as e:
                errors.append(f"Строка {idx}: {e}")

        db.session.commit()
        report = dict(
            mode=mode,
            created=len(set(created_tools)),
            updated=len(set(updated_tools)),
            events=events_written,
            errors=errors,
        )
        if errors:
            flash(f"Импорт выполнен с ошибками ({len(errors)} строк). Смотри отчёт ниже.", "warning")
        else:
            flash("Импорт успешно выполнен.", "success")

    return render_template("tooling/import_tooling.html", report=report)
