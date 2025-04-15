from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Инициализация расширений без привязки к конкретному приложению

# База данных
db = SQLAlchemy()

# Авторизация и управление пользователями
login_manager = LoginManager()
