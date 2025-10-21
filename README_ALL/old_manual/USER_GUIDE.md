# Parts & Maintenance — Руководство пользователя и установка

## Содержание
- [1. Обзор системы](#1-обзор-системы)
- [2. Требования](#2-требования)
- [3. Установка и первый запуск](#3-установка-и-первый-запуск)
  - [3.1 Структура проекта](#31-структура-проекта)
  - [3.2 Виртуальное окружение и зависимости](#32-виртуальное-окружение-и-зависимости)
  - [3.3 Конфигурация .env](#33-конфигурация-env)
  - [3.4 Первый запуск](#34-первый-запуск)
  - [3.5 Создание пользователей](#35-создание-пользователей)
- [4. Навигация и адреса модулей](#4-навигация-и-адреса-модулей)
- [5. Модуль «Запчасти»](#5-модуль-запчасти)
  - [5.1 Каталог и поиск](#51-каталог-и-поиск)
  - [5.2 Добавление вручную](#52-добавление-вручную)
  - [5.3 Импорт/Экспорт Excel](#53-импортэкспорт-excel)
  - [5.4 Фото](#54-фото)
- [6. Модуль «Обслуживание» (ТО)](#6-модуль-обслуживание-то)
  - [6.1 Сущности](#61-сущности)
  - [6.2 Оборудование](#62-оборудование)
  - [6.3 Шаблоны чек-листов](#63-шаблоны-чек-листов)
  - [6.4 Планы ТО](#64-планы-то)
  - [6.5 Планировщик → Work Orders](#65-планировщик--work-orders)
  - [6.6 Заполнение Work Order](#66-заполнение-work-order)
  - [6.7 Быстрая форма (QR/ссылка)](#67-быстрая-форма-qrссылка)
- [7. Полезные утилиты](#7-полезные-утилиты)
- [8. Типичные ошибки и решения](#8-типичные-ошибки-и-решения)
- [9. Рекомендации по кодированию](#9-рекомендации-по-кодированию)
- [10. Продакшен-запуск (кратко)](#10-продакшен-запуск-кратко)
- [11. Планируемые расширения](#11-планируемые-расширения)
- [12. Чек-лист «от нуля до первого WO»](#12-чек-лист-от-нуля-до-первого-wo)

---

## 1. Обзор системы

**Parts & Maintenance** — веб-приложение на Flask из двух модулей:

- **Parts (Запчасти)**: каталог, поиск, импорт/экспорт Excel, карточки деталей, фото.
- **Maintenance (Обслуживание)**: оборудование, шаблоны чек-листов, планы ТО, формирование нарядов (Work Orders, WO) и их закрытие.

После входа — домашняя страница с выбором модуля. Наверху: переключатель модулей и глобальный поиск (Ctrl+K). Слева на страницах модулей — контекстный сайдбар.

---

## 2. Требования

- Python **3.10+** (Windows / Linux / macOS)
- pip или conda
- Git (по желанию)
- База по умолчанию: **SQLite** (файл `instance/app.db` создаётся автоматически)

---

## 3. Установка и первый запуск

### 3.1 Структура проекта

```
spare_parts_inventory/
├─ app.py
├─ config.py
├─ extensions.py
├─ models.py                 # пользователи и модуль запчастей
├─ routes.py                 # блюпринт Parts (url-префикс /parts)
├─ maintenance_models.py     # модели ТО
├─ maintenance_routes.py     # блюпринт Maintenance (url-префикс /maintenance)
├─ ui_routes.py              # домашняя "/" и переключатель модулей
├─ templates/                # шаблоны (включая _sidebar_*.html, home.html, base.html)
├─ requirements.txt
└─ ...
```

### 3.2 Виртуальное окружение и зависимости

**Windows (PowerShell):**
```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Если `requirements.txt` пуст/отсутствует, установите вручную:  
> `pip install Flask Flask-Login Flask-SQLAlchemy SQLAlchemy python-dotenv openpyxl`

### 3.3 Конфигурация .env

Создайте файл `.env` в корне проекта:

```
SECRET_KEY=dev-secret-change-me
SQLALCHEMY_DATABASE_URI=sqlite:///instance/app.db
SQLALCHEMY_TRACK_MODIFICATIONS=False
UPLOAD_FOLDER=uploads
FLASK_ENV=development
```

Создайте папки (если не создались автоматически):
```bash
mkdir instance
mkdir uploads
```

### 3.4 Первый запуск

**Вариант A — напрямую:**
```bash
python app.py
```
Приложение стартует на `http://127.0.0.1:5000/`. Таблицы создадутся автоматически (в `create_app()` вызывается `db.create_all()`).

**Вариант B — через Flask CLI:**
```bash
# Windows
$env:FLASK_APP="app:create_app"
flask run

# Linux/macOS
export FLASK_APP=app:create_app
flask run
```

### 3.5 Создание пользователей

```bash
python create_user.py <логин> <пароль> <роль>
```
Примеры:
```bash
python create_user.py root root root
python create_user.py admin admin123 admin
python create_user.py user user123 user
```

**Права по ролям (кратко):**
- `user` — просмотр/заполнение форм;
- `admin` — добавление/редактирование/экспорт;
- `root` — все права, включая удаление.

---

## 4. Навигация и адреса модулей

- Домашняя: `/` (экран выбора модуля)
- Запчасти: `/parts/...` (каталог, добавить, импорт, экспорт)
- Обслуживание: `/maintenance/...` (оборудование, чек-листы, планы, WO)

Вверху страницы — переключатель модулей и глобальный поиск (Ctrl+K). Слева — сайдбар соответствующего модуля.

---

## 5. Модуль «Запчасти»

### 5.1 Каталог и поиск
`/parts/` — таблица запчастей. Встроенный поиск по SAP, Part Number, Name, Category и пр.  
Глобальный поиск в шапке перенаправляет на `/parts/?q=...`.

### 5.2 Добавление вручную
`/parts/add` — заполните карточку (минимум: **SAP Code**, **Part Number**, **Name**, **Category**).

### 5.3 Импорт/Экспорт Excel

- **Импорт** `/parts/import` — `.xlsx` с колонками наподобие:  
  `SAP Code, Part Number, Name, Category, Equipment Code, Location, Manufacturer, Analog Group, Photo`
- **Экспорт** `/parts/export` — выгрузка текущей выборки/всей базы.

### 5.4 Фото
Загрузка фото из карточки детали, файлы сохраняются в `uploads/`.

---

## 6. Модуль «Обслуживание» (ТО)

### 6.1 Сущности
- **Equipment** — оборудование.
- **Checklist Template** — шаблон чек-листа.
- **Maintenance Plan** — привязка шаблона к оборудованию и частота.
- **Work Order (WO)** — наряд, создаётся планировщиком из планов.

### 6.2 Оборудование
`/maintenance/equipment` → **+ Add**  
Пример: `EQ001` — Compressor, Category: Utilities, Location: Comp Room.

### 6.3 Шаблоны чек-листов
`/maintenance/checklists/templates` → **+ Add**

**Формат одной строки пункта:**
```
EN | RU | field_type | options
```
Поддерживаемые `field_type`:
- `checkbox` — галка (options пусто)
- `numeric` — число (десятичные через точку: `0.18`)
- `text` — произвольный текст
- `select` — варианты в `options` через запятую (без кавычек)

**Пример (ежедневный чек-лист для компрессора):**
```
Visual check for leaks at hoses and fittings | Осмотр на протечки шлангов и соединений | checkbox |
Oil level visible in sight glass (unit running) | Уровень масла виден в смотровом стекле (при работе) | select | OK,Add oil,Stop line
Condensate drain operation | Работа сливов конденсата | select | OK,Adjust timer,Check drain valve
Controller service indicators | Индикаторы обслуживания на контроллере | select | No alerts,Service due,Alarm/Trip
Package pre-filter condition | Предфильтр установки (засорение) | select | OK,Dirty,Cleaned
Air filter inlet restriction | Воздушный фильтр (разрежение на входе) | select | OK,Replace,Clean
Oil filter differential pressure (bar) | Перепад давления на масляном фильтре (бар) | numeric |
Unusual noise or vibration | Посторонний шум/вибрация | select | Normal,Monitor,Stop line
Comments | Комментарии | text |
```

### 6.4 Планы ТО
`/maintenance/plans` → **+ Add**  
Параметры: Equipment, Template, Frequency (`daily/weekly/monthly/...`), **Next due** (для первого запуска поставьте **сегодня**), `Grace days` (допустимая просрочка, обычно 0–2).

### 6.5 Планировщик → Work Orders
На странице планов нажмите **Run Scheduler** — создаст WO по всем планам, у которых наступил срок.

### 6.6 Заполнение Work Order
`/maintenance/workorders` → выбрать WO → **Fill** → заполнить поля согласно типам → **Submit**. Статус станет `done`.

### 6.7 Быстрая форма (QR/ссылка)
Создание одноразового WO и сразу форма заполнения:
```
/maintenance/form?eq=<EQUIPMENT_CODE>&tpl=<TEMPLATE_CODE>
```
Пример: `/maintenance/form?eq=EQ001&tpl=COMP-Daily`

---

## 7. Полезные утилиты

**Сидер тестовых данных (по желанию):**
```bash
# Windows
set FLASK_APP=app.py
flask shell -c "import seed_maintenance as s; s.run()"

# Linux/macOS
export FLASK_APP=app.py
flask shell -c "import seed_maintenance as s; s.run()"
```
Выведет `Seed OK: ...` и создаст пример оборудования/шаблона/плана.

**Просмотр маршрутов:**
```bash
# Windows
$env:FLASK_APP="app.py"
flask routes
# Linux/macOS
export FLASK_APP=app.py && flask routes
```

---

## 8. Типичные ошибки и решения

- **VS Code: `Import "flask" could not be resolved`** — выберите интерпретатор: `Ctrl+Shift+P` → *Python: Select Interpreter* → `.venv`.
- **`ModuleNotFoundError: No module named 'extensions'`** — команды запускать из **корня** проекта (где `app.py`).
- **`TemplateAssertionError: block 'sidebar' defined twice`** — в каком-то шаблоне дважды объявлен блок `sidebar`. В `base.html` он должен быть **один** (без include), include вставляются в дочерних шаблонах.
- **`BuildError: Could not build url for endpoint ...`** — в шаблоне указан несуществующий эндпоинт. Либо поправьте имя, либо используйте прямые пути (`/parts/import`, `/parts/export`).
- **Числовые поля чек-листа** — используйте **точку** как десятичный разделитель.
- **После логина 500 на /parts/** — не используйте `current_app` в шаблонах по умолчанию; подсветку активного пункта делайте через `request.path`.

---

## 9. Рекомендации по кодированию

Унифицируйте коды оборудования/запчастей по внутреннему стандарту (см. отдельный документ «Guidelines»). Это улучшит поиск и интеграцию с ERP.

---

## 10. Продакшен-запуск (кратко)

- Используйте WSGI-сервер (**gunicorn**/**waitress**). Пример:
  ```bash
  pip install gunicorn
  export FLASK_APP=app:create_app
  gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
  ```
- Перед фронтом — **nginx** с TLS.
- Перейдите с SQLite на PostgreSQL/MySQL (замените `SQLALCHEMY_DATABASE_URI`).
- Делайте бэкапы `instance/app.db` (или внешней БД) и `uploads/`.
- В проде выключите режим разработки (`FLASK_ENV`).

---

## 11. Планируемые расширения

- Телеграм-бот: выдача новых WO операторам, кнопки Start/Done, привязка пользователя по одноразовому коду, уведомления.
- Вложения (фото/видео) к WO.
- Привязка «критичных» запчастей к оборудованию и списание со склада при закрытии WO.

---

## 12. Чек-лист «от нуля до первого WO»

1. Создать venv → `pip install -r requirements.txt`  
2. Создать `.env`, папки `instance/` и `uploads/`  
3. `python app.py` — первый старт (создаст таблицы)  
4. `python create_user.py root root root` — создать пользователя  
5. Зайти на `http://127.0.0.1:5000/` → войти  
6. **Maintenance → Equipment** — добавить `EQ001 Compressor`  
7. **Checklists → +Add** — вставить строки чек-листа (формат `EN | RU | type | options`)  
8. **Plans → +Add** — выбрать `EQ001 + COMP-Daily`, частота `daily`, дата **сегодня**  
9. На странице **Plans** нажать **Run Scheduler**  
10. **Work Orders** → открыть WO → **Fill** → **Submit** (статус `done`)

Готово — система готова к ежедневной работе.
