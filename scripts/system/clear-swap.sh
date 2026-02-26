#!/bin/bash
# /opt/server-monitor/scripts/system/clear-swap.sh
# Безопасная очистка swap-памяти

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

log_info "Начало очистки swap"

echo "🔄 Проверка использования swap..."

# Проверяем, настроен ли swap (ищем Swap или Подкачка)
SWAP_TOTAL=$(free -m | awk '/Swap:|Подкачка:/ {print $2}')

if [ -z "$SWAP_TOTAL" ] || [ "$SWAP_TOTAL" -eq 0 ]; then
    echo "⚠️ Swap не настроен на этом сервере"
    log_warning "Swap не обнаружен"
    exit 0
fi

SWAP_USED=$(free -m | awk '/Swap:|Подкачка:/ {print $3}')
SWAP_USED=${SWAP_USED:-0}

if [ "$SWAP_USED" -eq 0 ]; then
    echo "✅ Swap уже пуст (всего: ${SWAP_TOTAL}MB)"
    log_info "Swap уже пуст, очистка не требуется"
    exit 0
fi

echo "📊 Использовано swap: ${SWAP_USED}MB из ${SWAP_TOTAL}MB"

# Проверяем свободную память (Mem или Память)
FREE_MEM=$(free -m | awk '/Mem:|Память:/ {print $7}')
FREE_MEM=${FREE_MEM:-$(free -m | awk '/Mem:|Память:/ {print $4}')}
FREE_MEM=${FREE_MEM:-0}

echo "💾 Свободно RAM: ${FREE_MEM}MB"

if [ "$FREE_MEM" -lt "$SWAP_USED" ]; then
    echo "⚠️  Недостаточно свободной RAM для очистки swap!"
    echo "   Свободно RAM: ${FREE_MEM}MB, Использовано swap: ${SWAP_USED}MB"
    log_warning "Недостаточно RAM для очистки swap: RAM=${FREE_MEM}MB, SWAP=${SWAP_USED}MB"
    exit 1
fi

echo "⚠️  Очистка swap..."

# Отключаем swap
if swapoff -a; then
    echo "✅ Swap отключен"
    log_info "Swap отключен"

    # Включаем swap обратно
    if swapon -a; then
        echo "✅ Swap включен обратно"
        echo "🧹 Swap успешно очищен!"
        log_info "Swap очищен и включен обратно"
    else
        echo "❌ Ошибка при включении swap!"
        log_error "Ошибка включения swap"
        exit 1
    fi
else
    echo "❌ Ошибка при отключении swap!"
    log_error "Ошибка отключения swap"
    exit 1
fi

# Проверяем результат
NEW_SWAP=$(free -m | awk '/Swap:|Подкачка:/ {print $3}')
NEW_SWAP=${NEW_SWAP:-0}
echo "📊 Swap после очистки: ${NEW_SWAP}MB"
