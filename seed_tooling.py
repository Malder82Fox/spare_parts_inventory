# -*- coding: utf-8 -*-
"""
seed_tooling.py — утилита для инициализации таблиц модуля TOOLING.

Режимы:
- python seed_tooling.py --create    → создать НЕДОСТАЮЩИЕ таблицы (без потери данных)
- python seed_tooling.py --reset     → удалить таблицы модуля и создать заново (ВНИМАНИЕ: данные по инструменту будут удалены)

Работает как с SQLite, так и с PostgreSQL.
"""

import argparse
from sqlalchemy import text

from app import create_app           # фабрика приложения (как в твоём проекте)
from extensions import db

# Импорт моделей, чтобы SQLAlchemy «знал» о таблицах
import tooling.models_tooling as TM   # noqa


def drop_tooling_tables():
    """Удаляем таблицы модуля в правильном порядке зависимостей."""
    # порядок важен: сначала события (ссылаются на всё), затем монтирования, затем слоты, потом сами инструменты и типы
    stmts = [
        "DROP TABLE IF EXISTS tooling_events",
        "DROP TABLE IF EXISTS tooling_mounts",
        "DROP TABLE IF EXISTS equipment_slots",
        "DROP TABLE IF EXISTS tooling",
        "DROP TABLE IF EXISTS tool_types",
    ]

    # Для PostgreSQL можно добавить CASCADE (не обязательно при правильном порядке, но на всякий случай):
    # если хочешь принудительно:  stmt.replace("DROP TABLE", "DROP TABLE IF EXISTS") + " CASCADE"
    for s in stmts:
        db.session.execute(text(s))
    db.session.commit()


def create_missing_tables():
    """Создаёт недостающие таблицы по текущим моделям (без ALTER уже существующих)."""
    db.create_all()
    db.session.commit()


def main():
    parser = argparse.ArgumentParser(description="Init Tooling DB tables")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--create", action="store_true", help="создать недостающие таблицы (без удаления)")
    grp.add_argument("--reset", action="store_true", help="удалить таблицы модуля и создать заново (данные будут потеряны)")

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.reset:
            print("→ Dropping tooling tables …")
            drop_tooling_tables()
            print("→ Creating tables …")
            create_missing_tables()
            print("✔ Готово: таблицы модуля Tooling пересозданы с нуля.")
        elif args.create:
            print("→ Creating missing tables …")
            create_missing_tables()
            print("✔ Готово: недостающие таблицы созданы (существующие не трогались).")


if __name__ == "__main__":
    main()
