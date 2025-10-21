from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()

from config import Config
from extensions import db, login_manager

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # init extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    # blueprints
    from routes import main as parts_bp
    app.register_blueprint(parts_bp, url_prefix="/parts")

    from maintenance_routes import maintenance_bp
    app.register_blueprint(maintenance_bp, url_prefix="/maintenance")

    # 🔹 Tooling (инструментальная оснастка)
    # Важно: импортируем блюпринт и регистрируем модуль
    # 🔹 Tooling (инструментальная оснастка)
    from tooling.routes_tooling import tooling_bp
    app.register_blueprint(tooling_bp, url_prefix="/tooling")
#    from tooling.notuse_routes_tooling import tooling_bp
#    app.register_blueprint(tooling_bp, url_prefix="/tooling")

    from ui_routes import ui
    app.register_blueprint(ui)  # домашняя "/"

    # DB
    with app.app_context():
        # Важно: модели должны быть импортированы до create_all()
        import maintenance_models   # чтобы модели ТО загрузились
        import tooling.models_tooling  # 🔹 модели оснастки
        db.create_all()

    # uploads dir
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    # --- доступы в шаблоны Jinja ---
    from permissions import (
        can_equipment_create, can_equipment_edit, can_equipment_delete,
        can_tpl_create, can_tpl_edit, can_tpl_delete,
        can_plan_create, can_plan_edit, can_plan_delete, can_run_scheduler,
        can_wo_fill, can_wo_reopen, can_wo_create_quick,
        can_wo_fill, can_wo_reopen, can_wo_create_quick, can_wo_delete
    )
    @app.context_processor
    def inject_perms():
        return dict(
            can_equipment_create=can_equipment_create,
            can_equipment_edit=can_equipment_edit,
            can_equipment_delete=can_equipment_delete,
            can_tpl_create=can_tpl_create, can_tpl_edit=can_tpl_edit, can_tpl_delete=can_tpl_delete,
            can_plan_create=can_plan_create, can_plan_edit=can_plan_edit, can_plan_delete=can_plan_delete,
            can_run_scheduler=can_run_scheduler,
            can_wo_fill=can_wo_fill, can_wo_reopen=can_wo_reopen, can_wo_create_quick=can_wo_create_quick,
            can_wo_delete=can_wo_delete,
        )

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
