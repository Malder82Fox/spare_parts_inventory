# seed_maintenance.py
from datetime import date
from extensions import db
from maintenance_models import Equipment, ChecklistTemplate, ChecklistItem, MaintenancePlan

def run():
    eq = Equipment.query.filter_by(code="BM-01").first()
    if not eq:
        eq = Equipment(code="BM-01", name="Bodymaker", category="Bodymaker", location="Line A")
        db.session.add(eq)
        db.session.flush()

    tmpl = ChecklistTemplate.query.filter_by(code="BM-Daily").first()
    if not tmpl:
        tmpl = ChecklistTemplate(
            code="BM-Daily",
            name_en="Bodymaker — Daily",
            name_ru="Бодимейкер — Ежедневный",
            default_frequency="daily"
        )
        db.session.add(tmpl); db.session.flush()

        rows = [
            ("Main air pressure within range", "Давление основного воздуха в норме", "checkbox", ""),
            ("Lube level sight glass OK", "Уровень смазки по смотровому стеклу ОК", "checkbox", ""),
            ("Top wall thickness (mm)", "Толщина верхней стенки (мм)", "numeric", ""),
            ("Unusual noise", "Посторонний шум", "select", "OK,Monitor,Stop line"),
            ("Comments", "Комментарий", "text", ""),
        ]
        order = 1
        for en, ru, ftype, opts in rows:
            db.session.add(ChecklistItem(
                template_id=tmpl.id,
                order_index=order,
                text_en=en,
                text_ru=ru,
                field_type=ftype,
                options=opts or None
            ))
            order += 1

    plan = MaintenancePlan.query.filter_by(equipment_id=eq.id, template_id=tmpl.id, frequency="daily").first()
    if not plan:
        plan = MaintenancePlan(
            equipment_id=eq.id,
            template_id=tmpl.id,
            frequency="daily",
            next_due_date=date.today()
        )
        db.session.add(plan)

    db.session.commit()
    print("Seed OK: BM-01, BM-Daily, daily plan created.")
