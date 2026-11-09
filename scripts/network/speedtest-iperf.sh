#!/bin/bash
# /opt/server-monitor/scripts/network/speedtest-iperf.sh
# Тест скорости через iperf3

source /usr/local/lib/server-monitor/load-config.sh

WORKING_SERVERS=$(get_path "data.iperf_working" "/etc/iperf3-working.txt")
TEST_DURATION=$(get_setting "speedtest.test_duration" "3")
MAX_ATTEMPTS=$(get_setting "speedtest.max_attempts" "5")
TEMP_LOG="/tmp/iperf3-test.log"

> "$TEMP_LOG"

print_header() {
    echo "╔══════════════════════════════════════════════╗"
    echo "║         🌐 ТЕСТ СКОРОСТИ IPERF3             ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
}

test_server() {
    local server=$1
    local port=$2
    local location=$3
    local ping=$4

    echo "📡 Тест на $location ($ping ms)"
    echo "   Сервер: $server:$port"

    if ! ping -c 1 -W 2 $server >/dev/null 2>&1; then
        echo "   ⚠️  Сервер не отвечает на ping"
        return 1
    fi

    if ! timeout 5 iperf3 -c $server -p $port -t 1 -f m > /dev/null 2>&1; then
        echo "   ⚠️  Нет ответа от iperf3"
        return 1
    fi

    echo "   📥 Тест download..."
    DOWNLOAD=$(iperf3 -c $server -p $port -R -f m -O 1 -t $TEST_DURATION 2>&1)
    DOWNLOAD_VAL=$(echo "$DOWNLOAD" | grep "receiver" | tail -1 | awk '{print $7}')

    if [ -z "$DOWNLOAD_VAL" ]; then
        echo "   ❌ Ошибка download"
        return 1
    fi

    echo "   📤 Тест upload..."
    UPLOAD=$(iperf3 -c $server -p $port -f m -O 1 -t $TEST_DURATION 2>&1)
    UPLOAD_VAL=$(echo "$UPLOAD" | grep "receiver" | tail -1 | awk '{print $7}')

    if [ -z "$UPLOAD_VAL" ]; then
        echo "   ❌ Ошибка upload"
        return 1
    fi

    echo "   ✅ ↓ ${DOWNLOAD_VAL} Mbits/sec | ↑ ${UPLOAD_VAL} Mbits/sec"
    return 0
}

print_header

if [ ! -f "$WORKING_SERVERS" ] || [ ! -s "$WORKING_SERVERS" ]; then
    echo "❌ Список серверов не найден: $WORKING_SERVERS"
    echo "   Запустите: update-speedtest-servers.sh"
    exit 1
fi

TOTAL=$(wc -l < "$WORKING_SERVERS")
echo "🚀 Загружено $TOTAL рабочих серверов"
echo ""

SUCCESS=0
attempt=1

while [ $attempt -le $MAX_ATTEMPTS ] && [ $SUCCESS -eq 0 ]; do
    [ $attempt -gt 1 ] && echo "🔄 Попытка $attempt из $MAX_ATTEMPTS..."

    LINE=$(( (RANDOM % 5) + 1 ))
    SERVER_LINE=$(sed -n "${LINE}p" "$WORKING_SERVERS")

    if [ -n "$SERVER_LINE" ]; then
        IFS=':' read -r server port location ping <<< "$SERVER_LINE"
        test_server "$server" "$port" "$location" "$ping" && SUCCESS=1
    fi

    [ $SUCCESS -eq 0 ] && echo "   ⏳ Пробуем другой сервер..." && echo ""
    attempt=$((attempt + 1))
done

if [ $SUCCESS -ne 1 ]; then
    echo ""
    echo "❌ Не удалось выполнить тест после $MAX_ATTEMPTS попыток"
fi

echo ""
echo "📊 Дополнительная информация:"
echo "   🕐 Время: $(date '+%d.%m.%Y %H:%M:%S')"
echo "   🌐 IP: $(hostname -I | awk '{print $1}')"
