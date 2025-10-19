# maintenance_models.py
# Модели модуля обслуживания. Используем ЕДИНЫЙ db из extensions.py.
# Таблицы пользователей/запчастей подхватываем динамически по __tablename__.

from datetime import datetime, timedelta
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from extensions import db  # ЕДИНЫЙ экземпляр SQLAlchemy

# Пытаемся импортировать ваши модели, чтобы узнать реальные имена таблиц
try:
    from models import Part, User  # если User отсутствует – не страшно
except Exception:
    Part = None
    User = None

PART_TBL = getattr(Part, "__tablename__", "part")     # 'part' или 'parts'
USER_TBL = getattr(User, "__tablename__", "user")     # 'user' или 'users'


# ========== EQUIPMENT ==========
class Equipment(db.Model):
    __tablename__ = "equipment"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)   # BM-01
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(120))
    location = db.Column(db.String(120))
    status = db.Column(db.String(64), default="active")
    vendor = db.Column(db.String(120))
    model = db.Column(db.String(120))
    serial_number = db.Column(db.String(120))
    sap_number = db.Column(db.String(64))
    notes = db.Column(db.Text)
    photo_path = db.Column(db.String(255))

    # связи
    parts = relationship("Part", secondary="equipment_parts",
                         back_populates="equipments", lazy="dynamic")
    plans = relationship("MaintenancePlan", back_populates="equipment",
                         cascade="all, delete")
    workorders = relationship("WorkOrder", back_populates="equipment",
                              cascade="all, delete")

    def __repr__(self) -> str:
        return f"<Equipment {self.code}>"


# M2M связь Equipment ↔ Part (колонка part_id указывает на вашу реальную таблицу)
EquipmentParts = Table(
    "equipment_parts", db.metadata,
    Column("equipment_id", Integer,
           ForeignKey("equipment.id", ondelete="CASCADE"),
           primary_key=True),
    Column("part_id", Integer,
           ForeignKey(f"{PART_TBL}.id", ondelete="CASCADE"),
           primary_key=True),
    Column("quantity", Integer, default=1)
)

# Если у модели Part нет обратной связи — добавим её динамически
if Part is not None and not hasattr(Part, "equipments"):
    Part.equipments = relationship(
        "Equipment",
        secondary="equipment_parts",
        back_populates="parts",
        lazy="dynamic"
    )


# ========== CHECKLISTS ==========
class ChecklistTemplate(db.Model):
    __tablename__ = "checklist_templates"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)   # BM-Daily
    name_en = db.Column(db.String(255), nullable=False)
    name_ru = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(120))
    default_frequency = db.Column(db.String(32), default="daily")   # daily/weekly/monthly/quarterly/yearly/by_hours

    items = relationship("ChecklistItem", back_populates="template",
                         cascade="all, delete-orphan",
                         order_by="ChecklistItem.order_index")
    plans = relationship("MaintenancePlan", back_populates="template")


class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer,
                            db.ForeignKey("checklist_templates.id"),
                            nullable=False)
    order_index = db.Column(db.Integer, default=1)

    text_en = db.Column(db.String(255), nullable=False)
    text_ru = db.Column(db.String(255), nullable=False)

    field_type = db.Column(db.String(32), default="checkbox")  # checkbox|numeric|select|text
    options = db.Column(db.Text)   # CSV/JSON for select
    unit = db.Column(db.String(32))
    lower_bound = db.Column(db.Float)
    upper_bound = db.Column(db.Float)

    template = relationship("ChecklistTemplate", back_populates="items")


# ========== MAINTENANCE PLANS ==========
class MaintenancePlan(db.Model):
    __tablename__ = "maintenance_plans"

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer,
                             db.ForeignKey("equipment.id"),
                             nullable=False)
    template_id = db.Column(db.Integer,
                            db.ForeignKey("checklist_templates.id"),
                            nullable=False)

    frequency = db.Column(db.String(32), nullable=False)  # daily/weekly/monthly/quarterly/yearly/by_hours
    grace_days = db.Column(db.Integer, default=0)

    next_due_date = db.Column(db.Date)
    last_completed_at = db.Column(db.DateTime)

    equipment = relationship("Equipment", back_populates="plans")
    template = relationship("ChecklistTemplate", back_populates="plans")
    workorders = relationship("WorkOrder", back_populates="plan")

    def compute_next_due(self, from_date=None):
        from datetime import date
        base = from_date or date.today()
        if self.frequency == "daily":
            return base + timedelta(days=1)
        if self.frequency == "weekly":
            return base + timedelta(weeks=1)
        if self.frequency == "monthly":
            return base + timedelta(days=30)    # упрощённый расчёт
        if self.frequency == "quarterly":
            return base + timedelta(days=90)
        if self.frequency == "yearly":
            return base + timedelta(days=365)
        return base + timedelta(days=7)


# ========== WORK ORDERS ==========
class WorkOrder(db.Model):
    __tablename__ = "workorders"

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer,
                             db.ForeignKey("equipment.id"),
                             nullable=False)
    template_id = db.Column(db.Integer,
                            db.ForeignKey("checklist_templates.id"),
                            nullable=False)
    plan_id = db.Column(db.Integer,
                        db.ForeignKey("maintenance_plans.id"))

    due_date = db.Column(db.Date)
    status = db.Column(db.String(32), default="open")  # open|in_progress|done|rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    # используем реальное имя таблицы пользователей (user/users)
    created_by = db.Column(db.Integer, db.ForeignKey(f"{USER_TBL}.id"))
    assigned_to = db.Column(db.Integer, db.ForeignKey(f"{USER_TBL}.id"))

    equipment = relationship("Equipment", back_populates="workorders")
    template = relationship("ChecklistTemplate")
    plan = relationship("MaintenancePlan", back_populates="workorders")

    items = relationship("WorkOrderItem", back_populates="workorder",
                         cascade="all, delete-orphan")
    attachments = relationship("WorkOrderAttachment", back_populates="workorder",
                               cascade="all, delete-orphan")


class WorkOrderItem(db.Model):
    __tablename__ = "workorder_items"

    id = db.Column(db.Integer, primary_key=True)
    workorder_id = db.Column(db.Integer,
                             db.ForeignKey("workorders.id"),
                             nullable=False)
    checklist_item_id = db.Column(db.Integer,
                                  db.ForeignKey("checklist_items.id"),
                                  nullable=False)

    is_ok = db.Column(db.Boolean)
    value_numeric = db.Column(db.Float)
    value_text = db.Column(db.Text)
    value_select = db.Column(db.String(120))

    workorder = relationship("WorkOrder", back_populates="items")
    checklist_item = relationship("ChecklistItem")


class WorkOrderAttachment(db.Model):
    __tablename__ = "workorder_attachments"

    id = db.Column(db.Integer, primary_key=True)
    workorder_id = db.Column(db.Integer,
                             db.ForeignKey("workorders.id"),
                             nullable=False)
    path = db.Column(db.String(255), nullable=False)

    workorder = relationship("WorkOrder", back_populates="attachments")
