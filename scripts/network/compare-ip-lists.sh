#!/bin/bash
# /usr/local/bin/compare-ip-lists.sh - Сравнение списков IP России

# Файлы для сравнения
IPDENY_FILE="/root/geoip/ru.zone"
IPVERSE_FILE="/tmp/ru-ipverse.txt"
REPORT_FILE="/root/geoip/ip-comparison-report.txt"

# Цвета для вывода (опционально)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для подсчета IP в CIDR
count_ips() {
    local cidr=$1
    # Парсим CIDR
    local base=${cidr%/*}
    local mask=${cidr#*/}
    
    if [[ $mask -ge 32 ]]; then
        echo 1
    else
        echo $((2**(32-mask)))
    fi
}

# Функция для форматирования чисел
format_number() {
    printf "%'d" $1 | sed 's/,/ /g'
}

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        🔍 СРАВНЕНИЕ СПИСКОВ IP АДРЕСОВ РОССИИ             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Проверяем наличие файлов
if [ ! -f "$IPDENY_FILE" ]; then
    echo "❌ Файл ipdeny не найден: $IPDENY_FILE"
    exit 1
fi

# Скачиваем свежий список от ipverse
echo "📥 Загрузка списка от ipverse..."
curl -s -o "$IPVERSE_FILE" "https://raw.githubusercontent.com/ipverse/rir-ip/master/country/ru/ipv4-aggregated.txt"

if [ ! -f "$IPVERSE_FILE" ] || [ ! -s "$IPVERSE_FILE" ]; then
    echo "❌ Не удалось загрузить файл от ipverse"
    exit 1
fi

echo -e "${GREEN}✅ Файлы загружены${NC}\n"

# Очищаем файлы от комментариев и пустых строк
echo "🔧 Обработка файлов..."
grep -v '^#' "$IPDENY_FILE" | grep -v '^$' | sort > /tmp/ipdeny-clean.txt
grep -v '^#' "$IPVERSE_FILE" | grep -v '^$' | sort > /tmp/ipverse-clean.txt

# Подсчет статистики
IPDENY_COUNT=$(wc -l < /tmp/ipdeny-clean.txt)
IPVERSE_COUNT=$(wc -l < /tmp/ipverse-clean.txt)

# Подсчет общего количества IP-адресов
echo "📊 Подсчет общего количества IP-адресов (может занять несколько секунд)..."
TOTAL_IPDENY=0
while read cidr; do
    count=$(count_ips "$cidr")
    TOTAL_IPDENY=$((TOTAL_IPDENY + count))
done < /tmp/ipdeny-clean.txt

TOTAL_IPVERSE=0
while read cidr; do
    count=$(count_ips "$cidr")
    TOTAL_IPVERSE=$((TOTAL_IPVERSE + count))
done < /tmp/ipverse-clean.txt

# Поиск уникальных и общих записей
echo "🔍 Поиск пересечений..."
comm -12 /tmp/ipdeny-clean.txt /tmp/ipverse-clean.txt > /tmp/common.txt
comm -23 /tmp/ipdeny-clean.txt /tmp/ipverse-clean.txt > /tmp/only-ipdeny.txt
comm -13 /tmp/ipdeny-clean.txt /tmp/ipverse-clean.txt > /tmp/only-ipverse.txt

COMMON_COUNT=$(wc -l < /tmp/common.txt)
ONLY_IPDENY_COUNT=$(wc -l < /tmp/only-ipdeny.txt)
ONLY_IPVERSE_COUNT=$(wc -l < /tmp/only-ipverse.txt)

# Подсчет IP в уникальных диапазонах
TOTAL_ONLY_IPDENY=0
while read cidr; do
    count=$(count_ips "$cidr")
    TOTAL_ONLY_IPDENY=$((TOTAL_ONLY_IPDENY + count))
done < /tmp/only-ipdeny.txt

TOTAL_ONLY_IPVERSE=0
while read cidr; do
    count=$(count_ips "$cidr")
    TOTAL_ONLY_IPVERSE=$((TOTAL_ONLY_IPVERSE + count))
done < /tmp/only-ipverse.txt

# Форматируем числа для вывода
F_TOTAL_IPDENY=$(format_number $TOTAL_IPDENY)
F_TOTAL_IPVERSE=$(format_number $TOTAL_IPVERSE)
F_TOTAL_ONLY_IPDENY=$(format_number $TOTAL_ONLY_IPDENY)
F_TOTAL_ONLY_IPVERSE=$(format_number $TOTAL_ONLY_IPVERSE)

# Создаем отчет
{
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║        📊 ОТЧЕТ О СРАВНЕНИИ IP СПИСКОВ РОССИИ             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📅 Дата отчета: $(date '+%d.%m.%Y %H:%M:%S')"
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "📁 ИСТОЧНИКИ:"
    echo "════════════════════════════════════════════════════════════"
    echo "1. IPdeny  : https://www.ipdeny.com/ipblocks/data/countries/ru.zone"
    echo "2. IPverse : https://github.com/ipverse/rir-ip/raw/master/country/ru/ipv4-aggregated.txt"
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "📊 ОБЩАЯ СТАТИСТИКА:"
    echo "════════════════════════════════════════════════════════════"
    printf "   %-20s %10s %15s\n" "Источник" "Диапазоны" "Всего IP"
    printf "   %-20s %'10d %15s\n" "IPdeny" "$IPDENY_COUNT" "$F_TOTAL_IPDENY"
    printf "   %-20s %'10d %15s\n" "IPverse" "$IPVERSE_COUNT" "$F_TOTAL_IPVERSE"
    echo ""
    
    echo "════════════════════════════════════════════════════════════"
    echo "🔄 ПЕРЕСЕЧЕНИЯ:"
    echo "════════════════════════════════════════════════════════════"
    printf "   %-30s %'10d %15s\n" "Общие диапазоны" "$COMMON_COUNT" "-"
    printf "   %-30s %'10d %15s\n" "Только в IPdeny" "$ONLY_IPDENY_COUNT" "$F_TOTAL_ONLY_IPDENY IP"
    printf "   %-30s %'10d %15s\n" "Только в IPverse" "$ONLY_IPVERSE_COUNT" "$F_TOTAL_ONLY_IPVERSE IP"
    echo ""
    
    # Если есть уникальные диапазоны, покажем примеры
    if [ $ONLY_IPDENY_COUNT -gt 0 ]; then
        echo "════════════════════════════════════════════════════════════"
        echo "📌 ПРИМЕРЫ ДИАПАЗОНОВ ТОЛЬКО В IPDENY (первые 10):"
        echo "════════════════════════════════════════════════════════════"
        head -10 /tmp/only-ipdeny.txt | while read cidr; do
            ips=$(count_ips "$cidr")
            printf "   %-20s %'10d IP\n" "$cidr" "$ips"
        done
        echo ""
    fi
    
    if [ $ONLY_IPVERSE_COUNT -gt 0 ]; then
        echo "════════════════════════════════════════════════════════════"
        echo "📌 ПРИМЕРЫ ДИАПАЗОНОВ ТОЛЬКО В IPVERSE (первые 10):"
        echo "════════════════════════════════════════════════════════════"
        head -10 /tmp/only-ipverse.txt | while read cidr; do
            ips=$(count_ips "$cidr")
            printf "   %-20s %'10d IP\n" "$cidr" "$ips"
        done
        echo ""
    fi
    
    echo "════════════════════════════════════════════════════════════"
    echo "📊 ПРОЦЕНТНОЕ СООТНОШЕНИЕ:"
    echo "════════════════════════════════════════════════════════════"
    IPDENY_PERCENT=$((TOTAL_IPDENY * 100 / TOTAL_IPVERSE))
    IPVERSE_PERCENT=$((TOTAL_IPVERSE * 100 / TOTAL_IPDENY))
    COMMON_PERCENT=$((COMMON_COUNT * 100 / IPDENY_COUNT))
    
    printf "   IPdeny составляет %d%% от IPverse по количеству IP\n" "$IPDENY_PERCENT"
    printf "   IPverse составляет %d%% от IPdeny по количеству IP\n" "$IPVERSE_PERCENT"
    printf "   Общих диапазонов: %d%% от IPdeny\n" "$COMMON_PERCENT"
    echo ""
    
    echo "════════════════════════════════════════════════════════════"
    echo "💡 РЕКОМЕНДАЦИИ:"
    echo "════════════════════════════════════════════════════════════"
    
    if [ $TOTAL_ONLY_IPVERSE -gt $TOTAL_ONLY_IPDENY ]; then
        echo "   • IPverse содержит больше уникальных IP ($F_TOTAL_ONLY_IPVERSE vs $F_TOTAL_ONLY_IPDENY)"
        echo "   • Рекомендуется использовать IPverse для более полного охвата"
    elif [ $TOTAL_ONLY_IPDENY -gt $TOTAL_ONLY_IPVERSE ]; then
        echo "   • IPdeny содержит больше уникальных IP ($F_TOTAL_ONLY_IPDENY vs $F_TOTAL_ONLY_IPVERSE)"
        echo "   • Рекомендуется использовать IPdeny для более полного охвата"
    else
        echo "   • Списки примерно равны по охвату"
    fi
    
    if [ $COMMON_COUNT -lt 100 ]; then
        echo "   • ВНИМАНИЕ: Очень мало общих диапазонов! Списи сильно различаются."
        echo "   • Рекомендуется объединить оба списка для максимального охвата"
    fi
    echo ""
    
} | tee "$REPORT_FILE"

# Очистка временных файлов
rm -f /tmp/ipdeny-clean.txt /tmp/ipverse-clean.txt /tmp/common.txt /tmp/only-ipdeny.txt /tmp/only-ipverse.txt

echo -e "${GREEN}✅ Отчет сохранен в: $REPORT_FILE${NC}"
echo ""
