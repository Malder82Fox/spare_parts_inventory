# permissions.py
from functools import wraps
from flask import abort
from flask_login import current_user

def require_role(*roles):
    """Декоратор на роуты: пускаем только указанные роли."""
    roles = set(roles)
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return deco

# ---- флаги для шаблонов (UI) ----
def _is(*roles):  # helper
    return current_user.is_authenticated and current_user.role in roles

# Equipment
def can_equipment_create(): return _is("root")
def can_equipment_edit():   return _is("root")
def can_equipment_delete(): return _is("root")

# Checklist Templates
def can_tpl_create(): return _is("root","admin")
def can_tpl_edit():   return _is("root","admin")
def can_tpl_delete(): return _is("root")

# Maintenance Plans
def can_plan_create(): return _is("root")
def can_plan_edit():   return _is("root")
def can_plan_delete(): return _is("root")
def can_run_scheduler(): return _is("root")

# Work Orders
def can_wo_fill():    return _is("root","admin","user")
def can_wo_reopen():  return _is("root")
def can_wo_create_quick(): return _is("root")  # если используешь быстрые WO
def can_wo_delete(): return _is("root")