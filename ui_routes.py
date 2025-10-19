# ui_routes.py — оболочка UI: домашняя страница-выбор и общие хелперы
from flask import Blueprint, render_template
from flask_login import login_required
from extensions import db

# Модели для KPI
from models import Part
try:
    from maintenance_models import WorkOrder
except Exception:
    WorkOrder = None

ui = Blueprint("ui", __name__)

@ui.route("/")
@login_required
def home():
    parts_count = db.session.query(Part).count()
    overdue_wos = 0
    open_wos = 0
    if WorkOrder is not None:
        from datetime import date
        open_wos = db.session.query(WorkOrder).filter(WorkOrder.status.in_(["open","in_progress"])).count()
        overdue_wos = db.session.query(WorkOrder).filter(WorkOrder.status=="open", WorkOrder.due_date < date.today()).count()
    return render_template("home.html",
                           parts_count=parts_count,
                           open_wos=open_wos,
                           overdue_wos=overdue_wos)
