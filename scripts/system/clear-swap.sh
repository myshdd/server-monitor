#!/bin/bash
# /usr/local/bin/clear-swap.sh
# Безопасная очистка swap-памяти
# Использует конфигурацию из /root/.config/server-monitor/

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

log_info "Начало очистки swap"

echo "🔄 Проверка использования swap..."
SWAP_USED=$(free -m | awk '/Swap:/ {print $3}')

if [ "$SWAP_USED" -eq 0 ]; then
    echo "✅ Swap уже пуст"
    log_info "Swap уже пуст, очистка не требуется"
    exit 0
fi

echo "📊 Использовано swap: $(free -h | awk '/Swap:/ {print $3}')"

# Проверяем свободную память
FREE_MEM=$(free -m | awk '/Mem:/ {print $7}')
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
NEW_SWAP=$(free -h | awk '/Swap:/ {print $3}')
echo "📊 Swap после очистки: $NEW_SWAP"
