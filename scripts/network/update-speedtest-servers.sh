#!/bin/bash
# /usr/local/bin/update-speedtest-servers.sh
# Обновление списка рабочих iperf3 серверов
# Использует конфигурацию из /root/.config/server-monitor/

source /usr/local/lib/server-monitor/load-config.sh

WORKING_SERVERS=$(get_path "data.iperf_working" "/etc/iperf3-working.txt")
LOG_FILE=$(get_path "logs.iperf_update" "/var/log/iperf3-update.log")

log_info "Начало обновления списка iperf3 серверов"

# Список серверов (тот же что был в оригинале)
SERVERS=(
    "speedtest.hostkey.ru:5201:Россия (Hostkey)"
    "iperf.comstor.ru:5201:Россия (Comstor)"
    "speedtest.wtnet.de:5200:Германия (WTNet)"
    "fra.speedtest.clouvider.net:5200:Германия (Clouvider)"
    "ams.speedtest.clouvider.net:5200:Нидерланды (Clouvider)"
    "speedtest.novoserve.com:5201:Нидерланды (Novoserve)"
    "ping-ams1.online.net:5200:Нидерланды (Online.net)"
    "lon.speedtest.clouvider.net:5200:Великобритания (Clouvider)"
)

check_server() {
    local server=$1
    local port=$2
    local location=$3
    
    ping -c 1 -W 1 $server >/dev/null 2>&1 || return 1
    
    local ping_time=$(ping -c 1 $server 2>/dev/null | grep time= | awk -F 'time=' '{print $2}' | awk '{print $1}' | cut -d '.' -f1)
    
    if timeout 3 iperf3 -c $server -p $port -t 1 -f m >/dev/null 2>&1; then
        echo "$server:$port:$location:$ping_time"
        return 0
    fi
    return 1
}

echo "" > /tmp/working.tmp

total=${#SERVERS[@]}
count=0
working=0

for server_entry in "${SERVERS[@]}"; do
    server=$(echo $server_entry | cut -d: -f1)
    port=$(echo $server_entry | cut -d: -f2)
    location=$(echo $server_entry | cut -d: -f3-)
    
    count=$((count + 1))
    printf "\rПроверка: %d/%d, Найдено: %d" $count $total $working
    
    if result=$(check_server "$server" "$port" "$location"); then
        echo "$result" >> /tmp/working.tmp
        working=$((working + 1))
    fi
done

printf "\n\n"

if [ -s /tmp/working.tmp ]; then
    sort -t':' -k4 -n /tmp/working.tmp > "$WORKING_SERVERS"
    log_info "Найдено рабочих серверов: $working"
    
    echo "✅ Найдено $working рабочих серверов"
    echo "📁 Сохранено в: $WORKING_SERVERS"
    
    echo ""
    echo "🏆 Топ-5 лучших:"
    head -5 "$WORKING_SERVERS" | while IFS=: read server port location ping; do
        echo "   ${ping}ms - $location ($server:$port)"
    done
else
    log_error "Не найдено рабочих серверов"
    echo "❌ Не найдено рабочих серверов"
fi

rm -f /tmp/working.tmp
