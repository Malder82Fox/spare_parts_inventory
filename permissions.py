# permissions.py
# -*- coding: utf-8 -*-
"""
RBAC для приложения.
- role_required([...]) — основной декоратор на роуты (root всегда имеет доступ).
- require_role(*roles) — обратная совместимость (делает то же самое).
- UI-хелперы can_* для шаблонов: возвращают True/False.

Роли:
- user   — базовые операции (ставить/снимать инструмент, сервисные операции, заполнение WO и т.п.)
- admin  — всё как user + добавление/импорт/экспорт, создание новых сущностей, где указано
- root   — полный доступ, редактирование/удаление
"""

from functools import wraps
from typing import Iterable, Set

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required


# ----------------------------- БАЗОВЫЙ ДЕКОРАТОР ----------------------------- #
def role_required(allowed_roles: Iterable[str]):
    """
    Декоратор для ограничения доступа по ролям.
    Пример:
        @role_required(["admin", "root"])
        def view(): ...

    Правила:
    - Неавторизованный → 401 (для API) или редирект на домашнюю (если HTML).
    - root имеет доступ всегда.
    - Если не хватает прав → 403 (API) или флеш + редирект на домашнюю (HTML).
    """
    # нормализуем множество ролей
    if isinstance(allowed_roles, str):
        allowed: Set[str] = {allowed_roles}
    else:
        allowed = set(allowed_roles or [])

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            role = getattr(current_user, "role", None)

            # root всегда может
            if role == "root" or role in allowed:
                return view_func(*args, **kwargs)

            # Выбираем поведение в зависимости от ожидаемого формата ответа
            wants_json = request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
            if wants_json:
                abort(403)

            flash("Недостаточно прав для этого действия.", "warning")
            # домашняя страница UI (подправь, если у тебя другой эндпоинт)
            return redirect(url_for("ui.home"))

        return wrapped
    return decorator


# ----------------------- ОБРАТНАЯ СОВМЕСТИМОСТЬ API ------------------------ #
def require_role(*roles: str):
    """
    Старый декоратор, оставлен для совместимости.
    Поведение эквивалентно role_required(list(roles)).
    Пример:
        @require_role("admin", "root")
    """
    return role_required(list(roles))


# --------------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ------------------------ #
def _is(*roles: str) -> bool:
    """Удобный helper для шаблонов: проверка роли текущего пользователя."""
    return bool(current_user.is_authenticated and getattr(current_user, "role", None) in roles or
                (current_user.is_authenticated and getattr(current_user, "role", None) == "root"))


# ================================ UI-ПРАВА ================================== #
# ---- Equipment (Maintenance) ----
def can_equipment_create(): return _is("admin")      # разрешим admin создавать
def can_equipment_edit():   return _is("admin")      # и редактировать
def can_equipment_delete(): return _is("root")       # удалять — только root

# ---- Checklist Templates ----
def can_tpl_create(): return _is("admin")
def can_tpl_edit():   return _is("admin")
def can_tpl_delete(): return _is("root")

# ---- Maintenance Plans ----
def can_plan_create():   return _is("admin")
def can_plan_edit():     return _is("admin")
def can_plan_delete():   return _is("root")
def can_run_scheduler(): return _is("root")

# ---- Work Orders ----
def can_wo_fill():         return _is("user", "admin")  # user/admin заполняют
def can_wo_reopen():       return _is("admin")          # или root, см. ниже
def can_wo_create_quick(): return _is("admin")
def can_wo_delete():       return _is("root")


# =============================== TOOLING (НОВОЕ) ============================= #
# Видеть список/карточку
def can_tooling_view():     return _is("user", "admin")     # (root тоже по умолчанию)

# Создавать новую оснастку (BATCH #) на склад
def can_tooling_create():   return _is("admin")

# Импорт/экспорт базы оснастки
def can_tooling_import():   return _is("admin")
def can_tooling_export():   return _is("admin")

# Операции над оснасткой (ставить/снимать/сервисные действия)
def can_tooling_operate():  return _is("user", "admin")

# Редактирование карточки/жёсткие операции
def can_tooling_edit():     return _is("root")              # правки чувствительных полей
def can_tooling_delete():   return _is("root")              # физическое/soft удаление
def can_tooling_scrap():    return _is("root")              # списание SCRAP


# =========================== ДОПОЛНИТЕЛЬНЫЕ ШОРТКАТЫ ======================== #
def has_role(role: str) -> bool:
    """True, если у текущего пользователя именно указанная роль (root не подменяет)."""
    return bool(current_user.is_authenticated and getattr(current_user, "role", None) == role)

def is_root() -> bool:
    return has_role("root")

def is_admin() -> bool:
    return has_role("admin")

def is_user() -> bool:
    return has_role("user")
