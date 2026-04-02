#!/bin/bash
#===============================================================================
# Server Monitor - System Configs Installation Script
# Устанавливает конфигурационные файлы для fail2ban, iperf3, monit
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

INSTALL_DIR="/opt/server-monitor"
CONFIG_SRC="$INSTALL_DIR/config/system"
BIN_DIR="/usr/local/bin"

echo ""
echo "=========================================="
echo "  Установка конфигурационных файлов"
echo "=========================================="
echo ""

#-------------------------------------------------------------------------------
# Fail2ban
#-------------------------------------------------------------------------------
install_fail2ban_configs() {
    log_info "Установка конфигов fail2ban..."

    # Создаём резервные копии
    if [[ -f /etc/fail2ban/jail.local ]]; then
        cp /etc/fail2ban/jail.local /etc/fail2ban/jail.local.backup.$(date +%Y%m%d_%H%M%S)
    fi

    if [[ -f /etc/fail2ban/fail2ban.local ]]; then
        cp /etc/fail2ban/fail2ban.local /etc/fail2ban/fail2ban.local.backup.$(date +%Y%m%d_%H%M%S)
    fi

    # Копируем основные конфиги
    cp "$CONFIG_SRC/fail2ban/jail.local" /etc/fail2ban/
    cp "$CONFIG_SRC/fail2ban/fail2ban.local" /etc/fail2ban/

    # Копируем jail.d
    cp "$CONFIG_SRC/fail2ban/jail.d/"*.local /etc/fail2ban/jail.d/

    # Копируем filters
    cp "$CONFIG_SRC/fail2ban/filter.d/"*.conf /etc/fail2ban/filter.d/

    # Копируем actions
    cp "$CONFIG_SRC/fail2ban/action.d/"*.conf /etc/fail2ban/action.d/

    # Создаём директорию для скриптов
    mkdir -p /etc/fail2ban/scripts

    # Копируем скрипт telegram
    cp "$CONFIG_SRC/fail2ban/scripts/fail2ban-telegram.sh" /etc/fail2ban/scripts/
    chmod +x /etc/fail2ban/scripts/fail2ban-telegram.sh

    # Копируем cron задачи для fail2ban
    if [[ -d "$CONFIG_SRC/fail2ban/cron.d" ]]; then
        cp "$CONFIG_SRC/fail2ban/cron.d/"* /etc/cron.d/
        log_info "Cron задачи fail2ban установлены"
    fi

    log_success "Конфиги fail2ban установлены"
}

#-------------------------------------------------------------------------------
# ipset (зависимость для fail2ban с ipset)
#-------------------------------------------------------------------------------
install_ipset() {
    log_info "Проверка ipset..."
    
    if ! command -v ipset &> /dev/null; then
        log_info "Установка ipset..."
        apt-get install -y ipset > /dev/null 2>&1
        log_success "ipset установлен"
    else
        log_success "ipset уже установлен"
    fi
}

#-------------------------------------------------------------------------------
# iperf3
#-------------------------------------------------------------------------------
install_iperf3_configs() {
    log_info "Установка конфигов iperf3..."

    cp "$CONFIG_SRC/iperf3/iperf3-servers.txt" /etc/
    cp "$CONFIG_SRC/iperf3/iperf3-working.txt" /etc/

    log_success "Конфиги iperf3 установлены"
}

#-------------------------------------------------------------------------------
# monit
#-------------------------------------------------------------------------------
install_monit_configs() {
    log_info "Установка конфигов monit..."

    # Создаём резервную копию monitrc
    if [[ -f /etc/monit/monitrc ]]; then
        cp /etc/monit/monitrc /etc/monit/monitrc.backup.$(date +%Y%m%d_%H%M%S)
    fi

    # Копируем основной конфиг
    cp "$CONFIG_SRC/monit/monitrc" /etc/monit/
    chmod 600 /etc/monit/monitrc

    # Создаём директорию conf-enabled если не существует
    mkdir -p /etc/monit/conf-enabled

    # Резервная копия текущих конфигов
    if [[ -d /etc/monit/conf-enabled ]] && [[ "$(ls -A /etc/monit/conf-enabled 2>/dev/null)" ]]; then
        local backup_dir="/etc/monit/conf-enabled.backup.$(date +%Y%m%d_%H%M%S)"
        cp -r /etc/monit/conf-enabled "$backup_dir"
        log_info "Резервная копия conf-enabled создана: $backup_dir"
    fi

    # Очищаем и копируем новые конфиги
    rm -f /etc/monit/conf-enabled/*
    cp "$CONFIG_SRC/monit/conf-enabled/"* /etc/monit/conf-enabled/

    log_success "Конфиги monit установлены"
}

#-------------------------------------------------------------------------------
# monit-alert.sh симлинк
#-------------------------------------------------------------------------------
install_monit_script() {
    log_info "Установка скрипта monit-alert.sh..."

    # Удаляем старый симлинк если есть
    rm -f "$BIN_DIR/monit-alert.sh"
    rm -f "$BIN_DIR/monit-telegram.sh"

    # Создаём симлинк на новый скрипт
    if [[ -f "$INSTALL_DIR/scripts/system/monit-alert.sh" ]]; then
        ln -s "$INSTALL_DIR/scripts/system/monit-alert.sh" "$BIN_DIR/monit-alert.sh"
        chmod +x "$INSTALL_DIR/scripts/system/monit-alert.sh"
        log_success "Симлинк monit-alert.sh создан"
    else
        log_error "Файл monit-alert.sh не найден в $INSTALL_DIR/scripts/system/"
    fi
}

#-------------------------------------------------------------------------------
# Главная функция
#-------------------------------------------------------------------------------
main() {
    # Проверяем наличие исходных конфигов
    if [[ ! -d "$CONFIG_SRC" ]]; then
        log_error "Директория с конфигами не найдена: $CONFIG_SRC"
        exit 1
    fi

    install_ipset
    install_fail2ban_configs
    install_iperf3_configs
    install_monit_configs
    install_monit_script

    echo ""
    echo "=========================================="
    log_success "Конфигурационные файлы установлены"
    echo "=========================================="
    echo ""
    echo "Для применения изменений выполните:"
    echo "  systemctl restart fail2ban"
    echo "  systemctl restart monit"
    echo ""
}

main "$@"
