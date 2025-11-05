# -*- coding: utf-8 -*-
"""
МОДЕЛИ МОДУЛЯ TOOLING — версия под событийную логику из Google Sheet.
Главная идея: любой шаг — это событие (ACTION), а «состояние» инструмента
и «агрегированная строка» для списка получаются из последнего события.

Таблицы:
- ToolType         — справочник типов (минимально).
- Tooling          — карточка инструмента (BATCH # == tool_code, уникален).
- EquipmentSlot    — слот на оборудовании: (equipment_id, role, position) уникален.
- ToolingMount     — активное/историческое монтирование инструмента в слот.
- ToolingEvent     — Событие (ACTION) — как в твоём листе EVENTS.

Справочники (в коде):
- ALLOWED_ACTIONS  — CREATE, INSTALL, REMOVE, WASH, POLISH, INSPECT, REPAIR, REGRIND, MARK_READY, MARK_DEFECTIVE, SCRAP
- ALLOWED_SHIFTS   — TOOL ROOM, A, B, C (расширяемо)
- ALLOWED_ROLES    — IRONING, REDRAW DIE, и т.п. (можно расширять)
- ALLOWED_POSITIONS— '#1', '#2', '#3', ... (строки)

Авто-снятие:
- при INSTALL перед установкой нового инструмента в слот снимаем старый (закрываем mount, событие для «старого» пишется).
Контроль DIM:
- если есть current_diameter и min_diameter у инструмента, при INSTALL проверяем, что не ниже min_diameter.
"""
from datetime import datetime
from typing import Optional

from flask_login import current_user
from sqlalchemy import UniqueConstraint
from extensions import db

# ---------- Наборы значений (можно загрузить из БД, но пока — константы) ----------
ALLOWED_ACTIONS = [
    "CREATE", "INSTALL", "REMOVE",
    "WASH", "POLISH", "INSPECT", "REPAIR",
    "REGRIND", "MARK_READY", "MARK_DEFECTIVE",
    "SCRAP"
]
ALLOWED_SHIFTS = ["TOOL ROOM", "A", "B", "C", "ENGI"]
ALLOWED_ROLES  = ["IRONING", "REDRAW DIE", "REDRAW SLEEVE", "PUNCH", "NOSE", "DOME PLUG", "CLAMP RING"]    # добавляй свои
ALLOWED_POSITIONS = ["#1", "#2", "#3"]        # можно руками ввести любую строку
NEW_TRIAL_REASONS = {"NEW", "TRIAL"}          # ^ используем, чтобы отличать (новую/тестовую) установку

# ---------- МОДЕЛИ ----------

class ToolType(db.Model):
    __tablename__ = "tool_types"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)  # например "IRON-Ø63"
    name = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Tooling(db.Model):
    """
    Карточка инструмента = твой `BATCH #`.
    Остальное вытягиваем из последнего события.
    """
    __tablename__ = "tooling"
    id = db.Column(db.Integer, primary_key=True)
    tool_code = db.Column(db.String(128), unique=True, nullable=False)  # == BATCH #
    tool_type_id = db.Column(db.Integer, db.ForeignKey("tool_types.id"))
    serial_number = db.Column(db.String(128))
    intended_role = db.Column(db.String(64))  # справочно (необязательно)

    # Для контроля износа. Можно импортировать из CSV.
    current_diameter = db.Column(db.Numeric(10, 3))
    min_diameter = db.Column(db.Numeric(10, 3))
    regrind_count = db.Column(db.Integer, default=0)

    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    type = db.relationship("ToolType")

    # ------ Утилиты агрегирования (аналог твоего STOCK/PARTS листа) ------
    @property
    def last_event(self):
        return (ToolingEvent.query
                .filter_by(tool_id=self.id)
                .order_by(ToolingEvent.happened_at.desc())
                .first())

    def last_aggregate(self):
        """
        Возвращает словарь под таблицу: BATCH #, LAST DATE, LAST ACTION, STATUS,
        BM#, ROLE, POSITION, DIM, NEW DIM
        """
        ev = self.last_event
        return {
            "BATCH #": self.tool_code,
            "LAST DATE": ev.happened_at if ev else None,
            "LAST ACTION": ev.action if ev else None,
            "STATUS": ev.to_status if ev else "STOCK",
            "BM#": ev.machine_name if ev else None,
            "ROLE": ev.role if ev else self.intended_role,
            "POSITION": ev.position if ev else None,
            "DIM": ev.dimension if ev else None,
            "NEW DIM": ev.new_dimension if ev else None
        }

class EquipmentSlot(db.Model):
    """
    Уникальный слот на конкретном оборудовании для заданной роли и позиции.
    """
    __tablename__ = "equipment_slots"
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.id"), nullable=False)
    role = db.Column(db.String(64), nullable=False)
    position = db.Column(db.String(32), nullable=False)
    code = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("equipment_id", "role", "position", name="uq_slot_equipment_role_pos"),
    )

class ToolingMount(db.Model):
    """
    Интервал «на оборудовании в слоте».
    """
    __tablename__ = "tooling_mounts"
    id = db.Column(db.Integer, primary_key=True)
    tool_id = db.Column(db.Integer, db.ForeignKey("tooling.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("equipment_slots.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

class ToolingEvent(db.Model):
    """
    Событие — полностью повторяет структуру твоего листа EVENTS.
    """
    __tablename__ = "tooling_events"
    id = db.Column(db.Integer, primary_key=True)

    # Кто/где/когда
    user_name = db.Column(db.String(128))      # USER (как текст)
    machine_id = db.Column(db.Integer, db.ForeignKey("equipment.id"))
    machine_name = db.Column(db.String(128))   # BM# (текстовое имя машины)
    shift = db.Column(db.String(16))           # SHIFT (A/B/C/TOOL ROOM)
    happened_at = db.Column(db.DateTime, default=datetime.utcnow)  # DATE and TIME

    # Что сделали
    action = db.Column(db.String(32), nullable=False)  # ACTION
    reason = db.Column(db.String(255))                 # REASON
    note = db.Column(db.Text)                          # NOTE

    # Где именно в машине
    role = db.Column(db.String(64))       # ROLE
    position = db.Column(db.String(32))   # POSITION
    slot_id = db.Column(db.Integer, db.ForeignKey("equipment_slots.id"))

    # Измерения
    dimension = db.Column(db.Numeric(10, 3))     # DIM (до)
    new_dimension = db.Column(db.Numeric(10, 3)) # NEW DIM (после)

    # Что именно
    tool_id = db.Column(db.Integer, db.ForeignKey("tooling.id"), nullable=False)
    batch_no = db.Column(db.String(128))  # BATCH #

    # «Перевод статуса» (снятие/установка/готов и т.п.) — храним в событии
    from_status = db.Column(db.String(32))
    to_status = db.Column(db.String(32))

# ---------- Доменные операции ----------

def ensure_slot(equipment, role: str, position: str) -> EquipmentSlot:
    """
    Находит или создаёт слот на машине под ROLE/POSITION.
    """
    code = f"{equipment.code or equipment.name}:{role}:{position}"
    slot = (EquipmentSlot.query
            .filter_by(equipment_id=equipment.id, role=role, position=position)
            .first())
    if slot:
        return slot
    slot = EquipmentSlot(equipment_id=equipment.id, role=role, position=position, code=code)
    db.session.add(slot)
    db.session.flush()
    return slot

def active_mount_in_slot(slot_id: int) -> Optional[ToolingMount]:
    return (ToolingMount.query
            .filter_by(slot_id=slot_id, ended_at=None)
            .first())

def uninstall_current_from_slot(slot: EquipmentSlot, reason: str = "Auto-uninstall (new INSTALL)") -> Optional[ToolingEvent]:
    """
    Если слот занят — снимаем установленный инструмент.
    Создаём событие REMOVE для снятого инструмента.
    """
    mount = active_mount_in_slot(slot.id)
    if not mount:
        return None

    tool = Tooling.query.get(mount.tool_id)
    mount.ended_at = datetime.utcnow()
    # событие для снятого
    ev = ToolingEvent(
        user_name=(getattr(current_user, "username", None) or "system"),
        machine_id=slot.equipment_id,
        machine_name=None,
        shift=None,
        happened_at=datetime.utcnow(),
        action="REMOVE",
        reason=reason,
        note=None,
        role=slot.role,
        position=slot.position,
        slot_id=slot.id,
        dimension=tool.current_diameter,
        new_dimension=None,
        tool_id=tool.id,
        batch_no=tool.tool_code,
        from_status="INSTALLED",
        to_status="NEED_SERVICE",
    )
    db.session.add(ev)
    db.session.flush()
    return ev


def install_tool(tool: Tooling, equipment, role: str, position: str, shift: str, reason: str, dim: Optional[float]):
    """
    Установка с авто-снятием предыдущего инструмента из этого же слота.
    ВАЖНО:
    - Если REASON не NEW/TRIAL — она сохраняется в событии REMOVE у ПРЕЖНЕГО инструмента (автоснятие).
    - Если REASON = NEW/TRIAL — причина остаётся у INSTALL НОВОГО инструмента.
    - При передаче DIM — обновляем tool.current_diameter.
    """
    slot = ensure_slot(equipment, role, position)

    # Контроль DIM (если заданы пороги)
    if tool.min_diameter is not None and tool.current_diameter is not None:
        if float(tool.current_diameter) < float(tool.min_diameter):
            raise ValueError("Нельзя устанавливать инструмент ниже min_diameter")

    # 1) авто-снять того, кто уже стоит
    #    Причина уходит в снятый инструмент, КРОМЕ NEW/TRIAL.
    remove_reason = None if (reason or "").upper() in NEW_TRIAL_REASONS else reason
    uninstall_current_from_slot(slot, reason=remove_reason)

    # 2) создать mount для нового
    mount = ToolingMount(tool_id=tool.id, slot_id=slot.id, created_by_id=getattr(current_user, "id", 1))
    db.session.add(mount)

    # 3) событие INSTALL (причина только для NEW/TRIAL)
    install_reason = reason if (reason or "").upper() in NEW_TRIAL_REASONS else None
    ev = ToolingEvent(
        user_name=(getattr(current_user, "username", None) or "system"),
        machine_id=equipment.id,
        machine_name=getattr(equipment, "name", None) or getattr(equipment, "code", None),
        shift=shift,
        happened_at=datetime.utcnow(),
        action="INSTALL",
        reason=install_reason,
        role=role,
        position=position,
        slot_id=slot.id,
        dimension=dim,
        new_dimension=None,
        tool_id=tool.id,
        batch_no=tool.tool_code,
        from_status="READY",
        to_status="INSTALLED",
    )
    db.session.add(ev)

    # 4) Обновим текущий диаметр, если указан
    if dim is not None:
        try:
            tool.current_diameter = dim
        except Exception:
            pass

    return ev

def remove_tool(tool: Tooling, equipment, role: str, position: str, reason: str):
    """
    Снятие инструмента с указанного слота (если стоит).
    """
    slot = ensure_slot(equipment, role, position)
    mount = active_mount_in_slot(slot.id)
    if mount and mount.tool_id == tool.id:
        mount.ended_at = datetime.utcnow()
    ev = ToolingEvent(
        user_name=(getattr(current_user, "username", None) or "system"),
        machine_id=equipment.id,
        machine_name=getattr(equipment, "name", None) or getattr(equipment, "code", None),
        shift=None,
        happened_at=datetime.utcnow(),
        action="REMOVE",
        reason=reason,
        role=role,
        position=position,
        slot_id=slot.id,
        dimension=tool.current_diameter,
        new_dimension=None,
        tool_id=tool.id,
        batch_no=tool.tool_code,
        from_status="INSTALLED",
        to_status="NEED_SERVICE",
    )
    db.session.add(ev)
    return ev


def regrind_tool(tool: Tooling, dimension: Optional[float], new_dimension: Optional[float], reason: str, shift: Optional[str]):
    """
    Перешлифовка:
    - увеличиваем счётчик,
    - обновляем current_diameter (если пришёл new_dimension, иначе оставляем как есть),
    - переводим инструмент в статус STOCK.
    """
    tool.regrind_count = (tool.regrind_count or 0) + 1
    if new_dimension is not None:
        tool.current_diameter = new_dimension

    ev = ToolingEvent(
        user_name=(getattr(current_user, "username", None) or "system"),
        machine_id=None,
        machine_name=None,
        shift=shift,
        happened_at=datetime.utcnow(),
        action="REGRIND",
        reason=reason,
        role=None,
        position=None,
        slot_id=None,
        dimension=dimension,
        new_dimension=new_dimension,
        tool_id=tool.id,
        batch_no=tool.tool_code,
        from_status="NEED_SERVICE",
        to_status="STOCK",
    )
    db.session.add(ev)
    return ev
