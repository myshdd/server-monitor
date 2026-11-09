#!/bin/bash
# /opt/server-monitor/scripts/system/full-upgrade.sh - Полное обновление системы

echo "🔄 Начинаем полное обновление системы..."
echo ""

# Обновление списка пакетов
echo "📦 Обновление списка пакетов..."
apt update

# Установка обновлений
echo ""
echo "⬆️ Установка обновлений (upgrade)..."
apt upgrade -y

# Обновление с изменением зависимостей
echo ""
echo "🔄 Обновление с изменением зависимостей (dist-upgrade)..."
apt dist-upgrade -y

# Удаление ненужных пакетов
echo ""
echo "🧹 Очистка..."
apt autoremove -y
apt autoclean

# Проверка оставшихся обновлений
echo ""
echo "📊 Проверка оставшихся обновлений..."
UPGRADABLE=$(apt list --upgradable 2>/dev/null | grep -v "Listing..." | wc -l)

if [ $UPGRADABLE -eq 0 ]; then
    echo ""
    echo "✅ Система полностью обновлена!"
else
    echo ""
    echo "⚠️ Осталось обновлений: $UPGRADABLE"
    apt list --upgradable 2>/dev/null | grep -v "Listing..."
fi

echo ""
echo "📅 Дата обновления: $(date '+%d.%m.%Y %H:%M:%S')"
