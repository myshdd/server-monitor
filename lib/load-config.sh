#!/bin/bash
# /opt/server-monitor/lib/load-config.sh
# Библиотека для загрузки конфигурации в bash-скриптах

# Пути к конфигурационным файлам
CONFIG_DIR="/opt/server-monitor/config"
SETTINGS_FILE="$CONFIG_DIR/settings.json"
SECRETS_FILE="$CONFIG_DIR/secrets.json"
PATHS_FILE="$CONFIG_DIR/paths.json"

# Проверка наличия jq
if ! command -v jq &> /dev/null; then
    echo "❌ Ошибка: jq не установлен. Установите: apt install jq" >&2
    exit 1
fi

# Проверка существования конфигурационных файлов
check_config_files() {
    local missing=0
    
    if [ ! -f "$SETTINGS_FILE" ]; then
        echo "❌ Не найден файл: $SETTINGS_FILE" >&2
        missing=1
    fi
    
    if [ ! -f "$SECRETS_FILE" ]; then
        echo "❌ Не найден файл: $SECRETS_FILE" >&2
        missing=1
    fi
    
    if [ ! -f "$PATHS_FILE" ]; then
        echo "❌ Не найден файл: $PATHS_FILE" >&2
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        echo "💡 Запустите: init-server-monitor-config.sh" >&2
        return 1
    fi
    
    return 0
}

# ============================================
# ФУНКЦИИ ДЛЯ ЧТЕНИЯ НАСТРОЕК
# ============================================

# Получить значение из settings.json
# Использование: get_setting "monitoring.check_interval"
get_setting() {
    local key="$1"
    local default="${2:-}"
    
    if [ ! -f "$SETTINGS_FILE" ]; then
        echo "$default"
        return 1
    fi
    
    local value=$(jq -r ".$key // empty" "$SETTINGS_FILE" 2>/dev/null)
    
    if [ -z "$value" ] || [ "$value" = "null" ]; then
        echo "$default"
    else
        echo "$value"
    fi
}

# Получить секрет из secrets.json
# Использование: get_secret "telegram.admin_bot_token"
get_secret() {
    local key="$1"
    
    if [ ! -f "$SECRETS_FILE" ]; then
        echo "" >&2
        return 1
    fi
    
    local value=$(jq -r ".$key // empty" "$SECRETS_FILE" 2>/dev/null)
    
    if [ -z "$value" ] || [ "$value" = "null" ]; then
        echo "" >&2
        return 1
    else
        echo "$value"
    fi
}

# Получить путь из paths.json
# Использование: get_path "logs.fail2ban"
get_path() {
    local key="$1"
    local default="${2:-}"
    
    if [ ! -f "$PATHS_FILE" ]; then
        echo "$default"
        return 1
    fi
    
    local value=$(jq -r ".$key // empty" "$PATHS_FILE" 2>/dev/null)
    
    if [ -z "$value" ] || [ "$value" = "null" ]; then
        echo "$default"
    else
        echo "$value"
    fi
}

# ============================================
# ПРЕДЗАГРУЖЕННЫЕ ОБЩИЕ ПЕРЕМЕННЫЕ
# ============================================

# Автоматическая загрузка часто используемых переменных
load_common_vars() {
    # Telegram
    export TELEGRAM_ADMIN_TOKEN=$(get_secret "telegram.admin_bot_token")
    export TELEGRAM_MONITOR_TOKEN=$(get_secret "telegram.monitor_bot_token")
    export TELEGRAM_CHAT_ID=$(get_secret "telegram.chat_id")
    
    # Мониторинг
    export CHECK_INTERVAL=$(get_setting "monitoring.check_interval" "180")
    export CPU_THRESHOLD=$(get_setting "monitoring.thresholds.cpu" "80")
    export RAM_THRESHOLD=$(get_setting "monitoring.thresholds.ram" "90")
    export DISK_THRESHOLD=$(get_setting "monitoring.thresholds.disk" "95")
    
    # Fail2ban
    export F2B_SUBNET_THRESHOLD=$(get_setting "fail2ban.subnet_threshold" "5")
    export F2B_BANTIME=$(get_setting "fail2ban.subnet_bantime" "86400")
    
    # Пути к логам
    export LOG_DIR=$(get_path "logs.base_dir" "/var/log/server-monitor")
    export F2B_LOG=$(get_path "logs.fail2ban" "/var/log/fail2ban.log")
    export F2B_SUBNET_LOG=$(get_path "logs.f2b_subnet" "/var/log/f2b-subnet-aggregator.log")
    
    # Пути к данным
    export GEOIP_DIR=$(get_path "data.geoip_dir" "/opt/server-monitor/data/geoip")
    export GEOIP_RU_ZONE=$(get_path "data.geoip_ru_zone" "/opt/server-monitor/data/geoip/ru.zone")
    export NETWORK_STATS_DIR=$(get_path "data.network_stats_dir" "/opt/server-monitor/data")
}

# ============================================
# ФУНКЦИИ ЛОГИРОВАНИЯ
# ============================================

# Логирование в файл и systemd journal
# Использование: log_info "Сообщение"
log_info() {
    local message="$1"
    local script_name=$(basename "$0")
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $message"
    logger -t "$script_name" -p user.info "$message"
}

log_error() {
    local message="$1"
    local script_name=$(basename "$0")
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $message" >&2
    logger -t "$script_name" -p user.error "$message"
}

log_warning() {
    local message="$1"
    local script_name=$(basename "$0")
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $message"
    logger -t "$script_name" -p user.warning "$message"
}

# ============================================
# ФУНКЦИЯ ОТПРАВКИ В TELEGRAM (для bash-скриптов)
# ============================================

send_telegram() {
    local message="$1"
    local token="${2:-$TELEGRAM_MONITOR_TOKEN}"
    local chat_id="${3:-$TELEGRAM_CHAT_ID}"
    
    if [ -z "$token" ] || [ -z "$chat_id" ]; then
        log_error "Telegram token или chat_id не заданы"
        return 1
    fi
    
    local response=$(curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        -d "chat_id=${chat_id}" \
        -d "text=${message}" \
        -d "parse_mode=Markdown")
    
    if echo "$response" | jq -e '.ok' > /dev/null 2>&1; then
        return 0
    else
        log_error "Ошибка отправки в Telegram: $(echo $response | jq -r '.description // "Unknown error"')"
        return 1
    fi
}

# ============================================
# ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ
# ============================================

# Проверяем конфиги при подключении библиотеки
if ! check_config_files; then
    # Не выходим, чтобы не ломать скрипты, которые могут работать без конфига
    # но выводим предупреждение
    log_warning "Конфигурационные файлы не найдены или неполные"
fi
