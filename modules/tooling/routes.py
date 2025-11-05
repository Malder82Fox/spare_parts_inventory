# tooling/routes_tooling.py
# -*- coding: utf-8 -*-

from datetime import datetime
from decimal import Decimal, InvalidOperation
import csv
import io

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    make_response,
    jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import desc

from extensions import db
from modules.maintenance.models import Equipment
from modules.tooling.models import (
    Tooling,
    ToolType,
    ToolingEvent,
    ALLOWED_ACTIONS,
    ALLOWED_ROLES,
    ALLOWED_POSITIONS,
    install_tool,
    remove_tool,
    regrind_tool,
)
from permissions import role_required

from . import bp

# ---------- Справочники для UI ----------
SHIFT_CHOICES = ["Tooling room", "A", "B", "C", "D"]

INSTALL_REASONS = [
    "Top wall variation","Top wall oversize","Short trim","Sensor short can","Sugar scoop","Short can",
    "Die scratches","Die worn","Oval can","Progression","Mid wall below specification",
    "Progression mark horizontal","Progression mark vertical","Top wall undersize","Defective die","Die damage",
    "Trial","No reason","Pin hole","Pick up","Shadows","Roll back","Metal exposure","Chime smile","Dome depth",
    "Wrinkled domes","Slivers","Burrs","Uneven trim","Trimmer jams","Split flanges","Scheduled change","New",
]

# ---------- Утилиты ----------
def _parse_num(s: str | None):
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


# ---------- Список агрегированный ----------
@bp.route("/")
@login_required
def list_tooling():
    tools = Tooling.query.filter_by(is_active=True).order_by(desc(Tooling.updated_at)).all()
    rows = []
    for t in tools:
        a = t.last_aggregate()
        a["id"] = t.id
        rows.append(a)
    return render_template("tooling/list_tooling.html", rows=rows)


# ---------- Карточка BATCH ----------
@bp.route("/<int:tool_id>")
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


# ---------- Отчёт: что сейчас установлено ----------
@bp.route("/report/installed")
@login_required
def report_installed():
    """
    Информационный отчёт по текущим установленным инструментам.
    Фильтрация по STATUS делается через агрегатор last_aggregate(),
    т.к. в модели Tooling нет колонки 'status'.
    """
    tools = (Tooling.query
             .filter_by(is_active=True)
             .order_by(Tooling.tool_code.asc())
             .all())

    rows = []
    for t in tools:
        agg = t.last_aggregate() or {}
        if agg.get("STATUS") == "INSTALLED":
            rows.append({
                "id": t.id,
                "batch": t.tool_code,
                "bm": agg.get("BM#"),
                "role": agg.get("ROLE"),
                "pos": agg.get("POSITION"),
                "dim": agg.get("DIM"),
            })

    return render_template("tooling/report_installed.html", rows=rows)


# ---------- Новый BATCH ----------
@bp.route("/new", methods=["GET", "POST"])
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
            current_diameter=float(dim) if dim is not None else None,
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


# ---------- Универсальная форма события ----------
@bp.route("/event", methods=["GET", "POST"])
@login_required
def tooling_event():
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

        if not batch or action not in ALLOWED_ACTIONS:
            flash("Укажи BATCH # и корректный ACTION.", "warning")
            return redirect(url_for("tooling.tooling_event"))

        tool = Tooling.query.filter_by(tool_code=batch).first()
        if not tool:
            flash("Такого BATCH # нет. Сначала создай его через «Новый BATCH #».", "warning")
            return redirect(url_for("tooling.tooling_new"))

        equipment = Equipment.query.get(int(machine_id)) if machine_id else None

        # --- INSTALL ---
        if action == "INSTALL":
            if not role:
                flash("Для INSTALL необходимо указать ROLE.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            if role == "IRONING" and not position:
                flash("Для INSTALL с ROLE=IRONING необходимо указать POSITION.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            if not equipment:
                flash("Для INSTALL необходимо выбрать MACHINE (BM#).", "warning")
                return redirect(url_for("tooling.tooling_event"))
            if not shift or shift not in SHIFT_CHOICES:
                flash("Для INSTALL необходимо выбрать SHIFT.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            if dim is None:
                flash("Для INSTALL необходимо указать DIM.", "warning")
                return redirect(url_for("tooling.tooling_event"))
            if not reason or reason not in INSTALL_REASONS:
                flash("Для INSTALL необходимо выбрать REASON из списка.", "warning")
                return redirect(url_for("tooling.tooling_event"))

            install_tool(tool=tool, equipment=equipment, role=role, position=position,
                         shift=shift, reason=reason, dim=float(dim))
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
            regrind_tool(tool,
                         float(dim) if dim is not None else None,
                         float(new_dim) if new_dim is not None else None,
                         reason or "REGRIND", shift)
            db.session.commit()
            flash("Перешлифовка зафиксирована.", "success")
            return redirect(url_for("tooling.list_tooling"))

        # --- Прочие события ---
        ev = ToolingEvent(
            user_name=getattr(current_user, "username", "user"),
            machine_id=equipment.id if equipment else None,
            machine_name=(getattr(equipment, "name", None) or getattr(equipment, "code", None)) if equipment else None,
            shift=shift, happened_at=datetime.utcnow(), action=action,
            reason=reason, note=note, role=role, position=position, slot_id=None,
            dimension=dim, new_dimension=new_dim, tool_id=tool.id, batch_no=tool.tool_code,
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

    # GET
    return render_template("tooling/event_form.html",
                           actions=ALLOWED_ACTIONS,
                           roles=ALLOWED_ROLES,
                           positions=ALLOWED_POSITIONS,
                           shifts=SHIFT_CHOICES,
                           machines=machines,
                           reasons=INSTALL_REASONS)

# ---------- API: инфо по BATCH для автоподстановки DIM/ROLE ----------
@bp.route("/api/tool/<string:batch_no>")
@login_required
def api_tool_info(batch_no: str):
    tool = Tooling.query.filter_by(tool_code=batch_no.strip()).first()
    if not tool:
        return jsonify(ok=False, error="not found"), 404
    return jsonify(ok=True, dim=tool.current_diameter, role=tool.intended_role)


# ---------- Экспорт агрегированного списка ----------
@bp.route("/export/csv")
@role_required(["admin", "root"])
def export_csv():
    tools = Tooling.query.filter_by(is_active=True).order_by(desc(Tooling.updated_at)).all()
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
    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename=tooling_export_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return resp


# ---------- Экспорт истории событий конкретного BATCH ----------
@bp.route("/<int:tool_id>/export/events.csv")
@login_required
def export_tool_events(tool_id: int):
    tool = Tooling.query.get_or_404(tool_id)
    events = (ToolingEvent.query
              .filter_by(tool_id=tool_id)
              .order_by(ToolingEvent.happened_at.asc())
              .all())

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow([
        "BATCH #", "DATE", "ACTION", "FROM_STATUS", "TO_STATUS",
        "BM#", "ROLE", "POSITION", "SHIFT", "REASON",
        "DIM", "NEW_DIM", "USER", "NOTE"
    ])
    for e in events:
        writer.writerow([
            tool.tool_code,
            e.happened_at.isoformat(sep=" ") if e.happened_at else "",
            e.action or "",
            e.from_status or "",
            e.to_status or "",
            (e.machine_name or ""),
            e.role or "",
            e.position or "",
            e.shift or "",
            e.reason or "",
            e.dimension if e.dimension is not None else "",
            e.new_dimension if e.new_dimension is not None else "",
            e.user_name or "",
            e.note or "",
        ])

    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = \
        f"attachment; filename=tool_{tool.tool_code}_events_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return resp

@bp.route("/search")
@login_required
def tooling_search():
    """
    Быстрый поиск по BATCH #.
    Если нашли ровно один инструмент — сразу открываем его карточку.
    Иначе показываем таблицу результатов.
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        flash("Введите BATCH # для поиска.", "warning")
        return redirect(url_for("tooling.list_tooling"))

    # Ищем среди активных, но можно убрать filter_by(is_active=True), если нужно искать вообще все
    query = (Tooling.query
             .filter_by(is_active=True)
             .filter(Tooling.tool_code.ilike(f"%{q}%"))
             .order_by(Tooling.tool_code.asc()))

    items = query.all()

    # Если точное совпадение (без учета регистра) всего одно — сразу в карточку
    exact = [t for t in items if t.tool_code.lower() == q.lower()]
    if len(exact) == 1:
        return redirect(url_for("tooling.tooling_detail", tool_id=exact[0].id))

    if len(items) == 1:
        return redirect(url_for("tooling.tooling_detail", tool_id=items[0].id))

    # Иначе — собираем агрегированные строки
    rows = []
    for t in items:
        a = t.last_aggregate() or {}
        rows.append({
            "id": t.id,
            "batch": t.tool_code,
            "status": a.get("STATUS"),
            "bm": a.get("BM#"),
            "role": a.get("ROLE"),
            "pos": a.get("POSITION"),
            "dim": a.get("DIM"),
            "last_date": a.get("LAST DATE"),
            "last_action": a.get("LAST ACTION"),
        })

    return render_template("tooling/search_results.html", q=q, rows=rows)


# ---------- Заглушка импорта ----------
@bp.route("/import", methods=["GET", "POST"])
@role_required(["admin", "root"])
def import_tooling():
    if request.method == "POST":
        flash("Импорт CSV появится в следующей итерации. Пока используйте «Новый BATCH #» и «События».", "warning")
        return redirect(url_for("tooling.list_tooling"))
    return render_template("tooling/import_placeholder.html")
