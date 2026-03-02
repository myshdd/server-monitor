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

# Файл для rate limiting
LAST_NOTIFY_FILE="/tmp/monit-alert-$(echo "$1" | md5sum | cut -c1-8)"
RATE_LIMIT_SECONDS=300

# ============================================
# ПРОВЕРКА АРГУМЕНТОВ
# ============================================

ALERT_TYPE="$1"

if [ -z "$ALERT_TYPE" ]; then
    log_error "Не указан тип алерта"
    echo "Использование: $0 <тип_алерта>"
    exit 1
fi

# ============================================
# ВЫЧИСЛЕНИЕ ЗНАЧЕНИЙ
# ============================================

case "$ALERT_TYPE" in
    # CPU Load
    "load1_high")
        VALUE=$(cat /proc/loadavg | awk '{print $1}')
        MESSAGE="⚠️ Высокая нагрузка CPU (1мин): ${VALUE}"
        ;;
    "load5_high")
        VALUE=$(cat /proc/loadavg | awk '{print $2}')
        MESSAGE="⚠️ Высокая нагрузка CPU (5мин): ${VALUE}"
        ;;
    "load15_high")
        VALUE=$(cat /proc/loadavg | awk '{print $3}')
        MESSAGE="⚠️ Высокая нагрузка CPU (15мин): ${VALUE}"
        ;;
    "load1_ok")
        VALUE=$(cat /proc/loadavg | awk '{print $1}')
        MESSAGE="✅ Нагрузка CPU (1мин) в норме: ${VALUE}"
        ;;
    "load5_ok")
        VALUE=$(cat /proc/loadavg | awk '{print $2}')
        MESSAGE="✅ Нагрузка CPU (5мин) в норме: ${VALUE}"
        ;;
    
    # Memory
    "memory_high")
        VALUE=$(free -m | awk 'NR==2 {if($2>0) printf "%.1f", $3*100/$2; else print "0"}')
        MESSAGE="⚠️ Заканчивается память: использовано ${VALUE}%"
        ;;
    "memory_ok")
        VALUE=$(free -m | awk 'NR==2 {if($2>0) printf "%.1f", $3*100/$2; else print "0"}')
        MESSAGE="✅ Память в норме: использовано ${VALUE}%"
        ;;

    # Swap
    "swap_high")
        VALUE=$(free -m | awk 'NR==3 {if($2>0) printf "%.1f", $3*100/$2; else print "0"}')
        MESSAGE="⚠️ Swap заполнен на ${VALUE}%"
        ;;
    "swap_ok")
        VALUE=$(free -m | awk 'NR==3 {if($2>0) printf "%.1f", $3*100/$2; else print "0"}')
        MESSAGE="✅ Swap в норме: ${VALUE}%"
        ;;
    
    # Disk
    "disk_high")
        VALUE=$(df -h / | awk 'NR==2 {print $5}')
        MESSAGE="⚠️ Диск / заполнен на ${VALUE}! Пора чистить."
        ;;
    "inode_high")
        VALUE=$(df -i / | awk 'NR==2 {print $5}')
        MESSAGE="⚠️ Закончились inode на диске /: ${VALUE}!"
        ;;
    
    # Services - простые сообщения без значений
    *)
        MESSAGE="$ALERT_TYPE"
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
