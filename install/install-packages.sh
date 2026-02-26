#!/bin/bash
#===============================================================================
# Server Monitor - Package Installation Script
# Устанавливает необходимые системные пакеты
#===============================================================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверка root
if [[ $EUID -ne 0 ]]; then
    log_error "Скрипт должен быть запущен от root"
    exit 1
fi

echo ""
echo "=========================================="
echo "  Установка пакетов для Server Monitor"
echo "=========================================="
echo ""

# Обновление списка пакетов
log_info "Обновление списка пакетов..."
apt-get update -qq

# Основные пакеты для работы Server Monitor
PACKAGES=(
    # Сеть и безопасность
    "fail2ban"
    "iperf3"
    "iptables"
    "iptables-persistent"
    "netfilter-persistent"
    "ipset"
    "net-tools"
    "tcpdump"
    "whois"
    "socat"
    # Утилиты
    "curl"
    "wget"
    "jq"
    "git"
    "mc"
    "tree"
    "unzip"
    "htop"
    "bc"
    # GeoIP
    "geoip-bin"
    "geoip-database"
    # Мониторинг
    "monit"
    "sysstat"
    # Python
    "python3-full"
    "python3-venv"
    "python3-pip"
    # Дополнительно
    "sqlite3"
)

# Установка пакетов
log_info "Установка пакетов..."
for pkg in "${PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii.*$pkg "; then
        log_success "$pkg уже установлен"
    else
        log_info "Установка $pkg..."
        apt-get install -y -qq "$pkg"
        log_success "$pkg установлен"
    fi
done

echo ""
log_success "Все пакеты установлены"
echo ""

# Проверка версий ключевых пакетов
echo "Установленные версии:"
echo "  Python: $(python3 --version 2>&1 | cut -d' ' -f2)"
echo "  fail2ban: $(fail2ban-client --version 2>&1 | head -1)"
echo "  iperf3: $(iperf3 --version 2>&1 | head -1 | awk '{print $2}')"
echo "  monit: $(monit --version 2>&1 | head -1 | awk '{print $2}')"
echo ""

log_success "Установка завершена"
