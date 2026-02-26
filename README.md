# Server Monitor

Комплексная система мониторинга сервера с Telegram ботами для администрирования и уведомлений.

## Возможности

### 📱 Telegram Admin Bot
- Управление системой через Telegram
- Мониторинг ресурсов (CPU, RAM, диск, сеть)
- Управление fail2ban
- Speedtest и сетевая статистика
- Обновление системы
- Управление Docker контейнерами

### 🔔 Telegram Monitor Bot
- Автоматический мониторинг ресурсов
- Уведомления о превышении порогов
- Мониторинг SSH попыток входа
- Уведомления fail2ban о блокировках

### 🛡️ Fail2ban
- Многоуровневая защита SSH
- Детекция медленных brute-force атак
- Автоматическая блокировка по подсетям
- Telegram уведомления о блокировках

### 📊 Мониторинг
- Сбор сетевой статистики
- Мониторинг GeoIP
- Speedtest с несколькими серверами
- Статистика использования ресурсов

### Требования
- Ubuntu 24.04 LTS (или новее)
- Root доступ
- Telegram Bot Token (получить у [@BotFather](https://t.me/botfather))

### Новый сервер (полная установка)

```bash
# 1. Клонируем репозиторий
cd /opt
git clone https://github.com/myshdd/server-monitor.git
cd server-monitor

# 2. Первичная настройка (локаль, timezone, пользователи)
./install/setup-server-init.sh
# Потребуется перезагрузка

# 3. После reboot - настройка секретов
cp config/examples/secrets.json.example config/secrets.json
nano config/secrets.json

# 4. Основная установка
./install/setup.sh
```

### Сервер уже настроен

```bash
cd /opt
git clone https://github.com/myshdd/server-monitor.git
cd server-monitor
cp config/examples/secrets.json.example config/secrets.json
nano config/secrets.json
./install/setup.sh
```

## Структура проекта

```
/opt/server-monitor/
├── bots/                          # Telegram боты
│   ├── admin_bot.py              # Админ бот
│   ├── monitor.py                # Монитор бот
│   ├── admin_bot_venv/           # Виртуальное окружение admin bot
│   ├── monitor_venv/             # Виртуальное окружение monitor
│   ├── admin_bot_requirements.txt
│   └── monitor_requirements.txt
├── scripts/                       # Bash скрипты
│   ├── fail2ban/                 # Скрипты fail2ban
│   ├── geoip/                    # Скрипты GeoIP
│   ├── network/                  # Сетевые скрипты
│   └── system/                   # Системные скрипты
├── config/                        # Конфигурация
│   ├── secrets.json              # Секретные данные (не в git)
│   ├── settings.json             # Настройки
│   ├── paths.json                # Пути к файлам
│   ├── examples/                 # Примеры конфигов
│   └── system/                   # Конфиги системных пакетов
│       ├── fail2ban/
│       ├── iperf3/
│       └── monit/
├── lib/                           # Библиотеки
│   ├── config.py                 # Python библиотека конфигурации
│   └── load-config.sh            # Bash библиотека конфигурации
├── data/                          # Рабочие данные
│   ├── stats.json                # Сетевая статистика
│   └── geoip/                    # GeoIP базы
└── install/                       # Установочные скрипты
    ├── setup-server-init.sh      # Первичная настройка сервера
    ├── setup.sh                  # Полная установка
    ├── install-packages.sh       # Установка пакетов
    ├── install-configs.sh        # Установка конфигов
    └── install.sh                # Установка Server Monitor
```

## Конфигурация

### secrets.json

```json
{
  "telegram": {
    "admin_bot_token": "YOUR_BOT_TOKEN",
    "monitor_bot_token": "YOUR_BOT_TOKEN",
    "chat_id": YOUR_CHAT_ID
  }
}
```

### settings.json

Содержит пороги мониторинга, интервалы проверок и другие настройки.
Пример настройки GeoIP whitelist:

```json
{
  "geoip": {
    "whitelist_ips": ["127.0.0.0/8", "YOUR_IP"],
    "whitelist_domains": ["your.ddns.net"]
  }
}
```

### paths.json

Определяет пути к данным, логам и исполняемым файлам.

## Использование

### Управление сервисами

```bash
# Статус ботов
systemctl status telegram-admin-bot
systemctl status telegram-monitor

# Перезапуск
systemctl restart telegram-admin-bot
systemctl restart telegram-monitor

# Логи
journalctl -u telegram-admin-bot -f
journalctl -u telegram-monitor -f
```

### Telegram команды

Основные команды:
- `/start` - запуск бота


## Обновление

### Обновление на текущем сервере

```bash
cd /opt/server-monitor
git pull
systemctl restart telegram-admin-bot telegram-monitor
```

### Миграция на новый сервер

1. На старом сервере сделайте backup конфигурации:

```bash
cp /opt/server-monitor/config/secrets.json ~/secrets.json.backup
```

2. На новом сервере установите систему:

```bash
cd /opt
git clone https://github.com/myshdd/server-monitor.git
cd server-monitor
cp ~/secrets.json.backup config/secrets.json
./install/setup.sh
```

## Разработка

### Тестирование конфигурации

```bash
# Проверка Python конфига
/usr/local/bin/test-python-config.py

# Проверка bash конфига
/usr/local/bin/test-config.sh

# Валидация всех конфигов
/usr/local/bin/validate-config.sh
```

### Добавление нового скрипта

1. Создайте скрипт в соответствующей директории `scripts/`
2. Используйте библиотеку конфигурации:

```bash
source /usr/local/lib/server-monitor/load-config.sh
TOKEN=$(get_secret "telegram.admin_bot_token")
```

3. Добавьте скрипт в git
4. Установщик автоматически создаст симлинк в `/usr/local/bin/`

## Безопасность

- ✅ Секретные данные хранятся в `config/secrets.json` (chmod 600)
- ✅ Файл `secrets.json` добавлен в `.gitignore`
- ✅ Конфигурационные файлы вынесены из исходного кода
- ✅ Fail2ban блокирует SSH атаки на нескольких уровнях
- ✅ Telegram боты работают только с авторизованными пользователями
- ✅ GeoIP блокировка SSH (только РФ + whitelist)
- ✅ Whitelist для своих IP и DDNS доменов

## Устранение проблем

### Боты не запускаются

```bash
# Проверьте логи
journalctl -u telegram-admin-bot -n 50
journalctl -u telegram-monitor -n 50

# Проверьте конфигурацию
/usr/local/bin/test-python-config.py
```

### Скрипты не работают

```bash
# Проверьте симлинки
ls -la /usr/local/bin/*.sh

# Проверьте права
chmod +x /opt/server-monitor/scripts/*/*.sh
```

### Fail2ban не отправляет уведомления

```bash
# Проверьте скрипт
/etc/fail2ban/scripts/fail2ban-telegram.sh ban TEST 1.2.3.4

# Проверьте логи fail2ban
tail -f /var/log/fail2ban.log
```

## Лицензия

MIT License

## Автор

Создано для мониторинга и администрирования серверов через Telegram.
