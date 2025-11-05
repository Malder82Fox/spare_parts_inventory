from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()

from config import Config  # noqa: E402  (load_dotenv needs to run first)
from extensions import db, login_manager  # noqa: E402  (load_dotenv needs to run first)


def create_app() -> Flask:
    """Application factory for the ERP platform."""

    app = Flask(__name__)
    app.config.from_object(Config)

    # init extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    # blueprints
    from modules.spare_parts import bp as spare_parts_bp
    from modules.maintenance import bp as maintenance_bp
    from modules.tooling import bp as tooling_bp

    app.register_blueprint(spare_parts_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(tooling_bp)

    from ui_routes import ui
    app.register_blueprint(ui)  # домашняя "/"

    # DB
    with app.app_context():
        # Важно: модели должны быть импортированы до create_all()
        from modules.spare_parts import models as spare_parts_models  # noqa: F401
        from modules.maintenance import models as maintenance_models  # noqa: F401
        from modules.tooling import models as tooling_models  # noqa: F401

        db.create_all()

    # uploads dir
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    # --- доступы в шаблоны Jinja ---
    from permissions import (
        can_equipment_create,
        can_equipment_edit,
        can_equipment_delete,
        can_tpl_create,
        can_tpl_edit,
        can_tpl_delete,
        can_plan_create,
        can_plan_edit,
        can_plan_delete,
        can_run_scheduler,
        can_wo_fill,
        can_wo_reopen,
        can_wo_create_quick,
        can_wo_delete,
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
