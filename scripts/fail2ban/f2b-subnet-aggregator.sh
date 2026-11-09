#!/bin/bash
# /opt/server-monitor/scripts/fail2ban/f2b-subnet-aggregator.sh
# Агрегация подсетей атакующих IP
# Использует централизованную конфигурацию

source /usr/local/lib/server-monitor/load-config.sh
load_common_vars

THRESHOLD=$(get_setting "fail2ban.subnet_threshold" "5")
BANTIME=$(get_setting "fail2ban.subnet_bantime" "86400")
IPSET_NAME="f2b-banned-subnets"
LOG=$(get_path "logs.f2b_subnet" "/var/log/f2b-subnet-aggregator.log")

# Создаём ipset
ipset list "$IPSET_NAME" &>/dev/null || \
    ipset create "$IPSET_NAME" hash:net timeout "$BANTIME" maxelem 65536

# Правило iptables
iptables -C INPUT -m set --match-set "$IPSET_NAME" src -j DROP 2>/dev/null || \
    iptables -I INPUT 1 -m set --match-set "$IPSET_NAME" src -j DROP

# Получаем забаненные IP
BANNED_IPS=$(fail2ban-client status sshd 2>/dev/null | grep "Banned IP" | sed 's/.*://;s/^ *//')
BANNED_IPS+=" $(fail2ban-client status sshd-invalid-user 2>/dev/null | grep "Banned IP" | sed 's/.*://;s/^ *//')"

# Анализируем лог за последние 24 часа
RECENT_ATTACKERS=$(journalctl -u ssh --since "24 hours ago" --no-pager 2>/dev/null | \
    grep -oP 'from \K[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | sort -u)

ALL_IPS=$(echo "$BANNED_IPS $RECENT_ATTACKERS" | tr ' ' '\n' | sort -u | grep -v '^$')

# Агрегируем по /24
echo "$ALL_IPS" | \
    awk -F. '{print $1"."$2"."$3".0/24"}' | \
    sort | uniq -c | sort -rn | \
    while read count subnet; do
        if [ "$count" -ge "$THRESHOLD" ]; then
            # Проверяем белый список
            if ! echo "$subnet" | grep -qE '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)'; then
                if ! ipset test "$IPSET_NAME" "$subnet" 2>/dev/null; then
                    ipset add "$IPSET_NAME" "$subnet" timeout "$BANTIME"
                    echo "$(date '+%Y-%m-%d %H:%M:%S') BANNED SUBNET: $subnet ($count IPs)" >> "$LOG"
                    log_warning "Banned subnet $subnet with $count attacking IPs"
                fi
            fi
        fi
    done

log_info "Subnet aggregation completed"
