#!/bin/bash
#===============================================================================
# Server Monitor - Full Setup Script
# Полная установка Server Monitor на новый сервер
#===============================================================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# Проверка root
if [[ $EUID -ne 0 ]]; then
    log_error "Скрипт должен быть запущен от root"
    exit 1
fi

INSTALL_DIR="/opt/server-monitor"

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║                                                        ║"
echo "║          SERVER MONITOR - FULL SETUP                   ║"
echo "║                                                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Проверка что репозиторий установлен
if [[ ! -d "$INSTALL_DIR" ]]; then
    log_error "Директория $INSTALL_DIR не найдена"
    log_info "Склонируйте репозиторий в /opt/server-monitor/"
    exit 1
fi

cd "$INSTALL_DIR/install"

echo "Этот скрипт выполнит следующие действия:"
echo ""
echo "  1. Установка системных пакетов (fail2ban, iperf3, monit и т.д.)"
echo "  2. Установка конфигурационных файлов"
echo "  3. Установка Server Monitor (боты, скрипты, библиотеки)"
echo ""

read -p "Продолжить установку? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "Установка отменена"
    exit 0
fi

echo ""

#-------------------------------------------------------------------------------
# ШАГ 1: Установка пакетов
#-------------------------------------------------------------------------------
log_step "ШАГ 1/3: Установка системных пакетов"
echo ""
./install-packages.sh
echo ""

#-------------------------------------------------------------------------------
# ШАГ 2: Установка конфигов
#-------------------------------------------------------------------------------
log_step "ШАГ 2/3: Установка конфигурационных файлов"
echo ""
./install-configs.sh
echo ""

#-------------------------------------------------------------------------------
# ШАГ 3: Установка Server Monitor
#-------------------------------------------------------------------------------
log_step "ШАГ 3/3: Установка Server Monitor"
echo ""
./install.sh
echo ""

#-------------------------------------------------------------------------------
# Итог
#-------------------------------------------------------------------------------
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║                                                        ║"
echo "║          УСТАНОВКА ЗАВЕРШЕНА!                          ║"
echo "║                                                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Проверьте конфигурацию:"
echo "   nano /opt/server-monitor/config/secrets.json"
echo "   nano /opt/server-monitor/config/paths.json"
echo ""
echo "2. Перезапустите сервисы:"
echo "   systemctl restart fail2ban"
echo "   systemctl restart monit"
echo ""
echo "3. Запустите боты:"
echo "   systemctl enable --now telegram-admin-bot"
echo "   systemctl enable --now telegram-monitor"
echo ""
echo "4. Проверьте статус:"
echo "   systemctl status telegram-admin-bot"
echo "   systemctl status telegram-monitor"
echo ""
