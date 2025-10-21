# -*- coding: utf-8 -*-
"""
Blueprint модуля «Инструментальная оснастка» (Tooling).
Этот файл нужен, чтобы Flask видел наш модуль как пакет и мог зарегистрировать блюпринт.
"""
from flask import Blueprint

# Создаём блюпринт. Имя 'tooling' попадёт в url_for('tooling.xxx')
tooling_bp = Blueprint("tooling", __name__)
