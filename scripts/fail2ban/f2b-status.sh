#!/bin/bash
# /opt/server-monitor/scripts/fail2ban/f2b-status.sh
# Дашборд статуса Fail2ban
# Использует централизованную конфигурацию

# Подключаем библиотеку конфигурации
source /usr/local/lib/server-monitor/load-config.sh

echo "╔══════════════════════════════════════════╗"
echo "║        FAIL2BAN STATUS DASHBOARD         ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Server: $(hostname) | $(date)"
echo "────────────────────────────────────────────"

# Статус каждого jail
for jail in $(fail2ban-client status 2>/dev/null | grep "Jail list" | sed 's/.*://;s/,/ /g'); do
    status=$(fail2ban-client status "$jail" 2>/dev/null)
    currently_banned=$(echo "$status" | grep "Currently banned" | awk '{print $NF}')
    total_banned=$(echo "$status" | grep "Total banned" | awk '{print $NF}')
    currently_failed=$(echo "$status" | grep "Currently failed" | awk '{print $NF}')
    
    printf "%-30s | Banned: %-5s | Total: %-6s | Failed: %s\n" \
        "$jail" "$currently_banned" "$total_banned" "$currently_failed"
done

echo "────────────────────────────────────────────"

# ipset статистика
for setname in f2b-banned-subnets f2b-blocklists; do
    if ipset list "$setname" &>/dev/null; then
        count=$(ipset list "$setname" | grep -c "^[0-9]")
        printf "ipset %-25s | Entries: %s\n" "$setname" "$count"
    fi
done

echo "────────────────────────────────────────────"

# Последние 24 часа статистика
ATTACKS_24H=$(journalctl -u ssh --since "24 hours ago" --no-pager 2>/dev/null | \
    grep -c "Failed password")
UNIQUE_IPS=$(journalctl -u ssh --since "24 hours ago" --no-pager 2>/dev/null | \
    grep "Failed password" | grep -oP 'from \K[0-9.]+' | sort -u | wc -l)

echo "Last 24h: $ATTACKS_24H failed attempts from $UNIQUE_IPS unique IPs"

# Топ-10 атакующих
echo ""
echo "Top 10 attackers (24h):"
journalctl -u ssh --since "24 hours ago" --no-pager 2>/dev/null | \
    grep "Failed password" | grep -oP 'from \K[0-9.]+' | sort | uniq -c | sort -rn | head -10 | \
    while read count ip; do
        country=""
        if command -v geoiplookup &>/dev/null; then
            country=$(geoiplookup "$ip" 2>/dev/null | head -1 | awk -F': ' '{print $2}')
        fi
        printf "  %5d attempts - %-15s %s\n" "$count" "$ip" "$country"
    done

# Топ пробуемых логинов
echo ""
echo "Top 10 targeted usernames (24h):"
journalctl -u ssh --since "24 hours ago" --no-pager 2>/dev/null | \
    grep -oP 'Failed password for (?:invalid user )?\K\S+' | sort | uniq -c | sort -rn | head -10 | \
    while read count user; do
        printf "  %5d attempts - %s\n" "$count" "$user"
    done
