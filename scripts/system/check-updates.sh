#!/bin/bash
# /opt/server-monitor/scripts/system/check-updates.sh - Проверка обновлений системы

echo "📦 *ПРОВЕРКА ОБНОВЛЕНИЙ*"
echo ""

# Обновляем список пакетов
apt update > /dev/null 2>&1

# Проверяем доступные обновления
UPGRADABLE=$(apt list --upgradable 2>/dev/null | grep -v "Listing..." | wc -l)

if [ $UPGRADABLE -eq 0 ]; then
    echo "✅ Система полностью обновлена"
else
    echo "⚠️ Доступно обновлений: $UPGRADABLE"
    echo ""
    echo "📋 Список пакетов для обновления:"
    echo "----------------------------------------"
    apt list --upgradable 2>/dev/null | grep -v "Listing..." | while read line; do
        echo "  $line"
    done
fi

echo ""
echo "🔄 Для обновления выполните: sudo apt upgrade -y"
