#!/bin/bash
# /opt/server-monitor/scripts/geoip/apply-iptables.sh
# Применение правил геоблокировки

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

# Загружаем пути
GEOIP_FILE=$(get_path "data.geoip_ru_zone" "/opt/server-monitor/data/geoip/ru.zone")

log_info "Применение правил геоблокировки"

# Проверяем наличие файла
if [ ! -f "$GEOIP_FILE" ]; then
    echo "❌ Ошибка: файл $GEOIP_FILE не найден!"
    log_error "Файл GeoIP не найден: $GEOIP_FILE"
    exit 1
fi

# Очищаем старую цепочку
iptables -F geo-block 2>/dev/null
iptables -D INPUT -p tcp --dport 22 -j geo-block 2>/dev/null
iptables -X geo-block 2>/dev/null

# Создаём новую цепочку
iptables -N geo-block

# ============================================
# WHITELIST: Приоритетные IP/домены
# ============================================

echo "🔓 Добавление whitelist IP..."

# Читаем whitelist_ips из конфига
WHITELIST_IPS=$(get_setting "geoip.whitelist_ips")
if [ -n "$WHITELIST_IPS" ] && [ "$WHITELIST_IPS" != "null" ]; then
    echo "$WHITELIST_IPS" | jq -r '.[]' 2>/dev/null | while read -r ip; do
        if [ -n "$ip" ]; then
            iptables -A geo-block -s "$ip" -j ACCEPT
            echo "  ✅ Whitelist IP: $ip"
        fi
    done
fi

# Читаем whitelist_domains из конфига
WHITELIST_DOMAINS=$(get_setting "geoip.whitelist_domains")
if [ -n "$WHITELIST_DOMAINS" ] && [ "$WHITELIST_DOMAINS" != "null" ]; then
    echo "$WHITELIST_DOMAINS" | jq -r '.[]' 2>/dev/null | while read -r domain; do
        if [ -n "$domain" ]; then
            # Резолвим домен в IP
            resolved_ip=$(dig +short "$domain" A | head -1)
            
            if [ -n "$resolved_ip" ]; then
                iptables -A geo-block -s "$resolved_ip" -j ACCEPT
                echo "  ✅ Whitelist domain: $domain → $resolved_ip"
                log_info "Whitelist: $domain → $resolved_ip"
            else
                echo "  ⚠️  Не удалось резолвить: $domain"
                log_warning "Не удалось резолвить домен: $domain"
            fi
        fi
    done
fi

# ============================================
# GEOIP: Российские IP
# ============================================

echo "🇷🇺 Добавление IP России..."

# Счётчик
COUNT=0

# Добавляем правила
while IFS= read -r ip; do
    [[ -z "$ip" || "$ip" =~ ^# ]] && continue

    iptables -A geo-block -s "$ip" -j ACCEPT
    COUNT=$((COUNT + 1))

    if [ $((COUNT % 1000)) -eq 0 ]; then
        echo "Добавлено $COUNT правил..."
    fi
done < "$GEOIP_FILE"

echo "✅ Добавлено $COUNT правил для IP России"

# Разрешаем localhost
iptables -A geo-block -s 127.0.0.0/8 -j ACCEPT

# Блокируем остальные
iptables -A geo-block -j LOG --log-prefix "GEO-BLOCK: " --log-level 4
iptables -A geo-block -j DROP

# Применяем к SSH
iptables -I INPUT -p tcp --dport 22 -j geo-block

echo "✅ Правила geo-block применены к порту 22"

# Сохраняем
if command -v netfilter-persistent &>/dev/null; then
    netfilter-persistent save
    echo "✅ Правила сохранены"
fi

log_info "Геоблокировка применена: $COUNT правил + whitelist"
