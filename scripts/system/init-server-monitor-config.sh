#!/bin/bash
# /opt/server-monitor/scripts/system/init-server-monitor-config.sh
# Инициализация конфигурационных файлов для server-monitor

set -euo pipefail

CONFIG_DIR="/opt/server-monitor/config"
SETTINGS_FILE="$CONFIG_DIR/settings.json"
SECRETS_FILE="$CONFIG_DIR/secrets.json"
PATHS_FILE="$CONFIG_DIR/paths.json"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "╔══════════════════════════════════════════════╗"
echo "║   Инициализация конфигурации Server Monitor  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Создаём директорию
mkdir -p "$CONFIG_DIR"
chmod 755 "$CONFIG_DIR"

# Проверяем существование файлов
if [ -f "$SETTINGS_FILE" ] || [ -f "$SECRETS_FILE" ] || [ -f "$PATHS_FILE" ]; then
    echo -e "${YELLOW}⚠️  Конфигурационные файлы уже существуют!${NC}"
    echo ""
    read -p "Перезаписать? (yes/no): " OVERWRITE
    if [ "$OVERWRITE" != "yes" ]; then
        echo "Операция отменена."
        exit 0
    fi
    echo ""
fi

# Копируем из примеров
cp /opt/server-monitor/config/examples/settings.json "$SETTINGS_FILE"
cp /opt/server-monitor/config/examples/secrets.json.example "$SECRETS_FILE"
cp /opt/server-monitor/config/examples/paths.json "$PATHS_FILE"

chmod 600 "$SECRETS_FILE"
chmod 644 "$SETTINGS_FILE"
chmod 644 "$PATHS_FILE"

# Создаём недостающие директории
mkdir -p /opt/server-monitor/data
mkdir -p /opt/server-monitor/data/geoip
mkdir -p /var/log/server-monitor
mkdir -p /tmp/server-monitor

echo -e "${GREEN}✅ Конфигурационные файлы созданы:${NC}"
echo "   📄 $SETTINGS_FILE"
echo "   🔒 $SECRETS_FILE (mode 600)"
echo "   📂 $PATHS_FILE"
echo ""
echo -e "${YELLOW}⚠️  ВАЖНО: Отредактируйте secrets.json и укажите ваши токены!${NC}"
echo ""
echo "   nano $SECRETS_FILE"
echo ""
