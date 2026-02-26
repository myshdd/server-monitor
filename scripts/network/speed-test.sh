#!/bin/bash
# /opt/server-monitor/scripts/network/speed-test.sh
# Измерение скорости сети

# Фиксируем локаль для корректной работы с числами
export LC_NUMERIC=C

# Определяем основной интерфейс (берем тот, который имеет маршрут по умолчанию)
DEFAULT_IF=$(ip route | grep default | awk '{print $5}' | head -1)

if [ -z "$DEFAULT_IF" ]; then
    echo "❌ Не удалось определить основной сетевой интерфейс"
    exit 1
fi

echo "🌐 Основной интерфейс: $DEFAULT_IF"
echo "⏱️  Измерение скорости за 10 секунд..."
echo ""

# Функция форматирования скорости
format_speed() {
    local speed=$1
    if (( $(echo "$speed > 1000000" | bc -l) )); then
        printf "%.2f MB/s" $(echo "$speed / 1000000" | bc -l)
    elif (( $(echo "$speed > 1000" | bc -l) )); then
        printf "%.2f KB/s" $(echo "$speed / 1000" | bc -l)
    else
        printf "%.0f B/s" $speed
    fi
}

# Получаем начальные счетчики
RX1=$(cat /sys/class/net/$DEFAULT_IF/statistics/rx_bytes)
TX1=$(cat /sys/class/net/$DEFAULT_IF/statistics/tx_bytes)
sleep 10
RX2=$(cat /sys/class/net/$DEFAULT_IF/statistics/rx_bytes)
TX2=$(cat /sys/class/net/$DEFAULT_IF/statistics/tx_bytes)

# Вычисляем скорость (байт в секунду)
RX_SPEED=$(( ($RX2 - $RX1) / 10 ))
TX_SPEED=$(( ($TX2 - $TX1) / 10 ))

# Вычисляем общий трафик
RX_TOTAL=$RX2
TX_TOTAL=$TX2

# Форматируем для вывода
RX_SPEED_FMT=$(format_speed $RX_SPEED)
TX_SPEED_FMT=$(format_speed $TX_SPEED)

echo "📥 Входящая скорость:  $RX_SPEED_FMT"
echo "📤 Исходящая скорость: $TX_SPEED_FMT"
echo ""
echo "📊 Общий трафик с момента запуска:"
echo "   📥 Получено:  $(numfmt --to=iec $RX_TOTAL)"
echo "   📤 Отправлено: $(numfmt --to=iec $TX_TOTAL)"
