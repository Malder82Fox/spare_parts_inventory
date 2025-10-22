# tooling/routes_tooling.py
# -*- coding: utf-8 -*-

from datetime import datetime
from decimal import Decimal, InvalidOperation
import io
import csv

from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
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

tooling_bp = Blueprint("tooling", __name__)

# ----------------------------- СПРАВОЧНИКИ UI ------------------------------ #
# Фиксированный список смен
SHIFT_CHOICES = ["Tooling room", "A", "B", "C", "D"]

# Причины для INSTALL (выпадающий список)
INSTALL_REASONS = [
    "Top wall variation",
    "Top wall oversize",
    "Short trim",
    "Sensor short can",
    "Sugar scoop",
    "Short can",
    "Die scratches",
    "Die worn",
    "Oval can",
    "Progression",
    "Mid wall below specification",
    "Progression mark horizontal",
    "Progression mark vertical",
    "Top wall undersize",
    "Defective die",
    "Die damage",
    "Trial",
    "No reason",
    "Pin hole",
    "Pick up",
    "Shadows",
    "Roll back",
    "Metal exposure",
    "Chime smile",
    "Dome depth",
    "Wrinkled domes",
    "Slivers",
    "Burrs",
    "Uneven trim",
    "Trimmer jams",
    "Split flanges",
    "Scheduled change",
    "New",
]

# ----------------------------- ВСПОМОГАТЕЛЬНОЕ ----------------------------- #
def _parse_num(s: str | None):
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


# --------------------------------- СПИСОК ---------------------------------- #
@tooling_bp.route("/")
@login_required
def list_tooling():
    tools = Tooling.query.filter_by(is_active=True).order_by(desc(Tooling.updated_at)).all()
    rows = []
    for t in tools:
        a = t.last_aggregate()
        a["id"] = t.id
        rows.append(a)
    return render_template("tooling/list_tooling.html", rows=rows)


# -------------------------------- КАРТОЧКА --------------------------------- #
@tooling_bp.route("/<int:tool_id>")
@login_required
def tooling_detail(tool_id: int):
    item = Tooling.query.get_or_404(tool_id)
    events = (ToolingEvent.query
              .filter_by(tool_id=tool_id)
              .order_by(ToolingEvent.happened_at.desc())
              .all())

    ordered = Tooling.query.filter_by(is_active=True).order_by(desc(Tooling.updated_at)).all()
    ids = [t.id for t in ordered]
    idx = ids.index(tool_id) if tool_id in ids else -1
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if idx != -1 and idx < len(ids) - 1 else None

    return render_template("tooling/tooling_detail.html",
                           item=item, events=events,
                           prev_id=prev_id, next_id=next_id)


# ----------------------- СОЗДАНИЕ НОВОГО BATCH # --------------------------- #
@tooling_bp.route("/new", methods=["GET", "POST"])
@role_required(["admin", "root"])
def tooling_new():
    if request.method == "POST":
        code = (request.form.get("tool_code") or "").strip()
        type_code = (request.form.get("type_code") or "GENERIC").strip()
        role = (request.form.get("role") or "").strip() or None
        dim = _parse_num(request.form.get("dimension"))

        if not code:
            flash("Укажи BATCH #.", "warning")
            return redirect(url_for("tooling.tooling_new"))

        ttype = ToolType.query.filter_by(code=type_code).first()
        if not ttype:
            ttype = ToolType(code=type_code, name=type_code)
            db.session.add(ttype)
            db.session.flush()

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
        db.session.flush()

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
    roles = ALLOWED_ROLES
    positions = ALLOWED_POSITIONS
    shifts = SHIFT_CHOICES
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

        # --- INSTALL: строгие требования ---
        if action == "INSTALL":
            # 1) ROLE обязателен; если IRONING — обязательна POSITION
            if not role:
                flash("Для INSTALL необходимо указать ROLE.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            if role == "IRONING" and not position:
                flash("Для INSTALL с ROLE=IRONING необходимо указать POSITION.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            # 2) MACHINE обязателен
            if not equipment:
                flash("Для INSTALL необходимо выбрать MACHINE (BM#).", "warning")
                return redirect(url_for("tooling.tooling_event"))
            # 3) SHIFT обязателен из списка
            if not shift or shift not in SHIFT_CHOICES:
                flash("Для INSTALL необходимо выбрать SHIFT.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            # 4) DIM обязателен (число)
            if dim is None:
                flash("Для INSTALL необходимо указать DIM.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            # REASON обязателен и из справочника
            if not reason or reason not in INSTALL_REASONS:
                flash("Для INSTALL необходимо выбрать REASON из списка.", "warning")
                return redirect(url_for("tooling.tooling_event"))

            install_tool(
                tool=tool,
                equipment=equipment,
                role=role,
                position=position,
                shift=shift,
                reason=reason,
                dim=float(dim),
            )
            db.session.commit()
            flash("Установлено. Если слот был занят — предыдущий инструмент снят автоматически.", "success")
            return redirect(url_for("tooling.list_tooling"))

        # --- REMOVE ---
        if action == "REMOVE":
            if not (equipment and role and position):
                flash("Для REMOVE обязательны: MACHINE, ROLE и POSITION.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            remove_tool(tool, equipment, role, position, reason or "REMOVE")
            db.session.commit()
            flash("Снято.", "success")
            return redirect(url_for("tooling.list_tooling"))

        # --- REGRIND ---
        if action == "REGRIND":
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

        # --- Прочие события ---
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

    # GET → рендер формы
    return render_template(
        "tooling/event_form.html",
        actions=ALLOWED_ACTIONS,
        roles=ALLOWED_ROLES,
        positions=ALLOWED_POSITIONS,
        shifts=SHIFT_CHOICES,
        machines=machines,
        reasons=INSTALL_REASONS,
    )


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
