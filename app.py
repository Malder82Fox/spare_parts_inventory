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
    #login_manager.login_view = 'login'
    login_manager.login_view = 'main.login'

    # Создание папки для загрузок, если не существует
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Регистрация маршрутов через blueprint
    from routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)
