# Server Monitor

Комплексная система мониторинга сервера с Telegram ботами для администрирования и уведомлений.

## Возможности

### 📱 Telegram Admin Bot
- **Управление системой** через Telegram
- **Мониторинг ресурсов** (CPU, RAM, диск, сеть)
- **Управление fail2ban** (просмотр и разбан IP)
- **Speedtest** и сетевая статистика
- **Обновление системы**
- **Управление Docker контейнерами**
- **Дополнительные команды:**
  - 🌐 Сеть: открытые порты, активные соединения, SSH сессии, traceroute
  - 🛡️ Безопасность: история входов, sudo логи
  - 🔍 Диагностика: топ процессов по CPU/RAM, большие файлы, I/O wait, тест DNS
  - 🐳 Docker: статистика контейнеров, размер образов
  - ⚙️ Процессы: zombie процессы, количество потоков
  - 📦 Система: uptime, упавшие сервисы, история apt, размер кэша

### 🔔 Telegram Monitor Bot
- Автоматический мониторинг ресурсов (CPU, RAM, Disk, Swap)
- Уведомления о превышении порогов
- Мониторинг SSH попыток входа
- Уведомления fail2ban о блокировках
- Мониторинг Docker контейнеров

### 🛡️ Fail2ban
- Многоуровневая защита SSH
- Детекция медленных brute-force атак
- Автоматическая блокировка по подсетям
- Telegram уведомления о блокировках
- Ежедневные отчёты и алерты аномалий

### 📊 Мониторинг (Monit)
- Проверка сервисов (SSH, Docker, Fail2ban, Cron и др.)
- Мониторинг ресурсов (CPU load, Memory, Swap, Disk)
- Telegram уведомления о проблемах
- Автоматический перезапуск упавших сервисов

### 🌍 GeoIP
- Блокировка SSH по странам
- Whitelist для своих IP и DDNS доменов
- Автоматическое обновление баз GeoIP

## Требования
- **Ubuntu 24.04 LTS** (или новее)
- **systemd**
- **Root доступ**
- **Telegram Bot Token** (получить у [@BotFather](https://t.me/botfather)) и чат ID

## Установка

### Новый сервер (полная установка)

```bash
# 1. Клонируем репозиторий
apt install -y git
cd /opt
git clone https://github.com/myshdd/server-monitor.git
cd server-monitor
chmod +x install/*.sh

# 2. Первичная настройка сервера (локаль, timezone, пользователи)
./install/setup-server-init.sh
# Потребуется перезагрузка

# 3. После перезагрузки - настройка секретов
cp config/examples/secrets.json.example config/secrets.json
nano config/secrets.json

# 4. Полная установка
./install/setup.sh

# 5. Запуск сервисов
systemctl enable --now telegram-admin-bot telegram-monitor
systemctl restart fail2ban monit
```

### Сервер уже настроен

```bash
cd /opt
git clone https://github.com/myshdd/server-monitor.git
cd server-monitor
cp config/examples/secrets.json.example config/secrets.json
nano config/secrets.json
./install/setup.sh
systemctl enable --now telegram-admin-bot telegram-monitor
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
│       ├── monit/
│       └── conf-enabled/         # Конфиги проверок Monit
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

### Вызовы скриптов

```
Из admin_bot.py
Скрипт	                  Описание
clear-swap.sh	            Очистка swap памяти
collect-network-stats.sh	Сбор сетевой статистики
f2b-status.sh	            Статус fail2ban
speedtest-iperf.sh	      Тест скорости через iperf3
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
  "monitoring": {
    "check_interval": 180,
    "thresholds": {
      "cpu": 80,
      "ram": 90,
      "disk": 95,
      "swap": 80
    }
  },
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

Telegram Admin Bot - Команды

Главное меню:

    📊 Статистика
    🔒 Забаненные IP
    📊 Графики нагрузки
    🐳 Docker контейнеры
    📋 Системная информация
    📦 Обновление системы
    📁 Просмотр логов
    🛡️ Fail2ban Dashboard
    📡 Тест скорости
    🔧 Дополнительные команды

**Дополнительные команды:**

🌐 **Сеть:**
- Открытые порты
- Активные соединения
- SSH сессии
- Traceroute

🛡️ **Безопасность:**
- Последние входы
- Sudo логи

🔍 **Диагностика:**
- Top CPU процессы
- Top RAM процессы
- Zombie процессы
- Thread count
- Большие файлы
- I/O wait
- Тест DNS

🐳 **Docker:**
- Docker stats
- Images size

📦 **Система:**
- Uptime
- Systemd failed
- Apt history
- Apt cache size

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
- ✅ Monit контролирует работу сервисов

## Оптимизация производительности

### ipset для fail2ban

Fail2ban использует **ipset** для хранения забаненных IP вместо отдельных правил iptables. Это даёт:

- ✅ **O(1) lookup** вместо O(n) — проверка IP в хэш-таблице
- ✅ **Поддержка тысяч IP** без нагрузки на CPU
- ✅ **Снижение нагрузки в 100+ раз** при большом количестве атак

**Было (без ipset):**

iptables: 174 отдельных правила для каждого IP
CPU: высокая нагрузка при каждом пакете
Load average: 3-15+ при атаках

text


**Стало (с ipset):**

iptables: 3 правила (по одному на jail)
ipset: все IP в хэш-таблицах
Load average: ~1.5 даже при 1000+ забаненных IP

text


Проверка состояния ipset:
```bash
# Количество IP в ipset'ах
ipset list f2b-SSH-slow | grep "Number of entries"
ipset list f2b-SSH-very-slow | grep "Number of entries"
ipset list f2b-SSH-ultra-slow | grep "Number of entries"

# Правила iptables с ipset
iptables -L INPUT -n -v | grep "match-set"

Анализатор медленных атак

Скрипт f2b-slow-attack-detector.py запускается каждые 6 часов для снижения нагрузки. Он анализирует паттерны распределённых SSH-атак:

    Один логин с множества IP (распределённая атака)
    Один IP пробует множество логинов (credential stuffing)
    Подозрительные подсети (/24)

Настройка в /etc/cron.d/f2b-analysis:

Bash

# Запуск в 00:30, 06:30, 12:30, 18:30
30 */6 * * * root /usr/bin/python3 /usr/local/bin/f2b-slow-attack-detector.py --auto-ban

Ручной запуск анализа:

Bash

/usr/bin/python3 /usr/local/bin/f2b-slow-attack-detector.py
# С автоматическим баном:
/usr/bin/python3 /usr/local/bin/f2b-slow-attack-detector.py --auto-ban


#

## Устранение проблем

## Боты не запускаются

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

### Monit не отправляет уведомления
```bash
# Тест скрипта
/usr/local/bin/monit-alert.sh swap_high

# Проверьте логи
journalctl -u monit -f
```

## Лицензия

MIT License

## Автор

Создано для мониторинга и администрирования серверов через Telegram.
