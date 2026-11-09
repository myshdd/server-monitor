#!/bin/bash
# /opt/server-monitor/scripts/system/validate-config.sh
# Полная валидация конфигурации с проверкой всех зависимостей

source /usr/local/lib/server-monitor/load-config.sh

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           ВАЛИДАЦИЯ КОНФИГУРАЦИИ SERVER-MONITOR              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ============================================
# 1. ПРОВЕРКА КОНФИГУРАЦИОННЫХ ФАЙЛОВ
# ============================================
echo -e "${BLUE}[1/10]${NC} Проверка конфигурационных файлов..."

if [ -f "$SETTINGS_FILE" ]; then
    echo -e "   ${GREEN}✅${NC} $SETTINGS_FILE"
    # Валидация JSON
    if jq empty "$SETTINGS_FILE" 2>/dev/null; then
        echo -e "      ${GREEN}✓${NC} Валидный JSON"
    else
        echo -e "      ${RED}✗${NC} Невалидный JSON!"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "   ${RED}✗${NC} $SETTINGS_FILE не найден"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "$SECRETS_FILE" ]; then
    echo -e "   ${GREEN}✅${NC} $SECRETS_FILE"
    # Проверка прав доступа
    PERMS=$(stat -c %a "$SECRETS_FILE")
    if [ "$PERMS" = "600" ]; then
        echo -e "      ${GREEN}✓${NC} Права доступа: $PERMS (корректно)"
    else
        echo -e "      ${YELLOW}⚠${NC} Права доступа: $PERMS (рекомендуется 600)"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    # Проверка что токены заменены
    if grep -q "ЗАМЕНИТЕ" "$SECRETS_FILE"; then
        echo -e "      ${RED}✗${NC} Токены не заменены на реальные!"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "      ${GREEN}✓${NC} Токены настроены"
    fi
else
    echo -e "   ${RED}✗${NC} $SECRETS_FILE не найден"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "$PATHS_FILE" ]; then
    echo -e "   ${GREEN}✅${NC} $PATHS_FILE"
else
    echo -e "   ${RED}✗${NC} $PATHS_FILE не найден"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# ============================================
# 2. ПРОВЕРКА ЗАВИСИМОСТЕЙ
# ============================================
echo -e "${BLUE}[2/10]${NC} Проверка установленных зависимостей..."

DEPS=("jq" "curl" "python3" "fail2ban-client" "docker" "iptables" "ipset")
for cmd in "${DEPS[@]}"; do
    if command -v $cmd &> /dev/null; then
        version=$($cmd --version 2>&1 | head -1 || echo "unknown")
        echo -e "   ${GREEN}✅${NC} $cmd"
    else
        echo -e "   ${RED}✗${NC} $cmd не установлен"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# ============================================
# 3. ПРОВЕРКА PYTHON ОКРУЖЕНИЙ
# ============================================
echo -e "${BLUE}[3/10]${NC} Проверка Python окружений..."

ADMIN_VENV=$(get_path "python.admin_bot_venv")
MONITOR_VENV=$(get_path "python.monitor_bot_venv")

if [ -d "$ADMIN_VENV" ]; then
    echo -e "   ${GREEN}✅${NC} Admin bot venv: $ADMIN_VENV"
    if [ -f "$ADMIN_VENV/bin/python3" ]; then
        PY_VERSION=$("$ADMIN_VENV/bin/python3" --version 2>&1)
        echo -e "      ${GREEN}✓${NC} $PY_VERSION"
    fi
else
    echo -e "   ${RED}✗${NC} Admin bot venv не найден: $ADMIN_VENV"
    ERRORS=$((ERRORS + 1))
fi

if [ -d "$MONITOR_VENV" ]; then
    echo -e "   ${GREEN}✅${NC} Monitor bot venv: $MONITOR_VENV"
    if [ -f "$MONITOR_VENV/bin/python3" ]; then
        PY_VERSION=$("$MONITOR_VENV/bin/python3" --version 2>&1)
        echo -e "      ${GREEN}✓${NC} $PY_VERSION"
    fi
else
    echo -e "   ${RED}✗${NC} Monitor bot venv не найден: $MONITOR_VENV"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# ============================================
# 4. ПРОВЕРКА ДИРЕКТОРИЙ
# ============================================
echo -e "${BLUE}[4/10]${NC} Проверка необходимых директорий..."

load_common_vars

DIRS=(
    "$LOG_DIR:Логи"
    "$NETWORK_STATS_DIR:Сетевая статистика"
    "$GEOIP_DIR:GeoIP данные"
    "/usr/local/lib/server-monitor:Библиотеки"
    "/tmp/server-monitor:Временные файлы"
)

for dir_entry in "${DIRS[@]}"; do
    IFS=':' read -r dir desc <<< "$dir_entry"
    if [ -d "$dir" ]; then
        echo -e "   ${GREEN}✅${NC} $desc: $dir"
    else
        echo -e "   ${YELLOW}⚠${NC} $desc не существует: $dir (будет создана)"
        mkdir -p "$dir"
        WARNINGS=$((WARNINGS + 1))
    fi
done

echo ""

# ============================================
# 5. ПРОВЕРКА КРИТИЧНЫХ ФАЙЛОВ
# ============================================
echo -e "${BLUE}[5/10]${NC} Проверка критичных файлов данных..."

FILES=(
    "$GEOIP_RU_ZONE:GeoIP список России"
    "/etc/iperf3-working.txt:Список iperf3 серверов"
)

for file_entry in "${FILES[@]}"; do
    IFS=':' read -r file desc <<< "$file_entry"
    if [ -f "$file" ]; then
        size=$(stat -c%s "$file")
        if [ $size -gt 0 ]; then
            echo -e "   ${GREEN}✅${NC} $desc: $file ($(numfmt --to=iec-i --suffix=B $size))"
        else
            echo -e "   ${YELLOW}⚠${NC} $desc пустой: $file"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo -e "   ${YELLOW}⚠${NC} $desc не найден: $file"
        WARNINGS=$((WARNINGS + 1))
    fi
done

echo ""

# ============================================
# 6. ПРОВЕРКА TELEGRAM ПОДКЛЮЧЕНИЯ
# ============================================
echo -e "${BLUE}[6/10]${NC} Проверка подключения к Telegram..."

ADMIN_TOKEN=$(get_secret "telegram.admin_bot_token")
MONITOR_TOKEN=$(get_secret "telegram.monitor_bot_token")
CHAT_ID=$(get_secret "telegram.chat_id")

# Проверка admin bot
if [ -n "$ADMIN_TOKEN" ] && [ "$ADMIN_TOKEN" != "0" ]; then
    response=$(curl -s "https://api.telegram.org/bot${ADMIN_TOKEN}/getMe")
    if echo "$response" | jq -e '.ok' > /dev/null 2>&1; then
        bot_name=$(echo "$response" | jq -r '.result.username')
        echo -e "   ${GREEN}✅${NC} Admin bot: @$bot_name"
    else
        echo -e "   ${RED}✗${NC} Admin bot токен невалиден"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "   ${RED}✗${NC} Admin bot токен не настроен"
    ERRORS=$((ERRORS + 1))
fi

# Проверка monitor bot
if [ -n "$MONITOR_TOKEN" ] && [ "$MONITOR_TOKEN" != "0" ]; then
    response=$(curl -s "https://api.telegram.org/bot${MONITOR_TOKEN}/getMe")
    if echo "$response" | jq -e '.ok' > /dev/null 2>&1; then
        bot_name=$(echo "$response" | jq -r '.result.username')
        echo -e "   ${GREEN}✅${NC} Monitor bot: @$bot_name"
    else
        echo -e "   ${RED}✗${NC} Monitor bot токен невалиден"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "   ${RED}✗${NC} Monitor bot токен не настроен"
    ERRORS=$((ERRORS + 1))
fi

# Проверка chat_id
if [ -n "$CHAT_ID" ] && [ "$CHAT_ID" != "0" ]; then
    echo -e "   ${GREEN}✅${NC} Chat ID: $CHAT_ID"
else
    echo -e "   ${RED}✗${NC} Chat ID не настроен"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# ============================================
# 7. ПРОВЕРКА FAIL2BAN
# ============================================
echo -e "${BLUE}[7/10]${NC} Проверка Fail2ban..."

if systemctl is-active --quiet fail2ban; then
    echo -e "   ${GREEN}✅${NC} Fail2ban запущен"
    
    # Проверяем наличие jail'ов
    JAILS=$(fail2ban-client status 2>/dev/null | grep "Jail list" | sed 's/.*://;s/,/ /g')
    if [ -n "$JAILS" ]; then
        echo -e "   ${GREEN}✅${NC} Активные jail'ы: $JAILS"
    else
        echo -e "   ${YELLOW}⚠${NC} Нет активных jail'ов"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "   ${RED}✗${NC} Fail2ban не запущен"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# ============================================
# 8. ПРОВЕРКА DOCKER
# ============================================
echo -e "${BLUE}[8/10]${NC} Проверка Docker..."

if systemctl is-active --quiet docker; then
    echo -e "   ${GREEN}✅${NC} Docker запущен"
    
    CONTAINERS=$(docker ps --format '{{.Names}}' 2>/dev/null | wc -l)
    echo -e "   ${GREEN}✓${NC} Запущено контейнеров: $CONTAINERS"
else
    echo -e "   ${YELLOW}⚠${NC} Docker не запущен"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# ============================================
# 9. ПРОВЕРКА SYSTEMD СЕРВИСОВ
# ============================================
echo -e "${BLUE}[9/10]${NC} Проверка systemd сервисов..."

SERVICES=(
    "telegram-admin-bot:Admin Telegram bot"
    "telegram-monitor:Monitor Telegram bot"
)

for service_entry in "${SERVICES[@]}"; do
    IFS=':' read -r service desc <<< "$service_entry"
    
    if systemctl list-unit-files | grep -q "^${service}.service"; then
        if systemctl is-active --quiet "$service"; then
            echo -e "   ${GREEN}✅${NC} $desc ($service) - запущен"
        else
            echo -e "   ${YELLOW}⚠${NC} $desc ($service) - не запущен"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo -e "   ${YELLOW}⚠${NC} $desc ($service) - сервис не создан"
        WARNINGS=$((WARNINGS + 1))
    fi
done

echo ""

# ============================================
# 10. ПРОВЕРКА CRON ЗАДАЧ
# ============================================
echo -e "${BLUE}[10/10]${NC} Проверка cron задач..."

CRON_JOBS=$(crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$' | wc -l)
if [ $CRON_JOBS -gt 0 ]; then
    echo -e "   ${GREEN}✅${NC} Настроено cron задач: $CRON_JOBS"
    
    # Проверяем ключевые задачи
    if crontab -l 2>/dev/null | grep -q "collect-network-stats"; then
        echo -e "   ${GREEN}✓${NC} Сбор сетевой статистики"
    else
        echo -e "   ${YELLOW}⚠${NC} Сбор сетевой статистики не настроен"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    if crontab -l 2>/dev/null | grep -q "update-ips.sh"; then
        echo -e "   ${GREEN}✓${NC} Обновление GeoIP"
    else
        echo -e "   ${YELLOW}⚠${NC} Обновление GeoIP не настроено"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "   ${YELLOW}⚠${NC} Cron задачи не настроены"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo "══════════════════════════════════════════════════════════════"

# ============================================
# ИТОГИ
# ============================================
echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ ВСЁ ОТЛИЧНО!${NC} Конфигурация полностью корректна."
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  ЕСТЬ ПРЕДУПРЕЖДЕНИЯ${NC}"
    echo -e "   Найдено предупреждений: $WARNINGS"
    echo -e "   Система работоспособна, но рекомендуется устранить предупреждения."
else
    echo -e "${RED}❌ ОБНАРУЖЕНЫ ОШИБКИ!${NC}"
    echo -e "   Критичных ошибок: $ERRORS"
    echo -e "   Предупреждений: $WARNINGS"
    echo -e "   Необходимо устранить ошибки перед запуском системы."
    exit 1
fi

echo ""
