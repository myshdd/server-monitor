#!/bin/bash
# /usr/local/bin/check-ip-in-lists.sh - Проверка IP в обоих списках

IPDENY_FILE="/root/geoip/ru.zone"
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
echo "╔══════════════════════════════════════════════╗"
echo "║     🔍 ПРОВЕРКА IP В СПИСКАХ РОССИИ         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Проверяем наличие файлов
if [ ! -f "$IPDENY_FILE" ]; then
    echo "❌ Файл IPdeny не найден: $IPDENY_FILE"
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
grep -v '^#' "$IPDENY_FILE" | grep -v '^$' > /tmp/ipdeny-clean.txt
grep -v '^#' "$IPVERSE_FILE" | grep -v '^$' > /tmp/ipverse-clean.txt

# Массив IP для проверки
IPS=(
    "91.103.211.70"
    "89.188.96.18"
)

# Проверяем каждый IP
for ip in "${IPS[@]}"; do
    echo "══════════════════════════════════════════════"
    echo "🌐 Проверка IP: $ip"
    echo "══════════════════════════════════════════════"
    
    check_ip "$ip" "/tmp/ipdeny-clean.txt" "IPdeny"
    check_ip "$ip" "/tmp/ipverse-clean.txt" "IPverse"
    echo ""
done

# Также проверим несколько случайных IP из топ-атакующих
echo "══════════════════════════════════════════════"
echo "🔄 Дополнительная проверка (топ атакующие):"
echo "══════════════════════════════════════════════"

ATTACKERS=(
    "176.120.22.13"
    "176.120.22.47"
    "91.202.233.33"
    "103.53.231.159"
    "95.221.43.254"
)

for ip in "${ATTACKERS[@]}"; do
    result_ipdeny="?"
    result_ipverse="?"
    
    ip_num=$(echo $ip | awk -F. '{print ($1*256**3) + ($2*256**2) + ($3*256) + $4}')
    
    # Проверка в IPdeny
    while read cidr; do
        base=${cidr%/*}
        mask=${cidr#*/}
        base_num=$(echo $base | awk -F. '{print ($1*256**3) + ($2*256**2) + ($3*256) + $4}')
        size=$((2**(32-mask)))
        end=$((base_num + size - 1))
        
        if [ $ip_num -ge $base_num ] && [ $ip_num -le $end ]; then
            result_ipdeny="✅"
            break
        fi
    done < /tmp/ipdeny-clean.txt
    
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
    
    printf "   %-15s | IPdeny: %s | IPverse: %s\n" "$ip" "$result_ipdeny" "$result_ipverse"
done

echo ""
echo "📊 Статистика по файлам:"
echo "   IPdeny:  $(wc -l < /tmp/ipdeny-clean.txt) диапазонов"
echo "   IPverse: $(wc -l < /tmp/ipverse-clean.txt) диапазонов"

# Очистка
rm -f /tmp/ipdeny-clean.txt /tmp/ipverse-clean.txt
