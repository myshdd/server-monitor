#!/bin/bash
# /opt/server-monitor/scripts/system/monit-telegram.sh
# Отправка уведомлений от Monit в Telegram

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
LAST_NOTIFY_FILE="/tmp/monit-last-notify"
RATE_LIMIT_SECONDS=300  # 5 минут

# ============================================
# ПРОВЕРКА АРГУМЕНТОВ
# ============================================

if [ -z "$1" ]; then
    log_error "Не указан текст сообщения"
    echo "Использование: $0 \"текст сообщения\""
    exit 1
fi

MESSAGE="$1"
CURRENT_TIME=$(date +%s)

# ============================================
# RATE LIMITING
# ============================================

if [ -f "$LAST_NOTIFY_FILE" ]; then
    LAST_TIME=$(cat "$LAST_NOTIFY_FILE")
    TIME_DIFF=$((CURRENT_TIME - LAST_TIME))

    if [ "$TIME_DIFF" -lt "$RATE_LIMIT_SECONDS" ]; then
        log_info "Сообщение пропущено (rate limit): отправлено $TIME_DIFF сек назад"
        exit 0
    fi
fi

# ============================================
# ОТПРАВКА СООБЩЕНИЯ (без Markdown)
# ============================================

response=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_MONITOR_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    -d "text=${MESSAGE}")

if echo "$response" | jq -e '.ok' > /dev/null 2>&1; then
    echo "$CURRENT_TIME" > "$LAST_NOTIFY_FILE"
    log_info "Monit уведомление отправлено"
    exit 0
else
    error_msg=$(echo "$response" | jq -r '.description // "Unknown error"')
    log_error "Ошибка отправки: $error_msg"
    exit 1
fi
