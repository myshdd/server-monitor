#!/bin/bash
# /opt/server-monitor/scripts/fail2ban/f2b-daily-report.sh
# Ежедневный отчёт Fail2ban в Telegram

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

# Загружаем переменные
load_common_vars

# Проверяем наличие необходимых переменных
if [ -z "$TELEGRAM_MONITOR_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    log_error "Telegram токен или chat_id не настроены"
    exit 1
fi

# ============================================
# ФОРМИРОВАНИЕ ОТЧЁТА
# ============================================

# Получаем статистику от f2b-status.sh
REPORT=$(f2b-status.sh 2>&1)

# Добавляем данные за неделю
REPORT+="

═══════════════════════════════════════
📊 *Недельная статистика атак:*
"

for i in $(seq 7 -1 0); do
    day=$(date -d "$i days ago" +%Y-%m-%d)
    count=$(journalctl -u ssh --since "$day 00:00:00" --until "$day 23:59:59" --no-pager 2>/dev/null | \
        grep -c "Failed password")
    
    # Эмодзи в зависимости от количества атак
    if [ "$count" -eq 0 ]; then
        emoji="✅"
    elif [ "$count" -lt 10 ]; then
        emoji="⚠️"
    elif [ "$count" -lt 50 ]; then
        emoji="🔴"
    else
        emoji="🔥"
    fi
    
    REPORT+="
${emoji}  ${day}: ${count} попыток"
done

# Добавляем время отчёта
REPORT+="

═══════════════════════════════════════
📅 Отчёт за $(date +%d.%m.%Y)
🕐 Время: $(date +%H:%M:%S)
"

# ============================================
# ОТПРАВКА В TELEGRAM
# ============================================

send_telegram "$REPORT" "$TELEGRAM_MONITOR_TOKEN" "$TELEGRAM_CHAT_ID"

log_info "Ежедневный отчёт Fail2ban отправлен"
