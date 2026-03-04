#!/bin/bash
#===============================================================================
# Server Monitor - Initial Server Setup
# Первичная настройка сервера: локаль, timezone, пользователи
# Запускается один раз на новом сервере, требует reboot
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

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║                                                        ║"
echo "║      ПЕРВИЧНАЯ НАСТРОЙКА СЕРВЕРА                       ║"
echo "║                                                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Этот скрипт выполнит:"
echo "  1. Обновление системы"
echo "  2. Настройка локали (ru_RU.UTF-8)"
echo "  3. Настройка временной зоны (Europe/Moscow)"
echo "  4. Создание пользователей с sudo"
echo ""
echo -e "${YELLOW}⚠️  После завершения потребуется перезагрузка!${NC}"
echo ""

read -p "Продолжить? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "Отменено"
    exit 0
fi

#===============================================================================
# ЭТАП 1: Обновление системы
#===============================================================================
echo ""
log_step "ЭТАП 1/4: Обновление системы"
echo "═══════════════════════════════════════════════════"

log_info "Обновление списка пакетов..."
apt update

log_info "Обновление пакетов..."
apt upgrade -y

log_success "Система обновлена"

#===============================================================================
# ЭТАП 2: Настройка локали
#===============================================================================
echo ""
log_step "ЭТАП 2/4: Настройка локали"
echo "═══════════════════════════════════════════════════"

log_info "Установка пакетов локализации..."
apt install -y locales language-pack-ru

log_info "Генерация локалей..."
locale-gen en_US.UTF-8 ru_RU.UTF-8

log_info "Установка русской локали по умолчанию..."
update-locale LANG=ru_RU.UTF-8

# Сохраняем в /etc/default/locale
cat > /etc/default/locale << 'LOCALEEOF'
LANG=ru_RU.UTF-8
LANGUAGE=ru_RU:ru
LC_ALL=ru_RU.UTF-8
LOCALEEOF

log_success "Локаль настроена: ru_RU.UTF-8"

#===============================================================================
# ЭТАП 3: Настройка временной зоны
#===============================================================================
echo ""
log_step "ЭТАП 3/4: Настройка временной зоны"
echo "═══════════════════════════════════════════════════"

log_info "Установка временной зоны Europe/Moscow..."
timedatectl set-timezone Europe/Moscow

log_success "Временная зона: $(timedatectl | grep 'Time zone' | awk '{print $3}')"
log_success "Текущее время: $(date '+%d.%m.%Y %H:%M:%S')"

#===============================================================================
# ЭТАП 4: Создание пользователей
#===============================================================================
echo ""
log_step "ЭТАП 4/4: Создание пользователей"
echo "═══════════════════════════════════════════════════"

create_user() {
    local username="$1"
    local sudo_nopasswd="$2"  # "yes" или "no"
    local user_desc="$3"

    echo ""
    echo -e "${CYAN}Создание пользователя: $user_desc${NC}"
    echo "─────────────────────────────────────────────"

    # Ввод логина
    read -p "Введите логин: " username_input
    if [[ -z "$username_input" ]]; then
        log_warning "Логин не введён, пропускаем"
        return 1
    fi

    # Проверка существования пользователя
    if id "$username_input" &>/dev/null; then
        log_warning "Пользователь $username_input уже существует"
        read -p "Пропустить? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi

    # Ввод пароля с очисткой буфера
    while true; do
        # Очистка буфера ввода
        read -t 0.1 -n 10000 discard 2>/dev/null || true
        
        read -s -p "Введите пароль: " password1
        echo ""
        read -s -p "Повторите пароль: " password2
        echo ""
        
        if [[ "$password1" == "$password2" ]]; then
            if [[ ${#password1} -lt 6 ]]; then
                log_error "Пароль слишком короткий (минимум 6 символов)"
                continue
            fi
            break
        else
            log_error "Пароли не совпадают"
            continue
        fi
    done
    # Создаём пользователя
    log_info "Создание пользователя $username_input..."
    useradd -m -s /bin/bash "$username_input"
    echo "$username_input:$password1" | chpasswd

    # Добавляем в группу sudo
    usermod -aG sudo "$username_input"

    # Настройка sudoers
    if [[ "$sudo_nopasswd" == "yes" ]]; then
        echo "$username_input ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$username_input"
        chmod 440 "/etc/sudoers.d/$username_input"
        log_success "Пользователь $username_input создан (sudo БЕЗ пароля)"
    else
        log_success "Пользователь $username_input создан (sudo С паролем)"
    fi

    return 0
}

echo ""
echo "Будут созданы 2 пользователя:"
echo "  1. Пользователь с sudo (требуется пароль для sudo)"
echo "  2. Пользователь с sudo (БЕЗ пароля для sudo)"
echo ""

read -p "Создать пользователей? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Пользователь 1: sudo с паролем
    create_user "" "no" "Пользователь с sudo (требуется пароль)"

    # Пользователь 2: sudo без пароля
    create_user "" "yes" "Пользователь с sudo (БЕЗ пароля)"
else
    log_warning "Создание пользователей пропущено"
fi

#===============================================================================
# ЗАВЕРШЕНИЕ
#===============================================================================
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║                                                        ║"
echo "║      НАСТРОЙКА ЗАВЕРШЕНА!                              ║"
echo "║                                                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}✅ Выполнено:${NC}"
echo "   • Система обновлена"
echo "   • Локаль: ru_RU.UTF-8"
echo "   • Временная зона: Europe/Moscow"
echo "   • Пользователи созданы"
echo ""
echo -e "${YELLOW}⚠️  ТРЕБУЕТСЯ ПЕРЕЗАГРУЗКА!${NC}"
echo ""
echo "После перезагрузки выполните:"
echo "  cd /opt/server-monitor"
echo "  ./install/setup.sh"
echo ""

read -p "Перезагрузить сейчас? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Перезагрузка через 5 секунд..."
    sleep 5
    reboot
else
    log_warning "Не забудьте перезагрузить сервер командой: reboot"
fi
