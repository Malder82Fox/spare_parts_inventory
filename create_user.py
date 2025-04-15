from app import create_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

app = create_app()

def create_user(username, password, role):
    with app.app_context():
        # Проверка на уникальность логина
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"⚠️  User '{username}' already exists with role '{existing_user.role}'.")
            return

        user = User(
            username=username,
            password=generate_password_hash(password),
            role=role
        )
        db.session.add(user)
        db.session.commit()
        print(f"✅ Created user: {username} (role: {role})")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Create a new user.')
    parser.add_argument('username', help='Username')
    parser.add_argument('password', help='Password')
    parser.add_argument('role', choices=['root', 'admin', 'user'], help='User role')

    args = parser.parse_args()
    create_user(args.username, args.password, args.role)
