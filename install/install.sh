#!/bin/bash
#===============================================================================
# Server Monitor - Installation Script
# Устанавливает server-monitor на новый сервер или обновляет текущий
#===============================================================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Пути
INSTALL_DIR="/opt/server-monitor"
CONFIG_DIR="$HOME/.config/server-monitor"
LIB_DIR="/usr/local/lib/server-monitor"
BIN_DIR="/usr/local/bin"
DATA_DIR="/opt/server-monitor/data"

#-------------------------------------------------------------------------------
# Функции вывода
#-------------------------------------------------------------------------------
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

#-------------------------------------------------------------------------------
# Проверка запуска от root
#-------------------------------------------------------------------------------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Скрипт должен быть запущен от root"
        exit 1
    fi
}

#-------------------------------------------------------------------------------
# Создание директорий
#-------------------------------------------------------------------------------
create_directories() {
    log_info "Создание директорий..."
    
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LIB_DIR"
    mkdir -p "$DATA_DIR"
    
    chmod 700 "$CONFIG_DIR"
    
    log_success "Директории созданы"
}

#-------------------------------------------------------------------------------
# Установка библиотеки конфигурации
#-------------------------------------------------------------------------------
install_lib() {
    log_info "Установка библиотеки конфигурации..."

    # Удаляем старые файлы если есть
    rm -f "$LIB_DIR/config.py"
    rm -f "$LIB_DIR/load-config.sh"
    rm -rf "$LIB_DIR/__pycache__"

    # Создаём симлинки
    ln -s "$INSTALL_DIR/lib/config.py" "$LIB_DIR/config.py"
    ln -s "$INSTALL_DIR/lib/load-config.sh" "$LIB_DIR/load-config.sh"

    log_success "Библиотека установлена в $LIB_DIR (симлинки)"
}

#-------------------------------------------------------------------------------
# Создание симлинков для скриптов
#-------------------------------------------------------------------------------
create_symlinks() {
    log_info "Создание симлинков в $BIN_DIR..."
    
    local scripts_dir="$INSTALL_DIR/scripts"
    local count=0
    
    # Проходим по всем поддиректориям scripts
    for category in fail2ban network system geoip; do
        if [[ -d "$scripts_dir/$category" ]]; then
            for script in "$scripts_dir/$category"/*.sh "$scripts_dir/$category"/*.py; do
                if [[ -f "$script" ]]; then
                    local script_name=$(basename "$script")
                    local link_path="$BIN_DIR/$script_name"
                    
                    # Удаляем старый симлинк или файл если есть
                    if [[ -L "$link_path" ]] || [[ -f "$link_path" ]]; then
                        rm -f "$link_path"
                    fi
                    
                    ln -s "$script" "$link_path"
                    ((count++))
                fi
            done
        fi
    done
    
    log_success "Создано $count симлинков"
}

#-------------------------------------------------------------------------------
# Проверка/создание конфигурации
#-------------------------------------------------------------------------------
setup_config() {
    log_info "Проверка конфигурации..."
    
    # Проверяем наличие secrets.json
    if [[ ! -f "$CONFIG_DIR/secrets.json" ]]; then
        log_warning "Файл secrets.json не найден!"
        echo ""
        echo "Создайте файл $CONFIG_DIR/secrets.json со следующим содержимым:"
        echo ""
        cat "$INSTALL_DIR/config/examples/secrets.json.example"
        echo ""
        echo "Или выполните команду:"
        echo "  cp $INSTALL_DIR/config/examples/secrets.json.example $CONFIG_DIR/secrets.json"
        echo "  nano $CONFIG_DIR/secrets.json"
        echo ""
        return 1
    fi
    
    # Копируем paths.json и settings.json если отсутствуют
    if [[ ! -f "$CONFIG_DIR/paths.json" ]]; then
        cp "$INSTALL_DIR/config/examples/paths.json" "$CONFIG_DIR/"
        log_info "Создан paths.json (проверьте пути!)"
    fi
    
    if [[ ! -f "$CONFIG_DIR/settings.json" ]]; then
        cp "$INSTALL_DIR/config/examples/settings.json" "$CONFIG_DIR/"
        log_info "Создан settings.json"
    fi
    
    chmod 600 "$CONFIG_DIR/secrets.json"
    chmod 644 "$CONFIG_DIR/paths.json"
    chmod 644 "$CONFIG_DIR/settings.json"
    
    log_success "Конфигурация готова"
}

#-------------------------------------------------------------------------------
# Установка Python зависимостей
#-------------------------------------------------------------------------------
setup_venv() {
    log_info "Проверка виртуальных окружений..."
    
    local bots_dir="$INSTALL_DIR/bots"
    
    # admin_bot venv
    if [[ ! -d "$bots_dir/admin_bot_venv" ]]; then
        log_info "Создание venv для admin_bot..."
        python3 -m venv "$bots_dir/admin_bot_venv"
        "$bots_dir/admin_bot_venv/bin/pip" install --upgrade pip -q
        "$bots_dir/admin_bot_venv/bin/pip" install -r "$bots_dir/admin_bot_requirements.txt" -q
    fi
    
    # monitor venv
    if [[ ! -d "$bots_dir/monitor_venv" ]]; then
        log_info "Создание venv для monitor..."
        python3 -m venv "$bots_dir/monitor_venv"
        "$bots_dir/monitor_venv/bin/pip" install --upgrade pip -q
        "$bots_dir/monitor_venv/bin/pip" install -r "$bots_dir/monitor_requirements.txt" -q
    fi
    

    # Установка прав на скрипты ботов
    chmod 644 "$bots_dir/admin_bot.py"
    chmod 644 "$bots_dir/monitor.py"
    log_info "Права на файлы ботов установлены"
    log_success "Виртуальные окружения готовы"
}

#-------------------------------------------------------------------------------
# Установка systemd сервисов
#-------------------------------------------------------------------------------
install_systemd_services() {
    log_info "Установка systemd сервисов..."
    
    # telegram-admin-bot.service
    cat > /etc/systemd/system/telegram-admin-bot.service << SVCEOF
[Unit]
Description=Telegram Admin Bot
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/bots/admin_bot_venv/bin/python $INSTALL_DIR/bots/admin_bot.py
Restart=always
RestartSec=10
WorkingDirectory=$INSTALL_DIR/bots

[Install]
WantedBy=multi-user.target
SVCEOF

    # telegram-monitor.service
    cat > /etc/systemd/system/telegram-monitor.service << SVCEOF
[Unit]
Description=Telegram Server Monitor
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/bots/monitor_venv/bin/python $INSTALL_DIR/bots/monitor.py
Restart=always
RestartSec=10
WorkingDirectory=$INSTALL_DIR/bots

[Install]
WantedBy=multi-user.target
SVCEOF

    systemctl daemon-reload
    
    log_success "Systemd сервисы установлены"
}

#-------------------------------------------------------------------------------
# Настройка cron
#-------------------------------------------------------------------------------
setup_cron() {
    log_info "Настройка cron задач..."
    
    # Создаём временный файл с cron задачами
    local cron_file="/tmp/server-monitor-cron"
    
    cat > "$cron_file" << CRONEOF
# Server Monitor - автоматические задачи
# Обновление geoip каждое воскресенье в 3:00
0 3 * * 0 $BIN_DIR/update-ips.sh > /var/log/geoip-update.log 2>&1

# Сбор сетевой статистики каждый час
0 * * * * $BIN_DIR/collect-network-stats.sh force-save > /dev/null 2>&1

# При загрузке системы
@reboot $BIN_DIR/collect-network-stats.sh force-save > /dev/null 2>&1

# Сохранение дневной статистики в 23:59
59 23 * * * $BIN_DIR/collect-network-stats.sh force-save > /dev/null 2>&1
CRONEOF

    # Показываем что будет установлено
    echo ""
    echo "Будут добавлены следующие cron задачи:"
    cat "$cron_file"
    echo ""
    
    read -p "Установить эти cron задачи? (y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        crontab "$cron_file"
        log_success "Cron задачи установлены"
    else
        log_warning "Cron задачи пропущены"
    fi
    
    rm -f "$cron_file"
}

#-------------------------------------------------------------------------------
# Главная функция
#-------------------------------------------------------------------------------
main() {
    echo ""
    echo "=========================================="
    echo "  Server Monitor - Installation"
    echo "=========================================="
    echo ""
    
    check_root
    create_directories
    install_lib
    create_symlinks
    setup_venv
    
    if ! setup_config; then
        log_error "Настройте конфигурацию и запустите установщик повторно"
        exit 1
    fi
    
    install_systemd_services
    setup_cron
    
    echo ""
    echo "=========================================="
    echo "  Установка завершена!"
    echo "=========================================="
    echo ""
    echo "Для запуска сервисов выполните:"
    echo "  systemctl enable --now telegram-admin-bot"
    echo "  systemctl enable --now telegram-monitor"
    echo ""
    echo "Для проверки статуса:"
    echo "  systemctl status telegram-admin-bot"
    echo "  systemctl status telegram-monitor"
    echo ""
}

# Запуск
main "$@"
