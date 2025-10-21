# -*- coding: utf-8 -*-
"""
ROUTES для Tooling под событийную модель (как Google Sheet).

Ключевое:
- /tooling/event  — универсальная форма события (как в листе: USER, MACHINE, SHIFT, ACTION, ROLE, POSITION, REASON, DIM, NEW DIM, BATCH #, NOTE)
- /tooling/       — список с колонками: BATCH #, LAST DATE, LAST ACTION, STATUS, BM#, ROLE, POSITION, DIM, NEW DIM
- /tooling/new    — упрощённое создание "партии" (BATCH # + тип)

Автоматическое снятие: внутренняя функция install_tool() авто-снимает занятый слот.
"""
import io, csv
from flask import make_response
from datetime import datetime

from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from maintenance_models import Equipment  # твоя модель из модуля Maintenance
from tooling.models_tooling import (
    Tooling, ToolType, ToolingEvent, ToolingMount, EquipmentSlot,
    ALLOWED_ACTIONS, ALLOWED_SHIFTS, ALLOWED_ROLES, ALLOWED_POSITIONS,
    install_tool, remove_tool, regrind_tool
)
from permissions import role_required

tooling_bp = Blueprint("tooling", __name__, template_folder="../templates/tooling")

# ---------------- СПИСОК (агрегированное представление как STOCK/PARTS) ----------------
@tooling_bp.route("/")
@login_required
def list_tooling():
    tools = Tooling.query.filter_by(is_active=True).order_by(Tooling.updated_at.desc()).all()
    rows = [t.last_aggregate() for t in tools]
    return render_template("tooling/list_tooling.html", rows=rows)

# ---------------- КАРТОЧКА (минимальная) ----------------
@tooling_bp.route("/<int:tool_id>")
@login_required
def tooling_detail(tool_id):
    t = Tooling.query.get_or_404(tool_id)
    events = (ToolingEvent.query
              .filter_by(tool_id=tool_id)
              .order_by(ToolingEvent.happened_at.desc())
              .all())
    return render_template("tooling/tooling_detail.html", item=t, events=events)

# ---------------- СОЗДАТЬ ПАРТИЮ (BATCH #) ----------------
@tooling_bp.route("/new", methods=["GET", "POST"])
@role_required(["admin", "root"])
def tooling_new():
    if request.method == "POST":
        code = request.form.get("tool_code", "").strip()
        type_code = request.form.get("type_code", "").strip()
        if not code or not type_code:
            flash("Нужны: Код оснастки (BATCH #) и Тип.")
            return redirect(url_for("tooling.tooling_new"))

        ttype = ToolType.query.filter_by(code=type_code).first()
        if not ttype:
            ttype = ToolType(code=type_code, name=type_code)
            db.session.add(ttype)
            db.session.flush()

        if Tooling.query.filter_by(tool_code=code).first():
            flash("Инструмент с таким BATCH # уже существует.")
            return redirect(url_for("tooling.tooling_new"))

        tool = Tooling(tool_code=code, tool_type_id=ttype.id)
        db.session.add(tool)

        # событие CREATE
        ev = ToolingEvent(
            user_name=current_user.username,
            action="CREATE",
            to_status="STOCK",
            tool_id=tool.id,
            batch_no=tool.tool_code,
            happened_at=datetime.utcnow(),
        )
        db.session.add(ev)
        db.session.commit()
        flash("Создано.")
        return redirect(url_for("tooling.list_tooling"))
    return render_template("tooling/tooling_new.html")

# ---------------- УНИВЕРСАЛЬНАЯ ФОРМА СОБЫТИЯ (как в Google Sheet) ----------------
@tooling_bp.route("/event", methods=["GET", "POST"])
@login_required
def tooling_event():
    # подгружаем справочники (можно сделать из БД)
    actions = ALLOWED_ACTIONS
    shifts = ALLOWED_SHIFTS
    roles = ALLOWED_ROLES
    positions = ALLOWED_POSITIONS
    machines = Equipment.query.order_by(Equipment.name.asc()).all()

    if request.method == "POST":
        batch = request.form.get("batch_no", "").strip()    # BATCH #
        action = request.form.get("action")
        shift = request.form.get("shift") or None
        machine_id = request.form.get("machine_id")
        role = request.form.get("role") or None
        position = request.form.get("position") or None
        reason = request.form.get("reason") or None
        note = request.form.get("note") or None
        dim_raw = request.form.get("dimension") or None
        new_dim_raw = request.form.get("new_dimension") or None

        # безопасный парсинг чисел
        def parse_num(s):
            if not s:
                return None
            s = s.replace(",", ".")
            try:
                return Decimal(s)
            except InvalidOperation:
                return None

        dim = parse_num(dim_raw)
        new_dim = parse_num(new_dim_raw)

        if not batch or action not in actions:
            flash("Укажи BATCH # и корректный ACTION.")
            return redirect(url_for("tooling.tooling_event"))

        tool = Tooling.query.filter_by(tool_code=batch).first()
        if not tool:
            flash("Такого BATCH # нет. Сначала создай через 'New Tooling'.")
            return redirect(url_for("tooling.tooling_new"))

        equipment = None
        if machine_id:
            equipment = Equipment.query.get(int(machine_id))

        # Ветвление по ACTION
        if action == "INSTALL":
            if not (equipment and role and position and reason):
                flash("Для INSTALL обязательны MACHINE, ROLE, POSITION и REASON.")
                return redirect(url_for("tooling.tooling_event"))
            install_tool(tool, equipment, role, position, shift, reason, float(dim) if dim is not None else None)
            db.session.commit()
            flash("Установлено (старый из слота снят автоматически, если был).")
            return redirect(url_for("tooling.list_tooling"))

        elif action == "REMOVE":
            if not (equipment and role and position):
                flash("Для REMOVE обязательны MACHINE, ROLE и POSITION.")
                return redirect(url_for("tooling.tooling_event"))
            remove_tool(tool, equipment, role, position, reason or "REMOVE")
            db.session.commit()
            flash("Снято.")
            return redirect(url_for("tooling.list_tooling"))

        elif action == "REGRIND":
            ev = regrind_tool(tool, float(dim) if dim is not None else None,
                              float(new_dim) if new_dim is not None else None,
                              reason or "REGRIND", shift)
            db.session.commit()
            flash("Перешлифовано.")
            return redirect(url_for("tooling.list_tooling"))

        elif action in ("WASH", "POLISH", "INSPECT", "REPAIR", "MARK_READY", "MARK_DEFECTIVE", "SCRAP", "CREATE"):
            # простое событие без монтирования
            ev = ToolingEvent(
                user_name=current_user.username,
                machine_id=equipment.id if equipment else None,
                machine_name=getattr(equipment, "name", None) if equipment else None,
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
                to_status=(
                    "READY" if action == "MARK_READY"
                    else "DEFECTIVE" if action == "MARK_DEFECTIVE"
                    else "SCRAPPED" if action == "SCRAP"
                    else None
                )
            )
            # побочные эффекты по статусу
            if action == "MARK_READY":
                pass  # можно что-то менять в карточке, но статус берём из событий
            elif action == "SCRAP":
                tool.is_active = False

            db.session.add(ev)
            db.session.commit()
            flash(f"Событие {action} записано.")
            return redirect(url_for("tooling.list_tooling"))

        else:
            flash(f"Пока не поддержано: {action}")
            return redirect(url_for("tooling.tooling_event"))

    return render_template("tooling/event_form.html",
                           actions=actions, shifts=shifts, roles=roles,
                           positions=positions, machines=machines)

# ---------------- ЭКСПОРТ CSV (агрегированное представление) ----------------
@tooling_bp.route("/export/csv")
@role_required(["admin", "root"])
def export_csv():
    tools = Tooling.query.filter_by(is_active=True).order_by(Tooling.updated_at.desc()).all()

    output = io.StringIO()
    w = csv.writer(output, lineterminator="\n")
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

    # Excel-friendly UTF-8 with BOM
    data = ("\ufeff" + output.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename=tooling_export_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return resp


# ---------------- ПЛЕЙСХОЛДЕР ИМПОРТА (чтобы не падало) ----------------
@tooling_bp.route("/import", methods=["GET", "POST"])
@role_required(["admin", "root"])
def import_tooling():
    if request.method == "POST":
        flash("Импорт CSV в этой ветке пока не реализован. Используй /tooling/new или событие CREATE.", "warning")
        return redirect(url_for("tooling.list_tooling"))
    return render_template("tooling/import_placeholder.html")
