#!/bin/bash
# /usr/local/bin/speedtest-stats.sh - Статистика по серверам

WORKING_SERVERS="/etc/iperf3-working.txt"
LOG_FILE="/var/log/iperf3-update.log"

echo "╔══════════════════════════════════════════════╗"
echo "║      📊 СТАТИСТИКА IPERF3 СЕРВЕРОВ          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

if [ -f "$WORKING_SERVERS" ]; then
    TOTAL=$(wc -l < "$WORKING_SERVERS")
    echo "✅ Всего рабочих серверов: $TOTAL"
    echo ""
    
    echo "🏆 Топ-10 серверов (по пингу):"
    echo "----------------------------------------"
    head -10 "$WORKING_SERVERS" | nl -w2 -s'. ' | while read line; do
        IFS=':' read -r num server port location ping <<< "$line"
        printf "   %s %-25s %3sms\n" "$num" "$location" "$ping"
    done
    
    echo ""
    echo "📊 Распределение по регионам:"
    echo "----------------------------------------"
    cut -d: -f3 "$WORKING_SERVERS" | cut -d' ' -f1 | sort | uniq -c | sort -rn | while read count region; do
        printf "   %3d - %s\n" "$count" "$region"
    done
    
    echo ""
    echo "📅 Последнее обновление:"
    tail -5 "$LOG_FILE" | grep "ОБНОВЛЕНИЕ ЗАВЕРШЕНО" -B2
else
    echo "❌ Файл с серверами не найден"
fi
