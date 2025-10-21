# 📚 Spare Parts Inventory System

## 🌍 Описание
Web-приложение для учёта запчастей на производстве. Поддерживает просмотр, поиск, фильтрацию, редактирование и добавление запчастей, а также импорт/экспорт Excel-файлов. С разграничением прав по ролям.

## 🧑‍💼 Роли и права доступа
| Роль     | Просмотр | Добавление | Редактирование | Удаление | Экспорт в Excel | Фото |
|----------|----------|------------|----------------|----------|------------------|------|
| `user`   | ✅        | ❌         | ❌             | ❌       | ❌               | ✅    |
| `admin`  | ✅        | ✅         | ✅             | ❌       | ✅               | ✅    |
| `root`   | ✅        | ✅         | ✅             | ✅       | ✅               | ✅    |

## 📁 Структура проекта
```
spare_parts_inventory/
├── app.py              # Точка входа, создаёт app
├── config.py           # Загрузка настроек из .env
├── extensions.py       # Инициализация SQLAlchemy и LoginManager
├── models.py           # Модели User и Part
├── routes.py           # Маршруты Flask, обработчики view
├── utils.py            # Функции для Excel-экспорта, обработки фото
├── create_user.py      # Скрипт создания любого пользователя
├── .env                # Секреты, путь к базе и фолдеру загрузок
├── environment.yml     # Conda-файл с зависимостями
├── requirements.txt    # pip-зависимости (если не через conda)
├── templates/
│   ├── base.html       # Базовый шаблон (шапка, меню)
│   ├── index.html      # Главная страница (список запчастей)
│   ├── login.html      # Форма входа
│   ├── add_part.html   # Форма добавления запчасти
│   ├── edit_part.html  # Форма редактирования
│   └── view_part.html  # Карточка запчасти
```

## 🚀 Запуск
```bash
conda activate spare_parts_inventory
python app.py
```

🌐 Перейти в браузере: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 👤 Создание пользователей

Один универсальный скрипт для root, admin и user:
```bash
python create_user.py <логин> <пароль> <роль>
```

### Примеры:
```bash
python create_user.py root root123 root
python create_user.py admin admin123 admin
python create_user.py user user123 user
```
> ⚠️ Если логин уже существует — будет выведено предупреждение и пользователь не будет создан.

## 🧪 Тестирование
```bash
pytest test_routes.py
```

## ✍️ Автор
Malder82Fox

---
📫 По всем вопросам: au252780@gmail.com