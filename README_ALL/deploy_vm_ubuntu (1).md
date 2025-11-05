# Разворачивание нашей CRM/ERP на виртуальной машине (Ubuntu Server) — полный пошаговый гайд

> Этот документ — «как мы сделали это у себя» + лучшие практики. Скопируй в репозиторий как `docs/deploy_vm_ubuntu.md`.

---

## 0) Что получится в итоге

- Виртуальная машина (VM) с **Ubuntu Server** под **VirtualBox** на твоём ноутбуке с Windows.  
- Приложение Flask из GitHub развёрнуто в **venv** и запускается одной командой `./run.sh`.  
- Доступ к приложению из локальной сети по адресу `http://<IP_виртуалки>:8000` (или по имени `http://erpserver.local:8000`).  
- Репозиторий привязан по **SSH**, обновления кода — через `git pull` из ветки **deploy**.  
- (Опционально) Автозапуск бэкенда как сервиса через **gunicorn + systemd**.

---

## 1) Подготовка VirtualBox и создание ВМ

1. Установи **VirtualBox** (на Windows).  
2. Создай новую VM:  
   - **Name**: `CRM_SERVER` (произвольно).  
   - **Type / Version**: *Linux / Ubuntu (64‑bit)*.  
   - **CPU/RAM**: минимум 2 vCPU и 4–8 GB RAM.  
   - **Disk**: 20–40 GB VDI, динамический.  
   - **Network**: лучше *Bridged Adapter* (ВМ получит IP в твоей сети). Альтернатива — NAT + Port Forwarding.  
3. Подключи ISO **Ubuntu Server 24.04 LTS** (или близкую), установи систему (стандартная установка).  
   - Пользователь, например: `admin_erp`.  
   - OpenSSH Server можно поставить сразу (не обязательно — мы работаем через консоль VirtualBox).

> **Зачем Bridged?** Чтобы ВМ имела «нормальный» IP в твоей сети и приложение было доступно всем устройствам по этому IP/имени.

---

## 2) Первичная настройка Ubuntu

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git ca-certificates curl python3-venv tmux
sudo update-ca-certificates
```

**Пояснения:**  
- `git` — забираем код.  
- `python3-venv` — создаём изолированное окружение.  
- `tmux` — чтоб не терять процесс при закрытии терминала.  
- Обновления сразу подтягиваем, чтобы избежать багов старых пакетов.

---

## 3) Настройка сети и IP

- Узнать адрес ВМ:  
  ```bash
  ip a
  ```
- Если нужен **фиксированный IP**:  
  - **Вариант А (рекомендуется):** на роутере настроить DHCP‑резервацию по MAC‑адресу ВМ.  
  - **Вариант Б:** статический IP через netplan (см. ниже в разделе «Полезное: закрепляем IP (netplan)»).

---

## 4) Общая папка Windows ↔ Ubuntu (VirtualBox Shared Folder)

**Зачем?** Чтобы быстро перекидывать файлы (SSH‑ключ, скрипты) без копипаста.

1. В окне запущенной ВМ: `Devices → Shared Folders → Shared Folders Settings → +`  
   - **Folder Path**: например, `F:\Shared_VM` (создай папку на Windows).  
   - **Folder Name**: `Shared_VM`.  
   - Галочки: **Auto‑mount** и **Make Permanent**.
2. Если предложит установить *Guest Additions*, сделай так:
   ```bash
   sudo mkdir -p /mnt/cdrom
   sudo mount /dev/cdrom /mnt/cdrom
   sudo /mnt/cdrom/VBoxLinuxAdditions.run
   sudo reboot
   ```
3. Проверка автомонтирования (или вручную смонтируй):
   ```bash
   sudo mkdir -p /media/sf_Shared_VM
   sudo mount -t vboxsf Shared_VM /media/sf_Shared_VM
   ```
4. Чтобы монтировалось всегда:
   ```bash
   echo "Shared_VM  /media/sf_Shared_VM  vboxsf  defaults  0  0" | sudo tee -a /etc/fstab
   sudo usermod -aG vboxsf $USER
   sudo reboot
   ```

> **Важно:** В общей папке часто владельцем является `root:vboxsf`. Копируй файлы **из неё** в свой каталог и меняй владельца при необходимости: `cp /media/sf_Shared_VM/file ~ && chmod u+rw ~/<file>`.

---

## 5) Git и SSH‑доступ к GitHub

### 5.1. Мини‑конфиг git

```bash
git config --global user.name "Andrey Ushakov"
git config --global user.email "au252780@gmail.com"
```

### 5.2. Генерация SSH‑ключа и добавление на GitHub

```bash
ssh-keygen -t ed25519 -C "au252780@gmail.com"
cat ~/.ssh/id_ed25519.pub
```
- Скопируй **всю строку** из `.pub` (начинается с `ssh-ed25519`… и заканчивается твоим email).  
- На GitHub: **Settings → SSH and GPG keys → New SSH key →** вставь ключ.  
- Проверка связи:
  ```bash
  ssh -T git@github.com
  ```
  При первом подключении ответь `yes` — GitHub появится в `~/.ssh/known_hosts`.

---

## 6) Клонирование репозитория (ветка deploy)

```bash
mkdir -p ~/projects && cd ~/projects
git clone --depth 1 --branch deploy --single-branch git@github.com:Malder82Fox/spare_parts_inventory.git
cd spare_parts_inventory
```

**Комментарии:**  
- Клонируем **только** ветку deploy, чтобы не тащить историю/ветки.  
- Рабочая папка проекта: `~/projects/spare_parts_inventory`.

---

## 7) Окружение и зависимости

### 7.1. Создаём venv и ставим зависимости

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

> Если `requirements.txt` был собран на Windows и внутри есть строки вида `package @ file:///C:/...`, их нужно вычистить (Linux не понимает такие локальные пути). Самый простой фильтр:
> ```bash
> awk -F' @ ' '{print $1}' requirements.txt | awk -F';' '{print $1}' > req.tmp && mv req.tmp requirements.txt
> pip install -r requirements.txt
> ```

### 7.2. Проверка

```bash
pip check        # нет ли битых зависимостей
python -V        # Python 3.12.x
flask --version  # проверим, что Flask доступен
```

---

## 8) Ручной запуск для проверки

### Вариант A: через flask

```bash
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=8000
```
Теперь приложение доступно по `http://<IP_виртуалки>:8000` **со всех устройств в локальной сети**.

### Вариант B: через python

```bash
python app.py
```
(Этот вариант зависит от того, как устроен `app.py`. Для доступа из сети убедись, что внутри используется `host='0.0.0.0'` и нужный порт.)

---

## 9) Скрипт удобного запуска `run.sh`

Положи файл `run.sh` в корень проекта и сделай исполняемым: `chmod +x run.sh`.

```bash
#!/usr/bin/env bash
set -e

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
FLASK_APP_PATH="${FLASK_APP_PATH:-app.py}"

# всегда стартуем из каталога, где лежит run.sh
cd "$(dirname "$0")"

# 1) Активируем виртуальное окружение
if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "ERROR: venv не найден. Создай его: python3 -m venv venv && source venv/bin/activate"
  exit 1
fi

# 2) При наличии requirements — допоставим пакеты
if [ -f "requirements.txt" ]; then
  python -m pip install --upgrade pip wheel setuptools >/dev/null
  pip install -r requirements.txt
fi

# 3) Запускаем Flask
export FLASK_APP="$FLASK_APP_PATH"
echo "Starting Flask on ${HOST}:${PORT} ..."
exec flask run --host="${HOST}" --port="${PORT}"
```

**Запуск:**  
```bash
./run.sh
```

**Полезно знать:** можно задать порт/хост переменными окружения без правки скрипта:  
`HOST=0.0.0.0 PORT=8010 ./run.sh`

---

## 10) Обновление проекта с GitHub

```bash
cd ~/projects/spare_parts_inventory
git fetch origin
git switch deploy
git pull --ff-only origin deploy

source venv/bin/activate
pip install -r requirements.txt --upgrade

./run.sh
```

**Почему `--ff-only`?** Чтобы защититься от случайных merge‑коммитов и держать историю линейной.

---

## 11) Имя вместо IP (mDNS/Bonjour)

Чтобы открывать `http://erpserver.local:8000`:

```bash
# задаём имя хоста
sudo hostnamectl set-hostname erpserver
echo "127.0.1.1 erpserver" | sudo tee -a /etc/hosts

# включаем Avahi (служба mDNS)
sudo apt install -y avahi-daemon
sudo systemctl enable --now avahi-daemon

# (если включён UFW — откроем mDNS)
sudo ufw allow 5353/udp
```

> На Windows/Android может потребоваться установить Bonjour/ZeroConf‑клиент, но чаще всё работает из коробки в одной сети.

---

## 12) Чтобы не «висло» при блокировке экрана

- На Windows отключи сон/гибернацию для профиля, где запущен VirtualBox.  
- Запускай приложение внутри `tmux`, чтобы сессия не падала при закрытии окна:
  ```bash
  tmux new -s crm
  ./run.sh
  # Отсоединиться, не завершая процесс: Ctrl+b, затем d
  # Вернуться: tmux attach -t crm
  ```

---

## 13) (Опционально) Автозапуск как сервиса: gunicorn + systemd

```bash
# установить gunicorn в наше venv
source venv/bin/activate
pip install gunicorn

# сервис systemd
sudo bash -c 'cat > /etc/systemd/system/spi.service <<EOF
[Unit]
Description=Spare Parts Inventory (Flask via gunicorn)
After=network.target

[Service]
User=admin_erp
WorkingDirectory=/home/admin_erp/projects/spare_parts_inventory
Environment=PATH=/home/admin_erp/projects/spare_parts_inventory/venv/bin
ExecStart=/home/admin_erp/projects/spare_parts_inventory/venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable --now spi
sudo systemctl status spi --no-pager
```

Теперь приложение стартует само при загрузке ВМ и живёт в фоне. Логи: `journalctl -u spi -f`.

---

## 14) Полезное: закрепляем IP (netplan)

```bash
sudo nano /etc/netplan/01-netcfg.yaml
```
Пример содержимого:
```yaml
network:
  version: 2
  ethernets:
    enp0s3:
      dhcp4: false
      addresses: [192.168.1.38/24]
      routes:
        - to: 0.0.0.0/0
          via: 192.168.1.1
      nameservers:
        addresses: [192.168.1.1, 8.8.8.8]
```
Применить конфиг:
```bash
sudo netplan apply
```

---

## 15) Мини‑чеклист (перед сдачей/демо)

- [ ] ВМ в режиме **Bridged** и видна в сети.  
- [ ] У ВМ постоянный IP **или** доступ по имени `erpserver.local`.  
- [ ] SSH‑ключ добавлен на GitHub, `ssh -T git@github.com` показывает «success».  
- [ ] `venv` активируется, `pip check` без ошибок.  
- [ ] `./run.sh` поднимает сервер и он доступен с телефона/ноутбука по сети.  
- [ ] Сон/гибернация на Windows отключены (или используется `tmux`/`systemd`).  
- [ ] (Опционально) `systemd`‑сервис `spi` активен, автозапуск работает.

---

### FAQ (самые частые вопросы)

**Q: После `pip install -r requirements.txt` — ошибка `No such file or directory: 'C:\\...'`**  
A: Это Windows‑пути внутри `requirements.txt`. Очисти файл фильтром `awk`, как в п.7.1, и повтори установку.

**Q: Flask запустился, но доступен только с самой ВМ.**  
A: Используй `--host=0.0.0.0` (или скрипт `run.sh`). Проверь, что в сети нет файрвола, и что ты открываешь `http://<IP_виртуалки>:8000`.

**Q: IP меняется после перезагрузки.**  
A: Сделай DHCP‑резервацию на роутере или статический IP через netplan (раздел 14).

**Q: Как открыть порт 8000 в UFW?**  
```bash
sudo ufw allow 8000/tcp
sudo ufw enable
sudo ufw status
```

**Q: Что если захочу PostgreSQL/SQLite и миграции?**  
A: Добавь БД в зависимости, конфиг подключений в `config.py`, создай сервис и миграции (Alembic/Flask‑Migrate) — это уже следующий шаг.

---

Удачной сборки! Если что‑то упустили — правь этот документ прямо в репозитории и присылай PR в `deploy`.
