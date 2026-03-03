#!/bin/bash
# /opt/server-monitor/scripts/system/monit-alert.sh
# Универсальный скрипт уведомлений Monit с вычислением значений

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

# Загружаем переменные
load_common_vars

# Проверяем наличие необходимых переменных
if [ -z "$TELEGRAM_MONITOR_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    log_error "Telegram токен или chat_id не настроены"
    exit 1
fi

# Директория для файлов состояний
STATE_DIR="/tmp/monit-state"
mkdir -p "$STATE_DIR"

# Файл для rate limiting
ALERT_TYPE="$1"
LAST_NOTIFY_FILE="/tmp/monit-alert-$(echo "$ALERT_TYPE" | md5sum | cut -c1-8)"
RATE_LIMIT_SECONDS=300

# ============================================
# ПРОВЕРКА АРГУМЕНТОВ
# ============================================

if [ -z "$ALERT_TYPE" ]; then
    log_error "Не указан тип алерта"
    echo "Использование: $0 <тип_алерта>"
    exit 1
fi

# ============================================
# ФУНКЦИИ
# ============================================

get_mem_usage() {
    free -m | awk 'NR==2 {if($2>0) printf "%.1f", $3*100/$2; else print "0"}'
}

get_swap_usage() {
    free -m | awk 'NR==3 {if($2>0) printf "%.1f", $3*100/$2; else print "0"}'
}

# Проверка состояния (был ли алерт ранее)
check_state() {
    local state_name="$1"
    [ -f "$STATE_DIR/$state_name" ]
}

# Установка состояния
set_state() {
    local state_name="$1"
    touch "$STATE_DIR/$state_name"
}

# Сброс состояния
clear_state() {
    local state_name="$1"
    rm -f "$STATE_DIR/$state_name"
}

# Извлечение имени сервиса из сообщения (убираем эмодзи и статус)
get_service_name() {
    local msg="$1"
    # Убираем эмодзи и слова статуса, оставляем только название
    echo "$msg" | sed 's/[⚠️✅🚨]//g' | sed 's/упал//g; s/восстановлен//g; s/не работает//g; s/работает//g; s/остановлен//g' | tr -s ' ' | xargs | md5sum | cut -c1-16
}

# ============================================
# ВЫЧИСЛЕНИЕ ЗНАЧЕНИЙ И ЛОГИКА СОСТОЯНИЙ
# ============================================

case "$ALERT_TYPE" in
    # CPU Load - HIGH
    "load1_high")
        VALUE=$(cat /proc/loadavg | awk '{print $1}')
        MESSAGE="⚠️ Высокая нагрузка CPU (1мин): ${VALUE}"
        set_state "load1"
        ;;
    "load5_high")
        VALUE=$(cat /proc/loadavg | awk '{print $2}')
        MESSAGE="⚠️ Высокая нагрузка CPU (5мин): ${VALUE}"
        set_state "load5"
        ;;
    "load15_high")
        VALUE=$(cat /proc/loadavg | awk '{print $3}')
        MESSAGE="⚠️ Высокая нагрузка CPU (15мин): ${VALUE}"
        set_state "load15"
        ;;
    
    # CPU Load - OK (только если был high)
    "load1_ok")
        if ! check_state "load1"; then
            exit 0
        fi
        VALUE=$(cat /proc/loadavg | awk '{print $1}')
        MESSAGE="✅ Нагрузка CPU (1мин) в норме: ${VALUE}"
        clear_state "load1"
        ;;
    "load5_ok")
        if ! check_state "load5"; then
            exit 0
        fi
        VALUE=$(cat /proc/loadavg | awk '{print $2}')
        MESSAGE="✅ Нагрузка CPU (5мин) в норме: ${VALUE}"
        clear_state "load5"
        ;;
    
    # Memory - HIGH
    "memory_high")
        VALUE=$(get_mem_usage)
        MESSAGE="⚠️ Заканчивается память: использовано ${VALUE}%"
        set_state "memory"
        ;;
    
    # Memory - OK (только если был high)
    "memory_ok")
        if ! check_state "memory"; then
            exit 0
        fi
        VALUE=$(get_mem_usage)
        MESSAGE="✅ Память в норме: использовано ${VALUE}%"
        clear_state "memory"
        ;;
    
    # Swap - HIGH
    "swap_high")
        VALUE=$(get_swap_usage)
        MESSAGE="⚠️ Swap заполнен на ${VALUE}%"
        set_state "swap"
        ;;
    
    # Swap - OK (только если был high)
    "swap_ok")
        if ! check_state "swap"; then
            exit 0
        fi
        VALUE=$(get_swap_usage)
        MESSAGE="✅ Swap в норме: ${VALUE}%"
        clear_state "swap"
        ;;
    
    # Disk
    "disk_high")
        VALUE=$(df -h / | awk 'NR==2 {print $5}')
        MESSAGE="⚠️ Диск / заполнен на ${VALUE}! Пора чистить."
        set_state "disk"
        ;;
    "inode_high")
        VALUE=$(df -i / | awk 'NR==2 {print $5}')
        MESSAGE="⚠️ Закончились inode на диске /: ${VALUE}!"
        set_state "inode"
        ;;
    
    # Сервисы - с логикой состояний
    *)
        MESSAGE="$ALERT_TYPE"
        STATE_NAME=$(get_service_name "$ALERT_TYPE")
        
        # Определяем тип сообщения по эмодзи
        if [[ "$ALERT_TYPE" == *"⚠️"* ]] || [[ "$ALERT_TYPE" == *"🚨"* ]]; then
            # Проблема - устанавливаем состояние
            set_state "svc_$STATE_NAME"
        elif [[ "$ALERT_TYPE" == *"✅"* ]]; then
            # Восстановление - проверяем было ли падение
            if ! check_state "svc_$STATE_NAME"; then
                exit 0
            fi
            clear_state "svc_$STATE_NAME"
        fi
        ;;
esac

# ============================================
# RATE LIMITING
# ============================================

CURRENT_TIME=$(date +%s)

if [ -f "$LAST_NOTIFY_FILE" ]; then
    LAST_TIME=$(cat "$LAST_NOTIFY_FILE")
    TIME_DIFF=$((CURRENT_TIME - LAST_TIME))

    if [ "$TIME_DIFF" -lt "$RATE_LIMIT_SECONDS" ]; then
        log_info "Сообщение пропущено (rate limit): $ALERT_TYPE"
        exit 0
    fi
fi

# ============================================
# ОТПРАВКА СООБЩЕНИЯ
# ============================================

response=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_MONITOR_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    -d "text=${MESSAGE}")

if echo "$response" | jq -e '.ok' > /dev/null 2>&1; then
    echo "$CURRENT_TIME" > "$LAST_NOTIFY_FILE"
    log_info "Monit уведомление отправлено: $ALERT_TYPE"
    exit 0
else
    error_msg=$(echo "$response" | jq -r '.description // "Unknown error"')
    log_error "Ошибка отправки: $error_msg"
    exit 1
fi
