#!/bin/bash
# /opt/server-monitor/scripts/network/collect-network-stats.sh
# Сбор сетевой статистики с правильным расчётом дельт
# Использует централизованную конфигурацию

set -euo pipefail

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

# Загружаем пути из конфигурации
STATS_DIR=$(get_path "data.network_stats_dir" "/opt/server-monitor/data")
STATS_FILE=$(get_path "data.network_stats_file" "/opt/server-monitor/data/stats.json")
PREV_COUNTERS_FILE=$(get_path "data.prev_counters" "/opt/server-monitor/data/prev_counters.json")

TEMP_FILE="$STATS_DIR/temp_$$.json"
LOCK_FILE="$STATS_DIR/stats.lock"

# Настройки из конфига
RETENTION_DAILY=$(get_setting "network_stats.retention.daily" "7")
RETENTION_WEEKLY=$(get_setting "network_stats.retention.weekly" "4")
RETENTION_MONTHLY=$(get_setting "network_stats.retention.monthly" "12")
RETENTION_YEARLY=$(get_setting "network_stats.retention.yearly" "5")

mkdir -p "$STATS_DIR"

# Блокировка
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "Другой экземпляр уже запущен"; exit 1; }

cleanup() {
    rm -f "$TEMP_FILE"
    flock -u 200 2>/dev/null || true
}
trap cleanup EXIT

# ============================================
# ФУНКЦИИ
# ============================================

get_current_counters() {
    local result="{"
    local first=1
    
    for iface in /sys/class/net/*; do
        local iface_name=$(basename "$iface")
        if [[ "$iface_name" == "lo" ]] || [[ "$iface_name" =~ ^veth ]]; then
            continue
        fi
        
        local rx=$(cat "$iface/statistics/rx_bytes" 2>/dev/null || echo 0)
        local tx=$(cat "$iface/statistics/tx_bytes" 2>/dev/null || echo 0)
        
        [[ $first -eq 0 ]] && result="$result,"
        first=0
        result="$result\"$iface_name\":{\"rx\":$rx,\"tx\":$tx}"
    done
    
    result="$result}"
    echo "$result"
}

calculate_delta() {
    local current="$1"
    local previous="$2"
    
    if [[ -z "$previous" ]] || [[ "$previous" == "null" ]] || [[ "$previous" == "{}" ]]; then
        echo "$current" | jq 'with_entries(.value = {rx: 0, tx: 0})'
        return
    fi
    
    jq -n --argjson curr "$current" --argjson prev "$previous" '
        $curr | to_entries | map(
            .key as $iface |
            .value as $curr_val |
            ($prev[$iface] // {rx: 0, tx: 0}) as $prev_val |
            (if $curr_val.rx >= $prev_val.rx then $curr_val.rx - $prev_val.rx else $curr_val.rx end) as $delta_rx |
            (if $curr_val.tx >= $prev_val.tx then $curr_val.tx - $prev_val.tx else $curr_val.tx end) as $delta_tx |
            {key: $iface, value: {rx: $delta_rx, tx: $delta_tx}}
        ) | from_entries |
        . + {total: {
            rx: ([.[].rx] | add // 0),
            tx: ([.[].tx] | add // 0)
        }}
    '
}

add_delta_to_period() {
    local existing="$1"
    local delta="$2"
    
    if [[ -z "$existing" ]] || [[ "$existing" == "null" ]] || [[ "$existing" == "{}" ]]; then
        echo "$delta"
        return
    fi
    
    jq -n --argjson exist "$existing" --argjson delta "$delta" '
        ($exist | keys) + ($delta | keys) | unique | map(
            . as $iface |
            {
                key: $iface,
                value: {
                    rx: (($exist[$iface].rx // 0) + ($delta[$iface].rx // 0)),
                    tx: (($exist[$iface].tx // 0) + ($delta[$iface].tx // 0))
                }
            }
        ) | from_entries
    '
}

# ============================================
# ОСНОВНАЯ ЛОГИКА
# ============================================

NOW=$(date '+%Y-%m-%d %H:%M:%S')
CURRENT_DATE=$(date '+%Y-%m-%d')
CURRENT_WEEK=$(date '+%G-W%V')
CURRENT_MONTH=$(date '+%Y-%m')
CURRENT_YEAR=$(date '+%Y')

CURRENT_COUNTERS=$(get_current_counters)

if [[ -f "$PREV_COUNTERS_FILE" ]]; then
    PREV_COUNTERS=$(cat "$PREV_COUNTERS_FILE")
    PREV_DATE=$(echo "$PREV_COUNTERS" | jq -r '.date // empty')
    PREV_COUNTERS_DATA=$(echo "$PREV_COUNTERS" | jq -c '.counters // {}')
else
    PREV_COUNTERS_DATA="{}"
    PREV_DATE=""
fi

DELTA=$(calculate_delta "$CURRENT_COUNTERS" "$PREV_COUNTERS_DATA")

if [[ ! -f "$STATS_FILE" ]]; then
    cat > "$STATS_FILE" << INITEOF
{
    "daily": {},
    "weekly": {},
    "monthly": {},
    "yearly": {},
    "last_update": "$NOW"
}
INITEOF
fi

# Читаем текущую статистику
STATS=$(cat "$STATS_FILE")

# Обновляем периоды
DAILY_DATA=$(echo "$STATS" | jq -c --arg date "$CURRENT_DATE" '.daily[$date] // {}')
DAILY_UPDATED=$(add_delta_to_period "$DAILY_DATA" "$DELTA")
STATS=$(echo "$STATS" | jq --arg date "$CURRENT_DATE" --argjson data "$DAILY_UPDATED" '.daily[$date] = $data')

WEEKLY_DATA=$(echo "$STATS" | jq -c --arg week "$CURRENT_WEEK" '.weekly[$week] // {}')
WEEKLY_UPDATED=$(add_delta_to_period "$WEEKLY_DATA" "$DELTA")
STATS=$(echo "$STATS" | jq --arg week "$CURRENT_WEEK" --argjson data "$WEEKLY_UPDATED" '.weekly[$week] = $data')

MONTHLY_DATA=$(echo "$STATS" | jq -c --arg month "$CURRENT_MONTH" '.monthly[$month] // {}')
MONTHLY_UPDATED=$(add_delta_to_period "$MONTHLY_DATA" "$DELTA")
STATS=$(echo "$STATS" | jq --arg month "$CURRENT_MONTH" --argjson data "$MONTHLY_UPDATED" '.monthly[$month] = $data')

YEARLY_DATA=$(echo "$STATS" | jq -c --arg year "$CURRENT_YEAR" '.yearly[$year] // {}')
YEARLY_UPDATED=$(add_delta_to_period "$YEARLY_DATA" "$DELTA")
STATS=$(echo "$STATS" | jq --arg year "$CURRENT_YEAR" --argjson data "$YEARLY_UPDATED" '.yearly[$year] = $data')

# Очистка старых данных с использованием настроек из конфига
STATS=$(echo "$STATS" | jq --argjson d "$RETENTION_DAILY" --argjson w "$RETENTION_WEEKLY" \
    --argjson m "$RETENTION_MONTHLY" --argjson y "$RETENTION_YEARLY" '
    .daily = (.daily | to_entries | sort_by(.key) | reverse | .[0:$d] | from_entries) |
    .weekly = (.weekly | to_entries | sort_by(.key) | reverse | .[0:$w] | from_entries) |
    .monthly = (.monthly | to_entries | sort_by(.key) | reverse | .[0:$m] | from_entries) |
    .yearly = (.yearly | to_entries | sort_by(.key) | reverse | .[0:$y] | from_entries)
')

STATS=$(echo "$STATS" | jq --arg now "$NOW" '.last_update = $now')

# Сохранение
echo "$STATS" | jq '.' > "$TEMP_FILE"
mv "$TEMP_FILE" "$STATS_FILE"

jq -n --argjson counters "$CURRENT_COUNTERS" --arg date "$CURRENT_DATE" \
    '{counters: $counters, date: $date}' > "$PREV_COUNTERS_FILE"

# Вывод
echo "Статистика обновлена: $NOW"
echo ""
echo "Дельта с последнего замера:"
echo "$DELTA" | jq -r '
    to_entries[] | 
    "\(.key): 📥 \(.value.rx / 1048576 | floor) MB | 📤 \(.value.tx / 1048576 | floor) MB"
'
