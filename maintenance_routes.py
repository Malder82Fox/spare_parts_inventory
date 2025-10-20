# maintenance_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import date, datetime

from extensions import db
from maintenance_models import (
    Equipment, ChecklistTemplate, ChecklistItem,
    MaintenancePlan, WorkOrder, WorkOrderItem
)
from permissions import require_role

maintenance_bp = Blueprint("maintenance", __name__)

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
@require_role("root")
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
@require_role("root")
def equipment_edit(eid: int):
    eq = Equipment.query.get_or_404(eid)
    if request.method == "POST":
        for f in ["code", "name", "category", "location",
                  "vendor", "model", "serial_number", "sap_number", "notes"]:
            setattr(eq, f, request.form.get(f) or None)
        db.session.commit()
        flash("Equipment updated", "success")
        return redirect(url_for("maintenance.equipment_view", eid=eq.id))
    return render_template("maintenance/equipment_form.html", item=eq)

@maintenance_bp.route("/equipment/<int:eid>/delete", methods=["POST"])
@login_required
@require_role("root")
def equipment_delete(eid: int):
    eq = Equipment.query.get_or_404(eid)
    db.session.delete(eq)
    db.session.commit()
    flash("Equipment deleted", "success")
    return redirect(url_for("maintenance.equipment_list"))

# =================== CHECKLIST TEMPLATES ===================
@maintenance_bp.route("/checklists/templates")
@login_required
def checklist_templates_list():
    items = ChecklistTemplate.query.order_by(ChecklistTemplate.code.asc()).all()
    return render_template("maintenance/checklist_templates_list.html", items=items)

@maintenance_bp.route("/checklists/templates/add", methods=["GET", "POST"])
@login_required
@require_role("root", "admin")
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
        db.session.flush()

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
@require_role("root", "admin")
def checklist_template_edit(tid: int):
    tmpl = ChecklistTemplate.query.get_or_404(tid)
    if request.method == "POST":
        tmpl.code = request.form["code"].strip()
        tmpl.name_en = request.form["name_en"].strip()
        tmpl.name_ru = request.form["name_ru"].strip()
        tmpl.category = request.form.get("category") or None
        tmpl.default_frequency = request.form.get("default_frequency") or "daily"

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
    return render_template("maintenance/checklist_template_form.html",
                           item=tmpl, items_raw="\n".join(raw))

@maintenance_bp.route("/checklists/templates/<int:tid>/delete", methods=["POST"])
@login_required
@require_role("root")
def checklist_template_delete(tid: int):
    tmpl = ChecklistTemplate.query.get_or_404(tid)
    ChecklistItem.query.filter_by(template_id=tmpl.id).delete()
    db.session.delete(tmpl)
    db.session.commit()
    flash("Checklist Template deleted", "success")
    return redirect(url_for("maintenance.checklist_templates_list"))

# =================== MAINTENANCE PLANS ===================
@maintenance_bp.route("/plans")
@login_required
def maintenance_plans_list():
    items = MaintenancePlan.query.order_by(MaintenancePlan.id.desc()).all()
    return render_template("maintenance/maintenance_plans_list.html", items=items)

@maintenance_bp.route("/plans/add", methods=["GET", "POST"])
@login_required
@require_role("root")
def maintenance_plan_add():
    if request.method == "POST":
        mp = MaintenancePlan(
            equipment_id=int(request.form["equipment_id"]),
            template_id=int(request.form["template_id"]),
            frequency=request.form.get("frequency") or "daily",
            grace_days=int(request.form.get("grace_days") or 0),
            next_due_date=date.fromisoformat(request.form.get("next_due_date"))
                          if request.form.get("next_due_date") else date.today()
        )
        db.session.add(mp)
        db.session.commit()
        flash("Maintenance Plan created", "success")
        return redirect(url_for("maintenance.maintenance_plans_list"))

    eqs = Equipment.query.order_by(Equipment.code.asc()).all()
    tpls = ChecklistTemplate.query.order_by(ChecklistTemplate.code.asc()).all()
    return render_template("maintenance/maintenance_plan_form.html", eqs=eqs, tpls=tpls)

@maintenance_bp.route("/plans/<int:pid>/edit", methods=["GET", "POST"])
@login_required
@require_role("root")
def maintenance_plan_edit(pid: int):
    mp = MaintenancePlan.query.get_or_404(pid)
    if request.method == "POST":
        mp.equipment_id = int(request.form["equipment_id"])
        mp.template_id  = int(request.form["template_id"])
        mp.frequency    = request.form.get("frequency") or mp.frequency
        mp.grace_days   = int(request.form.get("grace_days") or 0)
        if request.form.get("next_due_date"):
            mp.next_due_date = date.fromisoformat(request.form.get("next_due_date"))
        db.session.commit()
        flash("Maintenance Plan updated", "success")
        return redirect(url_for("maintenance.maintenance_plans_list"))

    eqs = Equipment.query.order_by(Equipment.code.asc()).all()
    tpls = ChecklistTemplate.query.order_by(ChecklistTemplate.code.asc()).all()
    return render_template("maintenance/maintenance_plan_form.html", item=mp, eqs=eqs, tpls=tpls)

@maintenance_bp.route("/plans/<int:pid>/delete", methods=["POST"])
@login_required
@require_role("root")
def maintenance_plan_delete(pid: int):
    mp = MaintenancePlan.query.get_or_404(pid)
    db.session.delete(mp)
    db.session.commit()
    flash("Maintenance Plan deleted", "success")
    return redirect(url_for("maintenance.maintenance_plans_list"))

@maintenance_bp.route("/plans/run", methods=["POST"])
@login_required
@require_role("root")
def maintenance_schedule_run():
    today = date.today()
    plans = MaintenancePlan.query.filter(MaintenancePlan.next_due_date <= today).all()
    created = 0
    for p in plans:
        # не создаём дубль "open" WO по плану
        exists = WorkOrder.query.filter_by(plan_id=p.id, status="open").first()
        if exists:
            continue
        wo = WorkOrder(
            equipment_id=p.equipment_id,
            template_id=p.template_id,
            plan_id=p.id,
            due_date=today,
            status="open",
            created_by=getattr(current_user, "id", None),
        )
        db.session.add(wo)
        db.session.flush()
        for ci in p.template.items:
            db.session.add(WorkOrderItem(workorder_id=wo.id, checklist_item_id=ci.id))
        # если в модели есть метод compute_next_due — используем
        if hasattr(p, "compute_next_due"):
            p.next_due_date = p.compute_next_due(today)
        else:
            p.next_due_date = today
        created += 1
    db.session.commit()
    flash(f"Scheduler: created {created} work orders", "info")
    return redirect(url_for("maintenance.workorders_list"))

# =================== WORK ORDERS ===================
@maintenance_bp.route("/workorders")
@login_required
def workorders_list():
    status = request.args.get("status")
    query = WorkOrder.query
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
@require_role("root", "admin", "user")
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
        if hasattr(wo, "closed_at"):
            wo.closed_at = datetime.utcnow()
        db.session.commit()
        flash("Work order submitted", "success")
        return redirect(url_for("maintenance.workorders_list"))

    return render_template("maintenance/workorder_fill.html", wo=wo)

@maintenance_bp.route("/workorders/<int:wid>/reopen", methods=["POST"])
@login_required
@require_role("root")
def workorder_reopen(wid:int):
    wo = WorkOrder.query.get_or_404(wid)
    if wo.status == "done":
        wo.status = "open"
        if hasattr(wo, "closed_at"): wo.closed_at = None
        db.session.commit()
        flash("Work order reopened", "success")
    return redirect(url_for("maintenance.workorders_list"))

@maintenance_bp.route("/workorders/new", methods=["POST"])
@login_required
@require_role("root")
def workorder_new():
    equipment_id = int(request.form["equipment_id"])
    template_id = int(request.form["template_id"])
    wo = WorkOrder(
        equipment_id=equipment_id,
        template_id=template_id,
        due_date=date.today(),
        status="open",
        created_by=getattr(current_user, "id", None),
    )
    db.session.add(wo)
    db.session.flush()
    tmpl = ChecklistTemplate.query.get(template_id)
    for ci in tmpl.items:
        db.session.add(WorkOrderItem(workorder_id=wo.id, checklist_item_id=ci.id))
    db.session.commit()
    flash("Work order created", "success")
    return redirect(url_for("maintenance.workorders_list"))

# УДАЛЕНИЕ WORK ORDER (только root)
@maintenance_bp.route("/workorders/<int:wid>/delete", methods=["POST"])
@login_required
@require_role("root")
def workorder_delete(wid: int):
    wo = WorkOrder.query.get_or_404(wid)
    # подчистим строки, если каскада нет
    WorkOrderItem.query.filter_by(workorder_id=wo.id).delete()
    db.session.delete(wo)
    db.session.commit()
    flash(f"Work order #{wid} deleted", "success")
    return redirect(url_for("maintenance.workorders_list"))

# Быстрая форма по QR: /maintenance/form?eq=CODE&tpl=TPL
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
