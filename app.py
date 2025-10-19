# app.py
from flask import Flask
from dotenv import load_dotenv
import os

# 1) .env
load_dotenv()

# 2) конфиг и расширения
from config import Config
from extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 3) init extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"  # поправь, если у тебя другой эндпоинт логина

    # 4) blueprints (с префиксами)
    from routes import main as parts_bp
    app.register_blueprint(parts_bp, url_prefix="/parts")  # модуль Запчасти

    from maintenance_routes import maintenance_bp
    app.register_blueprint(maintenance_bp, url_prefix="/maintenance")  # модуль ТО

    from ui_routes import ui
    app.register_blueprint(ui)  # домашняя "/"

    # 5) создать таблицы (важно: просто импортируем модуль, НЕ import *)
    with app.app_context():
        import maintenance_models  # noqa: F401  <-- этого достаточно, чтобы зарегистрировать модели
        db.create_all()

    # 6) uploads (если используется)
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
