#!/bin/bash
# /usr/local/bin/init-server-monitor-config.sh
# Инициализация конфигурационных файлов для server-monitor

set -euo pipefail

CONFIG_DIR="/root/.config/server-monitor"
SETTINGS_FILE="$CONFIG_DIR/settings.json"
SECRETS_FILE="$CONFIG_DIR/secrets.json"
PATHS_FILE="$CONFIG_DIR/paths.json"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "╔══════════════════════════════════════════════╗"
echo "║   Инициализация конфигурации Server Monitor  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Создаём директорию
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

# Проверяем существование файлов
if [ -f "$SETTINGS_FILE" ] || [ -f "$SECRETS_FILE" ] || [ -f "$PATHS_FILE" ]; then
    echo -e "${YELLOW}⚠️  Конфигурационные файлы уже существуют!${NC}"
    echo ""
    read -p "Перезаписать? (yes/no): " OVERWRITE
    if [ "$OVERWRITE" != "yes" ]; then
        echo "Операция отменена."
        exit 0
    fi
    echo ""
fi

# Создаём settings.json
cat > "$SETTINGS_FILE" << 'EOF'
{
  "monitoring": {
    "check_interval": 180,
    "thresholds": {
      "cpu": 80,
      "ram": 90,
      "disk": 95,
      "swap": 80
    },
    "ssh_monitor": {
      "enabled": true,
      "alert_window": 60,
      "max_alerts_per_ip": 3
    },
    "port_monitor": {
      "enabled": true,
      "check_interval": 30
    }
  },
  "fail2ban": {
    "subnet_threshold": 5,
    "subnet_bantime": 86400,
    "alert_anomaly_threshold": 50,
    "daily_report_time": "08:00"
  },
  "network_stats": {
    "collection_interval": 3600,
    "retention": {
      "daily": 7,
      "weekly": 4,
      "monthly": 12,
      "yearly": 5
    }
  },
  "geoip": {
    "country_code": "ru",
    "update_schedule": "weekly",
    "source": "ipverse"
  },
  "speedtest": {
    "server_update_interval": 86400,
    "test_duration": 3,
    "max_attempts": 5
  }
}
EOF

# Создаём secrets.json (пустой шаблон)
cat > "$SECRETS_FILE" << 'EOF'
{
  "telegram": {
    "admin_bot_token": "ЗАМЕНИТЕ_НА_ВАШ_ТОКЕН_ADMIN_БОТА",
    "monitor_bot_token": "ЗАМЕНИТЕ_НА_ВАШ_ТОКЕН_MONITOR_БОТА",
    "chat_id": 0
  }
}
EOF

chmod 600 "$SECRETS_FILE"

# Создаём paths.json
cat > "$PATHS_FILE" << 'EOF'
{
  "config": {
    "base_dir": "/root/.config/server-monitor",
    "settings": "/root/.config/server-monitor/settings.json",
    "secrets": "/root/.config/server-monitor/secrets.json",
    "paths": "/root/.config/server-monitor/paths.json"
  },
  "data": {
    "network_stats_dir": "/var/lib/network-stats",
    "network_stats_file": "/var/lib/network-stats/stats.json",
    "prev_counters": "/var/lib/network-stats/prev_counters.json",
    "geoip_dir": "/root/geoip",
    "geoip_ru_zone": "/root/geoip/ru.zone",
    "iperf_servers": "/etc/iperf3-servers.txt",
    "iperf_working": "/etc/iperf3-working.txt",
    "docker_ports": "/etc/docker-monitor-ports.conf"
  },
  "logs": {
    "base_dir": "/var/log/server-monitor",
    "fail2ban": "/var/log/fail2ban.log",
    "f2b_subnet": "/var/log/f2b-subnet-aggregator.log",
    "f2b_anomaly": "/var/log/f2b-anomaly.log",
    "f2b_telegram": "/var/log/f2b-telegram.log",
    "iperf_update": "/var/log/iperf3-update.log",
    "geoip_update": "/var/log/geoip-update.log",
    "monitoring": "/var/log/server-monitor/monitor.log",
    "admin_bot": "/var/log/server-monitor/admin-bot.log"
  },
  "scripts": {
    "bin_dir": "/usr/local/bin",
    "lib_dir": "/usr/local/lib/server-monitor"
  },
  "python": {
    "admin_bot_dir": "/root/telegram-bot",
    "admin_bot_venv": "/root/telegram-bot/venv",
    "monitor_bot_dir": "/root/monitoring/telemonitor",
    "monitor_bot_venv": "/root/monitoring/telemonitor/venv"
  },
  "temp": {
    "base_dir": "/tmp/server-monitor"
  }
}
EOF

# Создаём недостающие директории
mkdir -p /var/log/server-monitor
mkdir -p /usr/local/lib/server-monitor
mkdir -p /tmp/server-monitor
mkdir -p /var/lib/network-stats
mkdir -p /root/monitoring/telemonitor

echo -e "${GREEN}✅ Конфигурационные файлы созданы:${NC}"
echo "   📄 $SETTINGS_FILE"
echo "   🔒 $SECRETS_FILE (mode 600)"
echo "   📂 $PATHS_FILE"
echo ""
echo -e "${YELLOW}⚠️  ВАЖНО: Отредактируйте secrets.json и укажите ваши токены!${NC}"
echo ""
echo "   nano $SECRETS_FILE"
echo ""
