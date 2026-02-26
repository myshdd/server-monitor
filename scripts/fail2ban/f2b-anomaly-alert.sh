#!/bin/bash
# /opt/server-monitor/scripts/fail2ban/f2b-anomaly-alert.sh
# Обнаружение аномалий в Fail2ban и отправка уведомлений в Telegram
# Использует централизованную конфигурацию

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

# Загружаем переменные
load_common_vars

# Проверяем наличие необходимых переменных
if [ -z "$TELEGRAM_MONITOR_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    log_error "Telegram токен или chat_id не настроены"
    exit 1
fi

# Локальные переменные
ANOMALY_THRESHOLD=$(get_setting "fail2ban.alert_anomaly_threshold" "50")
LOG_FILE=$(get_path "logs.f2b_anomaly" "/var/log/f2b-anomaly.log")

# ============================================
# ФУНКЦИИ
# ============================================

send_alert() {
    local message="$1"
    send_telegram "$message" "$TELEGRAM_MONITOR_TOKEN" "$TELEGRAM_CHAT_ID"
}

# ============================================
# 1. Резкий всплеск атак (за 15 минут)
# ============================================

ATTACKS_15MIN=$(journalctl -u ssh --since "15 minutes ago" --no-pager 2>/dev/null | \
    grep -c "Failed password")

PREV_15MIN=$(journalctl -u ssh --since "30 minutes ago" --until "15 minutes ago" --no-pager 2>/dev/null | \
    grep -c "Failed password")

if [ "$ATTACKS_15MIN" -gt 20 ] && [ "$ATTACKS_15MIN" -gt $((PREV_15MIN * 2)) ]; then
    send_alert "🔥 *ВСПЛЕСК АТАК!*

За последние 15 минут: *$ATTACKS_15MIN* попыток
Предыдущие 15 минут: $PREV_15MIN

Рост более чем в 2 раза!"
    log_warning "Всплеск атак: $ATTACKS_15MIN попыток за 15 минут"
fi

# ============================================
# 2. Подозрительно много разных IP
# ============================================

UNIQUE_IPS=$(journalctl -u ssh --since "1 hour ago" --no-pager 2>/dev/null | \
    grep "Failed password" | grep -oP 'from \K[0-9.]+' | sort -u | wc -l)

if [ "$UNIQUE_IPS" -gt 10 ]; then
    send_alert "🌐 *МНОГО УНИКАЛЬНЫХ IP!*

За последний час атаки с *$UNIQUE_IPS* разных IP-адресов.

Возможна распределённая атака."
    log_warning "Распределённая атака: $UNIQUE_IPS уникальных IP"
fi

# ============================================
# 3. Необычно много попыток за последний час
# ============================================

ATTACKS_1H=$(journalctl -u ssh --since "1 hour ago" --no-pager 2>/dev/null | \
    grep -c "Failed password")

if [ "$ATTACKS_1H" -gt "$ANOMALY_THRESHOLD" ]; then
    send_alert "📈 *ВЫСОКАЯ АКТИВНОСТЬ!*

За последний час: *$ATTACKS_1H* неудачных попыток входа.

Порог: $ANOMALY_THRESHOLD"
    log_warning "Высокая активность: $ATTACKS_1H попыток за час"
fi

# ============================================
# 4. Проверка самых активных атакующих
# ============================================

TOP_ATTACKER=$(journalctl -u ssh --since "1 hour ago" --no-pager 2>/dev/null | \
    grep "Failed password" | grep -oP 'from \K[0-9.]+' | sort | uniq -c | sort -rn | head -1)

if [ -n "$TOP_ATTACKER" ]; then
    COUNT=$(echo "$TOP_ATTACKER" | awk '{print $1}')
    IP=$(echo "$TOP_ATTACKER" | awk '{print $2}')
    
    if [ "$COUNT" -gt 20 ]; then
        send_alert "🎯 *САМЫЙ АКТИВНЫЙ АТАКУЮЩИЙ*

IP: \`$IP\`
Попыток за последний час: $COUNT

Проверьте: \`fail2ban-client status sshd | grep $IP\`"
        log_warning "Активный атакующий: $IP ($COUNT попыток)"
    fi
fi

# ============================================
# 5. Сохраняем статистику
# ============================================

echo "$(date +%Y-%m-%d_%H:%M:%S): 15min=$ATTACKS_15MIN, 1h=$ATTACKS_1H, unique=$UNIQUE_IPS" >> "$LOG_FILE"

log_info "Проверка аномалий завершена: 15min=$ATTACKS_15MIN, 1h=$ATTACKS_1H, unique=$UNIQUE_IPS"
