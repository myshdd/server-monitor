#!/bin/bash
# /opt/server-monitor/scripts/network/speedtest-stats.sh
# Статистика по серверам

source /usr/local/lib/server-monitor/load-config.sh

WORKING_SERVERS=$(get_path "data.iperf_working" "/etc/iperf3-working.txt")
LOG_FILE=$(get_path "logs.iperf_update" "/var/log/iperf3-update.log")

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
    if [ -f "$LOG_FILE" ]; then
        tail -5 "$LOG_FILE" | grep "ОБНОВЛЕНИЕ ЗАВЕРШЕНО" -B2
    else
        echo "   Лог-файл не найден"
    fi
else
    echo "❌ Файл с серверами не найден: $WORKING_SERVERS"
fi
