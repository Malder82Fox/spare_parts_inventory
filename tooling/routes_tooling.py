# tooling/routes_tooling.py
# -*- coding: utf-8 -*-

from datetime import datetime
from decimal import Decimal, InvalidOperation
import io
import csv

from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user

from extensions import db
from maintenance_models import Equipment  # модель оборудования из модуля Maintenance
from tooling.models_tooling import (
    Tooling, ToolType, ToolingEvent,
    ALLOWED_ACTIONS, ALLOWED_SHIFTS, ALLOWED_ROLES, ALLOWED_POSITIONS,
    install_tool, remove_tool, regrind_tool,
)
from permissions import role_required

# Имя блюпринта — "tooling", чтобы url_for('tooling.export_csv') и др. совпали с шаблоном
tooling_bp = Blueprint("tooling", __name__, template_folder="../templates/tooling")


# -----------------------------------------------------------------------------
# 1) Список / агрегированная витрина
# -----------------------------------------------------------------------------
@tooling_bp.route("/")
@login_required
def list_tooling():
    # Показ: BATCH #, LAST DATE, LAST ACTION, STATUS, BM#, ROLE, POSITION, DIM, NEW DIM
    tools = Tooling.query.filter_by(is_active=True).order_by(Tooling.updated_at.desc()).all()
    rows = [t.last_aggregate() for t in tools]
    return render_template("tooling/list_tooling.html", rows=rows)


# -----------------------------------------------------------------------------
# 2) Создание «партии» (BATCH #) — минимальная карточка
# -----------------------------------------------------------------------------
@tooling_bp.route("/new", methods=["GET", "POST"])
@role_required(["admin", "root"])
def tooling_new():
    if request.method == "POST":
        code = (request.form.get("tool_code") or "").strip()     # BATCH #
        type_code = (request.form.get("type_code") or "").strip()

        if not code or not type_code:
            flash("Нужны: BATCH # и Тип.", "warning")
            return redirect(url_for("tooling.tooling_new"))

        # upsert типа
        ttype = ToolType.query.filter_by(code=type_code).first()
        if not ttype:
            ttype = ToolType(code=type_code, name=type_code)
            db.session.add(ttype)
            db.session.flush()

        # уникальность BATCH #
        if Tooling.query.filter_by(tool_code=code).first():
            flash("Инструмент с таким BATCH # уже существует.", "warning")
            return redirect(url_for("tooling.tooling_new"))

        tool = Tooling(tool_code=code, tool_type_id=ttype.id)
        db.session.add(tool)
        db.session.flush()  # важно: чтобы tool.id уже был перед событием

        # событие CREATE — для прозрачной истории
        ev = ToolingEvent(
            user_name=getattr(current_user, "username", "system"),
            action="CREATE",
            to_status="STOCK",
            tool_id=tool.id,
            batch_no=tool.tool_code,
            happened_at=datetime.utcnow(),
        )
        db.session.add(ev)
        db.session.commit()

        flash("BATCH # создан.", "success")
        return redirect(url_for("tooling.list_tooling"))

    return render_template("tooling/tooling_new.html")


# -----------------------------------------------------------------------------
# 3) Универсальная форма события (как в твоём Google Sheet)
# -----------------------------------------------------------------------------
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
        dim_raw = request.form.get("dimension") or None
        new_dim_raw = request.form.get("new_dimension") or None

        # безопасный парсинг числа (поддержка запятой)
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
            flash("Укажи BATCH # и корректный ACTION.", "warning")
            return redirect(url_for("tooling.tooling_event"))

        tool = Tooling.query.filter_by(tool_code=batch).first()
        if not tool:
            flash("Такого BATCH # нет. Сначала создай его через «Новый BATCH #».", "warning")
            return redirect(url_for("tooling.tooling_new"))

        equipment = None
        if machine_id:
            equipment = Equipment.query.get(int(machine_id))

        # Развилка по ACTION
        if action == "INSTALL":
            if not (equipment and role and position and reason):
                flash("Для INSTALL обязательны: MACHINE, ROLE, POSITION и REASON.", "warning")
                return redirect(url_for("tooling.tooling_event"))

            install_tool(
                tool=tool,
                equipment=equipment,
                role=role,
                position=position,
                shift=shift,
                reason=reason,
                dim=float(dim) if dim is not None else None,
            )
            db.session.commit()
            flash("Установлено. Если слот был занят — предыдущий инструмент снят автоматически.", "success")
            return redirect(url_for("tooling.list_tooling"))

        elif action == "REMOVE":
            if not (equipment and role and position):
                flash("Для REMOVE обязательны: MACHINE, ROLE и POSITION.", "warning")
                return redirect(url_for("tooling.tooling_event"))

            remove_tool(tool, equipment, role, position, reason or "REMOVE")
            db.session.commit()
            flash("Снято.", "success")
            return redirect(url_for("tooling.list_tooling"))

        elif action == "REGRIND":
            regrind_tool(
                tool,
                float(dim) if dim is not None else None,
                float(new_dim) if new_dim is not None else None,
                reason or "REGRIND",
                shift,
            )
            db.session.commit()
            flash("Перешлифовка зафиксирована.", "success")
            return redirect(url_for("tooling.list_tooling"))

        elif action in ("WASH", "POLISH", "INSPECT", "REPAIR", "MARK_READY", "MARK_DEFECTIVE", "SCRAP", "CREATE"):
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
                to_status=(
                    "READY" if action == "MARK_READY"
                    else "DEFECTIVE" if action == "MARK_DEFECTIVE"
                    else "SCRAPPED" if action == "SCRAP"
                    else None
                ),
            )
            if action == "SCRAP":
                tool.is_active = False  # скрываем из витрины

            db.session.add(ev)
            db.session.commit()
            flash(f"Событие {action} записано.", "success")
            return redirect(url_for("tooling.list_tooling"))

        else:
            flash(f"Пока не поддержано: {action}", "warning")
            return redirect(url_for("tooling.tooling_event"))

    # GET → отрисовать форму
    return render_template(
        "tooling/event_form.html",
        actions=actions, shifts=shifts, roles=roles, positions=positions, machines=machines
    )


# -----------------------------------------------------------------------------
# 4) Экспорт CSV (эндпоинт совпадает с шаблоном: tooling.export_csv)
# -----------------------------------------------------------------------------
@tooling_bp.route("/export/csv")
@role_required(["admin", "root"])
def export_csv():
    tools = Tooling.query.filter_by(is_active=True).order_by(Tooling.updated_at.desc()).all()

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    header = ["BATCH #", "LAST DATE", "LAST ACTION", "STATUS", "BM#", "ROLE", "POSITION", "DIM", "NEW DIM"]
    writer.writerow(header)

    for t in tools:
        a = t.last_aggregate()
        writer.writerow([
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

    data = ("\ufeff" + out.getvalue()).encode("utf-8")  # BOM для Excel
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename=tooling_export_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return resp


# -----------------------------------------------------------------------------
# 5) Импорт CSV (заглушка; эндпоинт совпадает с шаблоном: tooling.import_tooling)
# -----------------------------------------------------------------------------
@tooling_bp.route("/import", methods=["GET", "POST"])
@role_required(["admin", "root"])
def import_tooling():
    if request.method == "POST":
        flash("Импорт CSV появится в следующей итерации. Пока используйте «Новый BATCH #» и «События».", "warning")
