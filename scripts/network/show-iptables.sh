#!/bin/bash
# /opt/server-monitor/scripts/network/show-iptables.sh
echo "══════════════════════════════════════════════"
echo "📋 ПРАВИЛА IPTABLES (без GEOIP)"
echo "══════════════════════════════════════════════"

# Правила INPUT
echo ""
echo "🔹 INPUT цепочка (без geoip):"
echo "----------------------------------------"
iptables -L INPUT -n -v --line-numbers | grep -v "geo-block" | head -30

# Правила FORWARD
echo ""
echo "🔸 FORWARD цепочка (без geoip):"
echo "----------------------------------------"
iptables -L FORWARD -n -v --line-numbers | head -10

# Сводка по ACCEPT правилам
echo ""
echo "📊 Сводка ACCEPT правил:"
echo "----------------------------------------"
iptables -L INPUT -n -v | grep "ACCEPT" | grep -v "geo-block" | while read line; do
    echo "  $line"
done
