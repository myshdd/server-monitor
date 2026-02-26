#!/bin/bash
# /opt/server-monitor/scripts/system/test-config.sh
# Тестирование загрузки конфигурации

# Подключаем библиотеку
source /usr/local/lib/server-monitor/load-config.sh

echo "╔══════════════════════════════════════════════╗"
echo "║        Тест загрузки конфигурации            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Тест 1: Проверка файлов
echo "1️⃣  Проверка конфигурационных файлов..."
if check_config_files; then
    echo "   ✅ Все файлы найдены"
else
    echo "   ❌ Не все файлы найдены"
    exit 1
fi
echo ""

# Тест 2: Чтение настроек
echo "2️⃣  Чтение из settings.json..."
CHECK_INTERVAL=$(get_setting "monitoring.check_interval")
CPU_THRESHOLD=$(get_setting "monitoring.thresholds.cpu")
echo "   Check interval: $CHECK_INTERVAL сек"
echo "   CPU threshold: $CPU_THRESHOLD%"
echo ""

# Тест 3: Чтение секретов
echo "3️⃣  Чтение из secrets.json..."
CHAT_ID=$(get_secret "telegram.chat_id")
if [ -n "$CHAT_ID" ] && [ "$CHAT_ID" != "0" ]; then
    echo "   ✅ Chat ID: $CHAT_ID"
else
    echo "   ⚠️  Chat ID не настроен"
fi
echo ""

# Тест 4: Чтение путей
echo "4️⃣  Чтение из paths.json..."
LOG_DIR=$(get_path "logs.base_dir")
GEOIP_DIR=$(get_path "data.geoip_dir")
echo "   Log dir: $LOG_DIR"
echo "   GeoIP dir: $GEOIP_DIR"
echo ""

# Тест 5: Загрузка общих переменных
echo "5️⃣  Загрузка общих переменных..."
load_common_vars
echo "   TELEGRAM_CHAT_ID: $TELEGRAM_CHAT_ID"
echo "   CPU_THRESHOLD: $CPU_THRESHOLD"
echo "   F2B_SUBNET_THRESHOLD: $F2B_SUBNET_THRESHOLD"
echo ""

# Тест 6: Функции логирования
echo "6️⃣  Тест функций логирования..."
log_info "Тестовое информационное сообщение"
log_warning "Тестовое предупреждение"
echo ""

echo "✅ Все тесты пройдены!"
