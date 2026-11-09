#!/bin/bash
# /opt/server-monitor/scripts/network/check-ip-in-lists.sh
# Проверка IP в списках России

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

GEOIP_FILE=$(get_path "data.geoip_ru_zone" "/opt/server-monitor/data/geoip/ru.zone")
IPVERSE_FILE="/tmp/ru-ipverse.txt"

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Функция проверки IP в файле
check_ip() {
    local ip=$1
    local file=$2
    local name=$3
    
    # Конвертируем IP в число для сравнения
    ip_num=$(echo $ip | awk -F. '{print ($1*256**3) + ($2*256**2) + ($3*256) + $4}')
    
    while read cidr; do
        # Пропускаем комментарии
        [[ "$cidr" =~ ^#.*$ ]] && continue
        [[ -z "$cidr" ]] && continue
        
        # Парсим CIDR
        base=${cidr%/*}
        mask=${cidr#*/}
        
        # Конвертируем базовый IP в число
        base_num=$(echo $base | awk -F. '{print ($1*256**3) + ($2*256**2) + ($3*256) + $4}')
        
        # Вычисляем диапазон
        size=$((2**(32-mask)))
        start=$base_num
        end=$((base_num + size - 1))
        
        if [ $ip_num -ge $start ] && [ $ip_num -le $end ]; then
            echo -e "${GREEN}✅ $ip найден в $name: $cidr${NC}"
            return 0
        fi
    done < "$file"
    
    echo -e "${RED}❌ $ip НЕ найден в $name${NC}"
    return 1
}

# Основная логика
echo "╔═══════════════════════════════════════════╗"
echo "║     🔍 ПРОВЕРКА IP В СПИСКАХ РОССИИ      ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Проверяем наличие файлов
if [ ! -f "$GEOIP_FILE" ]; then
    echo "❌ Файл GeoIP не найден: $GEOIP_FILE"
    exit 1
fi

# Скачиваем свежий список IPverse
echo "📥 Загрузка списка IPverse..."
curl -s -o "$IPVERSE_FILE" "https://raw.githubusercontent.com/ipverse/rir-ip/master/country/ru/ipv4-aggregated.txt"

if [ ! -f "$IPVERSE_FILE" ] || [ ! -s "$IPVERSE_FILE" ]; then
    echo "❌ Не удалось загрузить IPverse"
    exit 1
fi

# Очищаем файлы от комментариев для быстрого поиска
grep -v '^#' "$GEOIP_FILE" | grep -v '^$' > /tmp/geoip-clean.txt
grep -v '^#' "$IPVERSE_FILE" | grep -v '^$' > /tmp/ipverse-clean.txt

# ============================================
# Проверка whitelist IP из settings.json
# ============================================
echo "═══════════════════════════════════════════"
echo "📋 Проверка whitelist IP (из settings.json):"
echo "═══════════════════════════════════════════"

WHITELIST_IPS=$(get_setting "geoip.whitelist_ips")
if [ -n "$WHITELIST_IPS" ] && [ "$WHITELIST_IPS" != "null" ]; then
    echo "$WHITELIST_IPS" | jq -r '.[]' 2>/dev/null | while read -r ip; do
        # Пропускаем CIDR-диапазоны (только одиночные IP)
        if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo ""
            echo "🌐 Проверка IP: $ip"
            check_ip "$ip" "/tmp/geoip-clean.txt" "GeoIP"
            check_ip "$ip" "/tmp/ipverse-clean.txt" "IPverse"
        fi
    done
else
    echo "⚠️ whitelist_ips не настроен в settings.json"
fi

# Проверка whitelist доменов
echo ""
echo "═══════════════════════════════════════════"
echo "📋 Проверка whitelist доменов:"
echo "═══════════════════════════════════════════"

WHITELIST_DOMAINS=$(get_setting "geoip.whitelist_domains")
if [ -n "$WHITELIST_DOMAINS" ] && [ "$WHITELIST_DOMAINS" != "null" ]; then
    echo "$WHITELIST_DOMAINS" | jq -r '.[]' 2>/dev/null | while read -r domain; do
        if [ -n "$domain" ]; then
            resolved_ip=$(dig +short "$domain" A | head -1)
            if [ -n "$resolved_ip" ]; then
                echo ""
                echo "🌐 Проверка домена: $domain → $resolved_ip"
                check_ip "$resolved_ip" "/tmp/geoip-clean.txt" "GeoIP"
                check_ip "$resolved_ip" "/tmp/ipverse-clean.txt" "IPverse"
            else
                echo "⚠️ Не удалось резолвить: $domain"
            fi
        fi
    done
else
    echo "⚠️ whitelist_domains не настроен в settings.json"
fi

# ============================================
# Проверка топ-10 атакующих за 24 часа
# ============================================
echo ""
echo "═══════════════════════════════════════════"
echo "🔄 Топ-10 атакующих (24h):"
echo "═══════════════════════════════════════════"

TOP_ATTACKERS=$(journalctl -u ssh --since "24 hours ago" --no-pager 2>/dev/null | \
    grep "Failed password" | grep -oP 'from \K[0-9.]+' | sort | uniq -c | sort -rn | head -10 | awk '{print $2}')

if [ -n "$TOP_ATTACKERS" ]; then
    for ip in $TOP_ATTACKERS; do
        result_geoip="❌"
        result_ipverse="❌"
        
        ip_num=$(echo $ip | awk -F. '{print ($1*256**3) + ($2*256**2) + ($3*256) + $4}')
        
        # Проверка в GeoIP
        while read cidr; do
            base=${cidr%/*}
            mask=${cidr#*/}
            base_num=$(echo $base | awk -F. '{print ($1*256**3) + ($2*256**2) + ($3*256) + $4}')
            size=$((2**(32-mask)))
            end=$((base_num + size - 1))
            
            if [ $ip_num -ge $base_num ] && [ $ip_num -le $end ]; then
                result_geoip="✅"
                break
            fi
        done < /tmp/geoip-clean.txt
        
        # Проверка в IPverse
        while read cidr; do
            base=${cidr%/*}
            mask=${cidr#*/}
            base_num=$(echo $base | awk -F. '{print ($1*256**3) + ($2*256**2) + ($3*256) + $4}')
            size=$((2**(32-mask)))
            end=$((base_num + size - 1))
            
            if [ $ip_num -ge $base_num ] && [ $ip_num -le $end ]; then
                result_ipverse="✅"
                break
            fi
        done < /tmp/ipverse-clean.txt
        
        printf "   %-15s | GeoIP: %s | IPverse: %s\n" "$ip" "$result_geoip" "$result_ipverse"
    done
else
    echo "   Нет данных об атаках за последние 24 часа"
fi

echo ""
echo "📊 Статистика по файлам:"
echo "   GeoIP:   $(wc -l < /tmp/geoip-clean.txt) диапазонов"
echo "   IPverse: $(wc -l < /tmp/ipverse-clean.txt) диапазонов"

# Очистка
rm -f /tmp/geoip-clean.txt /tmp/ipverse-clean.txt
