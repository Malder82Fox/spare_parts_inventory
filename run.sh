#!/usr/bin/env bash
set -e

# ---- настройки по умолчанию (можешь поменять) ----
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
FLASK_APP_PATH="${FLASK_APP_PATH:-app.py}"

# ---- активируем venv (должен быть ./venv) ----
if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "ERROR: venv не найден. Создай его:  python3 -m venv venv && source venv/bin/activate"
  exit 1
fi

# ---- зависимости (если есть файл) ----
if [ -f "requirements.txt" ]; then
  python -m pip install --upgrade pip wheel setuptools >/dev/null
  pip install -r requirements.txt
fi

# ---- запуск Flask ----
export FLASK_APP="$FLASK_APP_PATH"
echo "Starting Flask on ${HOST}:${PORT} ..."
exec flask run --host="${HOST}" --port="${PORT}"
