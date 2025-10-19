# app.py
from flask import Flask
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

# Импорт конфигурации и расширений
from config import Config
from extensions import db, login_manager

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'  # маршрут логина из твоего main-blueprint

    # Создание папки для загрузок, если не существует
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)

    # === Регистрация роутов существующего приложения ===
    from routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # === Регистрация модуля обслуживания (Maintenance) ===
    # Если хочешь, можешь добавить префикс: url_prefix="/maintenance"
    from maintenance_routes import maintenance_bp
    app.register_blueprint(maintenance_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    # Важно: импортируем модели обслуживания перед create_all(),
    # чтобы SQLAlchemy «увидел» их и создал таблицы.
    with app.app_context():
        from maintenance_models import *  # noqa: F401,F403
        db.create_all()
    app.run(debug=True)
