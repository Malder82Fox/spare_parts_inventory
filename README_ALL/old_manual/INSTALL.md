# UI Shell (домашняя + переключатель модулей) — установка

1) Скопируйте файлы в проект:
   - `ui_routes.py` → в корень рядом с `app.py`
   - `templates/home.html` → в папку `templates/`
   - `templates/_module_switcher.html` → в папку `templates/`
   - `templates/_sidebar_maintenance.html` → в папку `templates/`
   - `templates/_sidebar_parts.html` → в папку `templates/`

2) Зарегистрируйте blueprint в `app.py`:
   ```python
   from ui_routes import ui
   app.register_blueprint(ui)
   ```

3) Подключите переключатель модулей в `templates/base.html` (под заголовком):
   ```html
   {% include '_module_switcher.html' %}
   {% include '_flash.html' %}
   ```

4) (Опционально) Префикс для Maintenance:
   В `app.py` регистрируйте:
   ```python
   from maintenance_routes import maintenance_bp
   app.register_blueprint(maintenance_bp, url_prefix="/maintenance")
   ```

5) Запуск:
   ```bash
   set FLASK_APP=app.py
   flask run
   ```
   После логина откроется `/` — домашняя с выбором модуля.
