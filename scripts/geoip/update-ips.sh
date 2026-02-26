#!/bin/bash
# /opt/server-monitor/scripts/geoip/update-ips.sh
# Обновление списка IP-адресов России

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

# Загружаем пути
GEOIP_DIR=$(get_path "data.geoip_dir" "/opt/server-monitor/data/geoip")
GEOIP_FILE=$(get_path "data.geoip_ru_zone" "/opt/server-monitor/data/geoip/ru.zone")
COUNTRY_CODE=$(get_setting "geoip.country_code" "ru")
GEOIP_SOURCE=$(get_setting "geoip.source" "ipverse")

cd "$GEOIP_DIR"

log_info "Начало обновления GeoIP"

# Сохраняем старый список как бэкап
if [ -f "$GEOIP_FILE" ]; then
    cp "$GEOIP_FILE" "${GEOIP_FILE}.backup"
    log_info "Создан бэкап: ${GEOIP_FILE}.backup"
fi

# Скачиваем свежий список
echo "📥 Загрузка списка IP России с IPverse..."

if [ "$GEOIP_SOURCE" = "ipverse" ]; then
    URL="https://raw.githubusercontent.com/ipverse/rir-ip/master/country/${COUNTRY_CODE}/ipv4-aggregated.txt"
else
    URL="https://www.ipdeny.com/ipblocks/data/countries/${COUNTRY_CODE}.zone"
fi

curl -sf -o "${GEOIP_FILE}.new" "$URL"

# Проверяем что скачалось успешно
if [ -s "${GEOIP_FILE}.new" ] && grep -v '^#' "${GEOIP_FILE}.new" | head -5 | grep -q '/'; then
    mv "${GEOIP_FILE}.new" "$GEOIP_FILE"

    COUNT=$(grep -v '^#' "$GEOIP_FILE" | wc -l)
    echo "✅ Список IP России обновлён $(date)"
    echo "   Всего диапазонов: $COUNT"

    log_info "GeoIP обновлён: $COUNT диапазонов"

    # Применяем обновлённые правила через симлинк в /usr/local/bin
    if command -v apply-iptables.sh &>/dev/null; then
        apply-iptables.sh
    fi
else
    echo "❌ Ошибка загрузки списка IP"
    rm -f "${GEOIP_FILE}.new"
    log_error "Ошибка загрузки GeoIP"
    exit 1
fi

# Статистика
if [ -f "${GEOIP_FILE}.backup" ]; then
    old_count=$(grep -v '^#' "${GEOIP_FILE}.backup" | wc -l)
    new_count=$(grep -v '^#' "$GEOIP_FILE" | wc -l)
    echo ""
    echo "📊 Статистика:"
    echo "   Было: $old_count диапазонов"
    echo "   Стало: $new_count диапазонов"
    echo "   Изменение: $((new_count - old_count)) диапазонов"
fi
