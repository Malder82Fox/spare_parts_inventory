# maintenance_routes.py
# Blueprint с маршрутами модуля обслуживания.
# Пути без префикса: /equipment, /checklists/templates, /plans, /workorders, /form

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, datetime
from functools import wraps

from extensions import db
from maintenance_models import (
    Equipment, ChecklistTemplate, ChecklistItem,
    MaintenancePlan, WorkOrder, WorkOrderItem
)

maintenance_bp = Blueprint("maintenance", __name__)  # шаблоны лежат в templates/maintenance/*


# ---- Декоратор проверки ролей (не строгий: если роли нет — пропускаем) ----
def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                # @login_required сам отправит на login_view
                return login_required(fn)(*args, **kwargs)
            if hasattr(current_user, "role") and roles and current_user.role not in roles:
                flash("Permission denied", "danger")
                return redirect(url_for("maintenance.equipment_list"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# =================== EQUIPMENT ===================
@maintenance_bp.route("/equipment")
@login_required
def equipment_list():
    q = request.args.get("q", "").strip()
    query = Equipment.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Equipment.code.ilike(like)) |
            (Equipment.name.ilike(like)) |
            (Equipment.category.ilike(like))
        )
    items = query.order_by(Equipment.code.asc()).all()
    return render_template("maintenance/equipment_list.html", items=items, q=q)


@maintenance_bp.route("/equipment/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "root")
def equipment_add():
    if request.method == "POST":
        eq = Equipment(
            code=request.form["code"].strip(),
            name=request.form["name"].strip(),
            category=request.form.get("category") or None,
            location=request.form.get("location") or None,
            vendor=request.form.get("vendor") or None,
            model=request.form.get("model") or None,
            serial_number=request.form.get("serial_number") or None,
            sap_number=request.form.get("sap_number") or None,
            notes=request.form.get("notes") or None
        )
        db.session.add(eq)
        db.session.commit()
        flash("Equipment created", "success")
        return redirect(url_for("maintenance.equipment_list"))
    return render_template("maintenance/equipment_form.html", item=None)


@maintenance_bp.route("/equipment/<int:eid>")
@login_required
def equipment_view(eid: int):
    eq = Equipment.query.get_or_404(eid)
    return render_template("maintenance/equipment_view.html", item=eq)


@maintenance_bp.route("/equipment/<int:eid>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "root")
def equipment_edit(eid: int):
    eq = Equipment.query.get_or_404(eid)
    if request.method == "POST":
        for f in ["code", "name", "category", "location",
                  "vendor", "model", "serial_number", "sap_number", "notes"]:
            setattr(eq, f, request.form.get(f))
        db.session.commit()
        flash("Equipment updated", "success")
        return redirect(url_for("maintenance.equipment_view", eid=eq.id))
    return render_template("maintenance/equipment_form.html", item=eq)


# =================== CHECKLISTS ===================
@maintenance_bp.route("/checklists/templates")
@login_required
def checklist_templates_list():
    items = ChecklistTemplate.query.order_by(ChecklistTemplate.code.asc()).all()
    return render_template("maintenance/checklist_templates_list.html", items=items)


@maintenance_bp.route("/checklists/templates/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "root")
def checklist_template_add():
    if request.method == "POST":
        tmpl = ChecklistTemplate(
            code=request.form["code"].strip(),
            name_en=request.form["name_en"].strip(),
            name_ru=request.form["name_ru"].strip(),
            category=request.form.get("category") or None,
            default_frequency=request.form.get("default_frequency") or "daily"
        )
        db.session.add(tmpl)
        db.session.flush()  # получим tmpl.id

        # Формат строки: EN | RU | field_type | options
        rows = request.form.get("items_raw", "").splitlines()
        order = 1
        for row in rows:
            row = row.strip()
            if not row:
                continue
            parts = [p.strip() for p in row.split("|")]
            text_en = parts[0]
            text_ru = parts[1] if len(parts) > 1 else parts[0]
            field_type = parts[2] if len(parts) > 2 else "checkbox"
            options = parts[3] if len(parts) > 3 else None

            db.session.add(ChecklistItem(
                template_id=tmpl.id,
                order_index=order,
                text_en=text_en,
                text_ru=text_ru,
                field_type=field_type,
                options=options
            ))
            order += 1

        db.session.commit()
        flash("Checklist Template created", "success")
        return redirect(url_for("maintenance.checklist_templates_list"))

    return render_template("maintenance/checklist_template_form.html", item=None)


@maintenance_bp.route("/checklists/templates/<int:tid>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "root")
def checklist_template_edit(tid: int):
    tmpl = ChecklistTemplate.query.get_or_404(tid)
    if request.method == "POST":
        tmpl.code = request.form["code"].strip()
        tmpl.name_en = request.form["name_en"].strip()
        tmpl.name_ru = request.form["name_ru"].strip()
        tmpl.category = request.form.get("category") or None
        tmpl.default_frequency = request.form.get("default_frequency") or "daily"

        # перезаписываем пункты
        ChecklistItem.query.filter_by(template_id=tmpl.id).delete()

        rows = request.form.get("items_raw", "").splitlines()
        order = 1
        for row in rows:
            row = row.strip()
            if not row:
                continue
            parts = [p.strip() for p in row.split("|")]
            text_en = parts[0]
            text_ru = parts[1] if len(parts) > 1 else parts[0]
            field_type = parts[2] if len(parts) > 2 else "checkbox"
            options = parts[3] if len(parts) > 3 else None

            db.session.add(ChecklistItem(
                template_id=tmpl.id,
                order_index=order,
                text_en=text_en,
                text_ru=text_ru,
                field_type=field_type,
                options=options
            ))
            order += 1

        db.session.commit()
        flash("Checklist Template updated", "success")
        return redirect(url_for("maintenance.checklist_templates_list"))

    raw = []
    for it in tmpl.items:
        raw.append(f"{it.text_en} | {it.text_ru} | {it.field_type} | {it.options or ''}")
    return render_template("maintenance/checklist_template_form.html", item=tmpl,
                           items_raw="\n".join(raw))


# =================== MAINTENANCE PLANS ===================
@maintenance_bp.route("/plans")
@login_required
def maintenance_plans_list():
    items = MaintenancePlan.query.order_by(MaintenancePlan.id.desc()).all()
    return render_template("maintenance/maintenance_plans_list.html", items=items)


@maintenance_bp.route("/plans/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "root")
def maintenance_plan_add():
    if request.method == "POST":
        equipment_id = int(request.form["equipment_id"])
        template_id = int(request.form["template_id"])
        mp = MaintenancePlan(
            equipment_id=equipment_id,
            template_id=template_id,
            frequency=request.form.get("frequency") or "daily",
            grace_days=int(request.form.get("grace_days") or 0),
            next_due_date=date.fromisoformat(request.form.get("next_due_date")) if request.form.get("next_due_date") else date.today()
        )
        db.session.add(mp)
        db.session.commit()
        flash("Maintenance Plan created", "success")
        return redirect(url_for("maintenance.maintenance_plans_list"))

    eqs = Equipment.query.order_by(Equipment.code.asc()).all()
    tpls = ChecklistTemplate.query.order_by(ChecklistTemplate.code.asc()).all()
    return render_template("maintenance/maintenance_plan_form.html", eqs=eqs, tpls=tpls)


@maintenance_bp.route("/plans/schedule/run", methods=["POST"])
@login_required
@role_required("admin", "root")
def maintenance_schedule_run():
    today = date.today()
    plans = MaintenancePlan.query.filter(MaintenancePlan.next_due_date <= today).all()
    created = 0
    for p in plans:
        exists = WorkOrder.query.filter_by(plan_id=p.id, status="open").first()
        if exists:
            continue

        wo = WorkOrder(
            equipment_id=p.equipment_id,
            template_id=p.template_id,
            plan_id=p.id,
            due_date=today,
            status="open",
            created_by=getattr(current_user, "id", None)
        )
        db.session.add(wo)
        db.session.flush()

        for ci in p.template.items:
            db.session.add(WorkOrderItem(workorder_id=wo.id, checklist_item_id=ci.id))

        p.next_due_date = p.compute_next_due(today)
        db.session.commit()
        created += 1

    flash(f"Scheduler: created {created} work orders", "info")
    return redirect(url_for("maintenance.workorders_list"))


# =================== WORK ORDERS ===================
@maintenance_bp.route("/workorders")
@login_required
def workorders_list():
    status = request.args.get("status")
    query = WorkOrder.query.order_by(WorkOrder.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    items = query.all()
    return render_template("maintenance/workorders_list.html", items=items, status=status)


@maintenance_bp.route("/workorders/<int:wid>")
@login_required
def workorder_view(wid: int):
    wo = WorkOrder.query.get_or_404(wid)
    return render_template("maintenance/workorder_view.html", wo=wo)


@maintenance_bp.route("/workorders/<int:wid>/fill", methods=["GET", "POST"])
@login_required
def workorder_fill(wid: int):
    wo = WorkOrder.query.get_or_404(wid)
    if request.method == "POST":
        for item in wo.items:
            field_name = f"item_{item.id}"
            ci = item.checklist_item

            if ci.field_type == "checkbox":
                item.is_ok = (request.form.get(field_name) == "on")

            elif ci.field_type == "numeric":
                val = request.form.get(field_name)
                item.value_numeric = float(val) if val else None
                if (ci.lower_bound is not None and ci.upper_bound is not None
                        and item.value_numeric is not None):
                    item.is_ok = (ci.lower_bound <= item.value_numeric <= ci.upper_bound)

            elif ci.field_type == "select":
                item.value_select = request.form.get(field_name)
                item.is_ok = bool(item.value_select)

            else:  # text
                item.value_text = request.form.get(field_name)

        wo.status = "done"
        wo.closed_at = datetime.utcnow()
        db.session.commit()
        flash("Work order submitted", "success")
        return redirect(url_for("maintenance.workorders_list"))

    return render_template("maintenance/workorder_fill.html", wo=wo)


@maintenance_bp.route("/workorders/new", methods=["POST"])
@login_required
@role_required("admin", "root")
def workorder_new():
    equipment_id = int(request.form["equipment_id"])
    template_id = int(request.form["template_id"])
    wo = WorkOrder(
        equipment_id=equipment_id,
        template_id=template_id,
        due_date=date.today(),
        status="open",
        created_by=getattr(current_user, "id", None)
    )
    db.session.add(wo)
    db.session.flush()

    tmpl = ChecklistTemplate.query.get(template_id)
    for ci in tmpl.items:
        db.session.add(WorkOrderItem(workorder_id=wo.id, checklist_item_id=ci.id))

    db.session.commit()
    flash("Work order created", "success")
    return redirect(url_for("maintenance.workorders_list"))


# Публичная форма по QR: /form?eq=BM-01&tpl=BM-Daily
@maintenance_bp.route("/form")
@login_required
def form_qr():
    code = request.args.get("eq")
    tpl_code = request.args.get("tpl")
    eq = Equipment.query.filter_by(code=code).first_or_404()
    tpl = ChecklistTemplate.query.filter_by(code=tpl_code).first_or_404()

    wo = WorkOrder(
        equipment_id=eq.id,
        template_id=tpl.id,
        due_date=date.today(),
        status="open",
        created_by=getattr(current_user, "id", None)
    )
    db.session.add(wo)
    db.session.flush()

    for ci in tpl.items:
        db.session.add(WorkOrderItem(workorder_id=wo.id, checklist_item_id=ci.id))

    db.session.commit()
    return redirect(url_for("maintenance.workorder_fill", wid=wo.id))
