# Tooling Module — Импорт/Экспорт

## Экспорт
- Экспорт всей базы оснастки: `GET /tooling/export/csv`
- Экспорт истории конкретного инструмента: `GET /tooling/<tool_id>/export/history.csv`
- Скачать CSV-шаблон для импорта: `GET /tooling/export/template.csv`

## Импорт CSV
- Страница импорта: `GET /tooling/import` (доступно для admin/root)
- Поддерживается **upsert по tool_code**: если `tool_code` существует — запись обновляется, иначе создаётся новая.
- Минимально обязательные колонки: `tool_code`, `tool_type_code`
- Рекомендуемые колонки:
  `tool_code, tool_type_code, serial_number, intended_role, current_diameter, min_diameter, regrind_count, current_location, vendor, purchase_date (YYYY-MM-DD), cost, status, equipment_name, notes`
- Тип инструмента ищется по `tool_type_code` (если нет — создаётся).
- Машина (equipment) подхватывается по `equipment_name` (если найдена по имени).

## Миграция
- Выполните SQL из `migrations/20251021_tooling_full.sql`
- Или создайте Alembic-миграцию на основе этих изменений.

## Регистрация модуля
В `app.py`:
```python
from tooling.routes_tooling import tooling_bp
app.register_blueprint(tooling_bp, url_prefix="/tooling")

with app.app_context():
    import tooling.models_tooling  # до db.create_all()
    db.create_all()
```
