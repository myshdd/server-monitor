#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import html
import subprocess
import psutil
import os
import sys
import json
from datetime import datetime, timedelta
import re

sys.path.insert(0, '/usr/local/lib/server-monitor')
from config import get_config, setup_logging, ConfigError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, TypeHandler, ApplicationHandlerStop

# Загрузка конфигурации
try:
    config = get_config()
    logger = setup_logging(__name__, config.get_path("logs.admin_bot"))
    TOKEN = config.telegram_admin_token
    ALLOWED_USER_ID = config.telegram_chat_id
    logger.info("Конфигурация загружена")
except ConfigError as e:
    print(f"❌ Ошибка конфигурации: {e}", file=sys.stderr)
    sys.exit(1)


# ============================================
# УТИЛИТЫ ДЛЯ ЭКРАНИРОВАНИЯ MARKDOWN
# ============================================

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы Markdown v1"""
    special_chars = r"_*[`"
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text
# ============================================
# УТИЛИТЫ ДЛЯ РАБОТЫ С СЕТЬЮ
# ============================================

async def get_network_speed():
    """
    Получает текущую скорость сети по всем интерфейсам.
    Делает два замера с интервалом 1 секунда и вычисляет разницу.
    Возвращает словарь с данными по каждому интерфейсу:
    - sent_speed, recv_speed: скорость в байтах/сек
    - total_sent, total_recv: всего передано/получено байт
    - packets_sent, packets_recv: количество пакетов
    - errin, errout, dropin, dropout: ошибки и потери
    """
    try:
        net1 = psutil.net_io_counters(pernic=True)
        await asyncio.sleep(1)
        net2 = psutil.net_io_counters(pernic=True)
        result = {}
        for iface in net2:
            if iface in net1:
                result[iface] = {
                    'sent_speed': (net2[iface].bytes_sent - net1[iface].bytes_sent),
                    'recv_speed': (net2[iface].bytes_recv - net1[iface].bytes_recv),
                    'total_sent': net2[iface].bytes_sent,
                    'total_recv': net2[iface].bytes_recv,
                    'packets_sent': net2[iface].packets_sent,
                    'packets_recv': net2[iface].packets_recv,
                    'errin': net2[iface].errin,
                    'errout': net2[iface].errout,
                    'dropin': net2[iface].dropin,
                    'dropout': net2[iface].dropout
                }
        return result
    except Exception as e:
        logger.error(f"Ошибка сетевой статистики: {e}")
        return None

def format_bytes(b):
    """
    Форматирует байты в читаемый вид (B, KB, MB, GB).
    Примеры: 1024 -> "1.0 KB", 1048576 -> "1.0 MB"
    """
    if b < 1024: return f"{b:.0f} B"
    elif b < 1024**2: return f"{b/1024:.1f} KB"
    elif b < 1024**3: return f"{b/(1024**2):.1f} MB"
    else: return f"{b/(1024**3):.2f} GB"

def format_speed(b):
    """
    Форматирует скорость передачи данных (B/s, KB/s, MB/s).
    Примеры: 1024 -> "1.0 KB/s", 1048576 -> "1.0 MB/s"
    """
    if b < 1024: return f"{b:.0f} B/s"
    elif b < 1024**2: return f"{b/1024:.1f} KB/s"
    else: return f"{b/(1024**2):.1f} MB/s"

# ============================================
# АВТОРИЗАЦИЯ И БЕЗОПАСНОСТЬ
# ============================================

async def is_authorized(update: Update) -> bool:
    """
    Проверяет, имеет ли пользователь право использовать бота.
    Сравнивает user_id отправителя с ALLOWED_USER_ID из конфига.
    Возвращает True если авторизован, False если нет.
    При неудачной авторизации отправляет сообщение об отказе.
    """
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Нет прав")
        return False
    return True

# ============================================
# КЛАВИАТУРЫ И МЕНЮ
# ============================================

def main_menu_keyboard():
    """
    Генерирует клавиатуру главного меню бота.
    Содержит кнопки для доступа ко всем основным функциям:
    статистика, Docker, логи, Fail2ban и т.д.
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("🔒 Забаненные IP", callback_data='banned_ips')],
        [InlineKeyboardButton("📊 Графики нагрузки", callback_data='graphs')],
        [InlineKeyboardButton("🐳 Docker контейнеры", callback_data='docker_list')],
        [InlineKeyboardButton("📋 Системная информация", callback_data='sysinfo')],
        [InlineKeyboardButton("📦 Обновление системы", callback_data='update_system')],
        [InlineKeyboardButton("📁 Просмотр логов", callback_data='logs_menu')],
        [InlineKeyboardButton("🛡️ Fail2ban Dashboard", callback_data='f2b_status')],
        [InlineKeyboardButton("🔧 Дополнительные команды", callback_data='extra_menu')],
        [InlineKeyboardButton("📡 Тест скорости", callback_data='iperf_speedtest')],
        [
            InlineKeyboardButton("🔄 Перезагрузка", callback_data='reboot'),
            InlineKeyboardButton("⛔ Выключение", callback_data='shutdown')
        ],
    ])

# ============================================
# КОМАНДЫ БОТА
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start.
    Проверяет авторизацию пользователя и показывает главное меню.
    Логирует запуск бота пользователем.
    """
    if not await is_authorized(update):
        return
    context.user_data.pop("pending_power_action", None)
    context.user_data.pop("pending_package_action", None)
    await update.message.reply_text("🤖 *Admin Bot v2*", reply_markup=main_menu_keyboard(), parse_mode='Markdown')

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать полную статистику сервера"""
    query = update.callback_query
    await query.answer()
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    cpu_info = f"🚀 *Процессор:*\n"
    cpu_info += f"  └ Загрузка: {cpu_percent}% ({cpu_count} ядер)\n"
    if cpu_freq:
        cpu_info += f"  └ Частота: {cpu_freq.current:.0f} МГц\n"
    
    # RAM
    mem = psutil.virtual_memory()
    mem_total = mem.total / (1024**3)
    mem_used = mem.used / (1024**3)
    mem_percent = mem.percent
    mem_info = f"💾 *Память:*\n"
    mem_info += f"  └ Использовано: {mem_used:.1f}ГБ / {mem_total:.1f}ГБ ({mem_percent}%)\n"
    
    # SWAP
    swap = psutil.swap_memory()
    swap_total = swap.total / (1024**3)
    swap_used = swap.used / (1024**3)
    swap_percent = swap.percent
    swap_info = f"🔄 *Swap:*\n"
    if swap_total > 0:
        swap_info += f"  └ Использовано: {swap_used:.2f}ГБ / {swap_total:.2f}ГБ ({swap_percent}%)\n"
    else:
        swap_info += f"  └ Swap не настроен\n"
    
    # Диск
    disk = psutil.disk_usage('/')
    disk_total = disk.total / (1024**3)
    disk_used = disk.used / (1024**3)
    disk_percent = disk.percent
    disk_info = f"💽 *Диск:*\n"
    disk_info += f"  └ Использовано: {disk_used:.1f}ГБ / {disk_total:.1f}ГБ ({disk_percent}%)\n"
    
    # Load Average
    load_avg = psutil.getloadavg()
    load_info = f"📈 *Load Average:* {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}\n"
    
    # Uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    uptime_str = str(uptime).split('.')[0]
    uptime_info = f"⏱️ *Аптайм:* {uptime_str}\n"
    
    # Сеть
    net_info = "🌐 *Сеть:*\n"
    net_speed = await get_network_speed()
    
    if net_speed:
        important_interfaces = []
        for iface in net_speed:
            if iface != 'lo' and not iface.startswith('veth') and not iface.startswith('br-'):
                important_interfaces.append(iface)
        
        docker_ifaces = ['docker0', 'amn0']
        for iface in docker_ifaces:
            if iface in net_speed and iface not in important_interfaces:
                important_interfaces.append(iface)
        
        if important_interfaces:
            net_info += f"  └ Интерфейсы: {', '.join(important_interfaces)}\n\n"
            
            for iface in important_interfaces:
                if iface in net_speed:
                    data = net_speed[iface]
                    net_info += f"  *{iface}:*\n"
                    net_info += f"    ├ 📤 {format_speed(data['sent_speed'])} (всего: {format_bytes(data['total_sent'])})\n"
                    net_info += f"    └ 📥 {format_speed(data['recv_speed'])} (всего: {format_bytes(data['total_recv'])})\n"
            
            total_sent = sum(data['total_sent'] for data in net_speed.values())
            total_recv = sum(data['total_recv'] for data in net_speed.values())
            total_sent_speed = sum(data['sent_speed'] for data in net_speed.values())
            total_recv_speed = sum(data['recv_speed'] for data in net_speed.values())
            
            net_info += f"\n  *Всего:*\n"
            net_info += f"    ├ 📤 {format_speed(total_sent_speed)} (всего: {format_bytes(total_sent)})\n"
            net_info += f"    └ 📥 {format_speed(total_recv_speed)} (всего: {format_bytes(total_recv)})\n"
        else:
            net_info += "  └ Нет активных интерфейсов\n"
    else:
        net_info += "  └ Не удалось получить статистику\n"
    
    message = (
        f"📊 *СТАТИСТИКА СЕРВЕРА*\n\n"
        f"{cpu_info}\n"
        f"{mem_info}\n"
        f"{swap_info}\n"
        f"{disk_info}\n"
        f"{load_info}\n"
        f"{uptime_info}\n"
        f"{net_info}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Очистить swap", callback_data='clear_swap')],
        [InlineKeyboardButton("📊 Сетевая статистика", callback_data='network_stats_menu')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

# ============================================
# СЕТЕВАЯ СТАТИСТИКА ИЗ JSON ФАЙЛА
# Отображает накопленную статистику по дням/неделям/месяцам/годам
# ============================================

async def network_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Меню выбора периода сетевой статистики.
    Позволяет выбрать: дневная, недельная, месячная, годовая статистика.
    """
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📊 Дневная (7 дней)", callback_data='net_stats_daily')],
        [InlineKeyboardButton("📊 Недельная (4 недели)", callback_data='net_stats_weekly')],
        [InlineKeyboardButton("📊 Месячная (12 месяцев)", callback_data='net_stats_monthly')],
        [InlineKeyboardButton("📊 Годовая (5 лет)", callback_data='net_stats_yearly')],
        [InlineKeyboardButton("🔙 Назад", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📊 *СЕТЕВАЯ СТАТИСТИКА*\n\n"
        "Выберите период:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def show_network_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображение сетевой статистики за выбранный период.
    Читает данные из JSON файла, который заполняется скриптом collect-network-stats.sh.
    Поддерживает периоды: daily, weekly, monthly, yearly.
    """
    query = update.callback_query
    await query.answer()
    
    period = query.data.replace('net_stats_', '')
    
    # Получаем путь к файлу статистики из конфига
    stats_file = config.get_path("data.network_stats_file", "/opt/server-monitor/data/stats.json")
    
    try:
        with open(stats_file, 'r') as f:
            data = json.load(f)
        
        def format_period_data(period_data: dict, period_key: str) -> str:
            """Форматирование данных одного периода"""
            result = ""
            
            # Сортируем интерфейсы: сначала обычные, потом total
            interfaces = sorted(
                period_data.items(),
                key=lambda x: (x[0] == 'total', x[0])
            )
            
            for iface_name, stats in interfaces:
                # Пропускаем виртуальные интерфейсы
                if iface_name.startswith('veth'):
                    continue
                
                rx = format_bytes(stats.get('rx', 0))
                tx = format_bytes(stats.get('tx', 0))
                
                if iface_name == 'total':
                    result += f"  └ *Всего:* 📥 {rx} | 📤 {tx}\n"
                else:
                    result += f"  ├ {iface_name}: 📥 {rx} | 📤 {tx}\n"
            
            return result
        
        # Заголовки для разных периодов
        titles = {
            'daily': "📊 *Дневная статистика (последние 7 дней)*",
            'weekly': "📊 *Недельная статистика (последние 4 недели)*",
            'monthly': "📊 *Месячная статистика (последние 12 месяцев)*",
            'yearly': "📊 *Годовая статистика (последние 5 лет)*"
        }
        
        period_labels = {
            'daily': "📅",
            'weekly': "📅 Неделя",
            'monthly': "📅",
            'yearly': "📅"
        }
        
        title = titles.get(period, "📊 *Статистика*") + "\n\n"
        
        # Получаем данные периода
        period_data = data.get(period, {})
        
        if not period_data:
            title += "_Нет данных за этот период_\n"
        else:
            # Сортируем по ключам (датам) в обратном порядке
            sorted_periods = sorted(period_data.keys(), reverse=True)
            
            for period_key in sorted_periods:
                stats = period_data[period_key]
                label = period_labels.get(period, "📅")
                title += f"{label} *{period_key}*:\n"
                title += format_period_data(stats, period_key)
                title += "\n"
        
        title += f"🕐 _Обновлено: {data.get('last_update', 'N/A')}_"
        
    except FileNotFoundError:
        title = "❌ Файл статистики не найден.\n\nЗапустите сбор статистики:\n`collect-network-stats.sh`"
    except json.JSONDecodeError as e:
        title = f"❌ Ошибка чтения JSON: {str(e)}"
    except Exception as e:
        logger.error(f"Ошибка загрузки сетевой статистики: {e}")
        title = f"❌ Ошибка загрузки статистики: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='network_stats_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(title, parse_mode='Markdown', reply_markup=reply_markup)


# ============================================
# ОЧИСТКА SWAP
# Безопасная очистка swap-памяти через внешний скрипт
# ============================================

async def clear_swap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос подтверждения очистки swap.
    Показывает текущее состояние swap и запрашивает подтверждение.
    """
    query = update.callback_query
    await query.answer()
    
    # Текущее состояние swap
    swap = psutil.swap_memory()
    swap_used = swap.used / (1024**3)
    swap_total = swap.total / (1024**3)
    swap_percent = swap.percent
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, очистить swap", callback_data='confirm_clear_swap')],
        [InlineKeyboardButton("❌ Нет, отмена", callback_data='stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🔄 *Очистка swap*\n\n"
        f"Текущее состояние swap:\n"
        f"  └ Использовано: {swap_used:.2f}ГБ / {swap_total:.2f}ГБ ({swap_percent:.1f}%)\n\n"
        f"⚠️ *ВНИМАНИЕ!*\n"
        f"Очистка swap переместит данные обратно в RAM.\n"
        f"Убедитесь, что достаточно свободной памяти!\n\n"
        f"Продолжить?",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def confirm_clear_swap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выполнение очистки swap через внешний скрипт.
    Вызывает clear-swap.sh и отображает результат.
    """
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔄 *Очистка swap...*\n\n"
        "Выполняется безопасная очистка...",
        parse_mode='Markdown'
    )
    
    try:
        # Запускаем скрипт очистки
        result = subprocess.run(
            ['clear-swap.sh'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            output = result.stdout
        else:
            output = f"❌ Ошибка:\n{result.stderr}"
        
        # Проверяем результат
        swap = psutil.swap_memory()
        swap_used = swap.used / (1024**3)
        swap_percent = swap.percent
        
        output += f"\n\n📊 Итоговое состояние:\n"
        output += f"  Использовано: {swap_used:.2f}ГБ ({swap_percent:.1f}%)"
        
        message = f"📊 *РЕЗУЛЬТАТ ОЧИСТКИ SWAP*\n\n```\n{output}\n```"
        
    except subprocess.TimeoutExpired:
        message = "❌ *Таймаут*\n\nОчистка swap заняла слишком много времени."
    except Exception as e:
        logger.error(f"Ошибка очистки swap: {e}")
        message = f"❌ *Ошибка*\n\n{str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='stats')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

# ============================================
# ЗАБАНЕННЫЕ IP / FAIL2BAN
# Управление забаненными IP-адресами через fail2ban-client
# ============================================

async def show_banned_ips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает блокировки Fail2ban с контролем полноты данных."""
    import html
    import ipaddress

    query = update.callback_query
    await query.answer()

    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ])

    try:
        result = subprocess.run(
            ['fail2ban-client', 'status'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise RuntimeError("Не удалось получить статус Fail2ban")

        jail_line = next(
            (line for line in result.stdout.splitlines()
             if "Jail list:" in line),
            None
        )

        if jail_line is None:
            raise ValueError("Отсутствует Jail list")

        jail_text = jail_line.partition("Jail list:")[2].strip()
        jail_list = (
            [j.strip() for j in jail_text.split(",")]
            if jail_text else []
        )

        if any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", jail)
            for jail in jail_list
        ):
            raise ValueError("Некорректный список jail")

        if not jail_list:
            await query.edit_message_text(
                "ℹ️ Активных jail Fail2ban нет.",
                reply_markup=back_keyboard
            )
            return

        message = "🔒 <b>ЗАБАНЕННЫЕ IP</b>\n\n"
        keyboard = []
        has_bans = False
        failed_jails = []
        shown_jails = 0
        hidden_jails = 0

        for jail in jail_list:
            try:
                result = subprocess.run(
                    ['fail2ban-client', 'status', jail],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    raise RuntimeError("Ошибка получения статуса jail")

                ip_line = next(
                    (line for line in result.stdout.splitlines()
                     if "Banned IP list:" in line),
                    None
                )

                if ip_line is None:
                    raise ValueError("Отсутствует Banned IP list")

                ip_text = ip_line.partition("Banned IP list:")[2].strip()
                ip_list = ip_text.split()

                for ip in ip_list:
                    if "%" in ip:
                        raise ValueError("Некорректный IP")
                    ipaddress.ip_address(ip)

                if not ip_list:
                    continue

                has_bans = True
                if shown_jails >= 8:
                    hidden_jails += 1
                    continue
                shown_jails += 1
                message += (
                    f"<b>{html.escape(jail)}:</b> "
                    f"{len(ip_list)} IP\n"
                )

                for ip in ip_list[:5]:
                    message += f"  └ <code>{html.escape(ip)}</code>\n"

                    callback = f"unban_{jail}_{ip}"
                    if len(callback.encode("utf-8")) <= 64:
                        keyboard.append([
                            InlineKeyboardButton(
                                f"🔓 Разбанить {ip}",
                                callback_data=callback
                            )
                        ])

                if len(ip_list) > 5:
                    message += f"  └ ... и еще {len(ip_list) - 5}\n"

                message += "\n"

            except Exception as e:
                failed_jails.append(jail)
                logger.warning(
                    "Не удалось получить блокировки jail=%s: %s",
                    jail, type(e).__name__
                )

        if hidden_jails:
            message += (
                f"ℹ️ Не показано jail с блокировками: "
                f"{hidden_jails}\n"
            )

        if failed_jails:
            message += (
                "⚠️ <b>Данные неполные.</b> "
                "Не удалось получить сведения для jail: "
                + ", ".join(html.escape(j) for j in failed_jails[:5])
                + (f" (и ещё {len(failed_jails) - 5})" if len(failed_jails) > 5 else "")
                + "\n"
            )

        if not has_bans:
            if failed_jails:
                message += (
                    "Подтверждённых блокировок в доступных данных нет."
                )
            else:
                message += "✅ Нет забаненных IP"

        if has_bans:
            keyboard.append([
                InlineKeyboardButton(
                    "🔓 Разбанить все", callback_data="unban_all"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    "🔍 Разбанить IP по адресу",
                    callback_data="unban_ip_input"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
        ])

        await query.edit_message_text(
            message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except subprocess.TimeoutExpired:
        logger.error("Таймаут при получении статуса Fail2ban")
        await query.edit_message_text(
            "❌ Таймаут при получении данных Fail2ban",
            reply_markup=back_keyboard
        )

    except Exception as e:
        logger.error(
            "Ошибка показа забаненных IP: %s",
            type(e).__name__
        )
        await query.edit_message_text(
            "❌ Не удалось получить список блокировок Fail2ban",
            reply_markup=back_keyboard
        )


async def unban_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Разбанивает конкретный IP-адрес в указанном jail'е.
    Формат callback_data: unban_{jail}_{ip}
    """
    query = update.callback_query
    await query.answer()
    
    # Разбираем и проверяем jail и IP из callback_data
    import ipaddress

    data = query.data
    if not isinstance(data, str) or not data.startswith("unban_"):
        await query.edit_message_text("❌ Ошибка: неверный формат данных")
        return

    parts = data[len("unban_"):].rsplit("_", 1)
    if len(parts) != 2:
        await query.edit_message_text("❌ Ошибка: неверный формат данных")
        return

    jail, ip = parts

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", jail):
        await query.edit_message_text("❌ Некорректное имя jail")
        return

    try:
        if "%" in ip:
            raise ValueError("IPv6 zone identifier is not allowed")
        ipaddress.ip_address(ip)
    except ValueError:
        await query.edit_message_text("❌ Некорректный IP-адрес")
        return
    
    try:
        result = subprocess.run(
            ['fail2ban-client', 'set', jail, 'unbanip', ip],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            logger.warning(
                "Fail2ban unban failed (exit=%s)",
                result.returncode
            )
            message = "❌ Не удалось разблокировать IP в указанном jail"
        else:
            count_text = result.stdout.strip()

            if count_text.isascii() and count_text.isdecimal():
                unbanned_count = int(count_text)
                if unbanned_count > 0:
                    logger.info(
                        "IP %s разбанен в jail %s (count=%s)",
                        ip, jail, unbanned_count
                    )
                    message = (
                        f"✅ IP <code>{html.escape(ip)}</code> "
                        f"успешно разбанен в jail "
                        f"<code>{html.escape(jail)}</code>"
                    )
                else:
                    message = (
                        f"ℹ️ IP <code>{html.escape(ip)}</code> "
                        f"не был заблокирован в jail "
                        f"<code>{html.escape(jail)}</code>"
                    )
            else:
                logger.warning(
                    "Неожиданный ответ Fail2ban unbanip: %r",
                    count_text[:100]
                )
                message = "❌ Не удалось подтвердить результат разблокировки"
        
        keyboard = [[InlineKeyboardButton("🔙 К списку", callback_data='banned_ips')]]
        await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            
    except Exception as e:
        logger.error(f"Ошибка разбана IP {ip}: {e}")
        await query.edit_message_text("❌ Внутренняя ошибка разблокировки IP")


async def unban_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрос подтверждения на разбан всех IP во всех jail'ах.
    """
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, разбанить все", callback_data='confirm_unban_all')],
        [InlineKeyboardButton("❌ Нет, отмена", callback_data='banned_ips')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⚠️ *ВНИМАНИЕ!*\n\n"
        "Вы действительно хотите разбанить ВСЕ IP во всех jail'ах?",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def confirm_unban_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Снимает все блокировки Fail2ban после подтверждения пользователя."""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 К списку", callback_data="banned_ips")]
    ])

    try:
        result = subprocess.run(
            ['fail2ban-client', 'unban', '--all'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.warning(
                "Fail2ban mass unban failed (exit=%s)",
                result.returncode
            )
            message = (
                "❌ Массовая разблокировка завершилась с ошибкой. "
                "Результат операции необходимо проверить."
            )
        else:
            count_text = result.stdout.strip()

            if not count_text.isascii() or not count_text.isdecimal():
                logger.warning(
                    "Неожиданный ответ Fail2ban mass unban: %r",
                    count_text[:100]
                )
                message = (
                    "⚠️ Команда массовой разблокировки выполнена, "
                    "но количество снятых блокировок не подтверждено."
                )
            else:
                removed_count = int(count_text)
                logger.info(
                    "Fail2ban mass unban: removed=%s",
                    removed_count
                )
                message = (
                    "✅ Массовая разблокировка завершена.\n\n"
                    f"Снято блокировок: {removed_count}"
                )

    except subprocess.TimeoutExpired:
        logger.error("Таймаут массовой разблокировки Fail2ban")
        message = (
            "⚠️ Превышено время ожидания Fail2ban. "
            "Результат операции неизвестен — проверьте список блокировок."
        )

    except Exception as e:
        logger.error(
            "Ошибка массовой разблокировки Fail2ban: %s",
            type(e).__name__
        )
        message = (
            "❌ Не удалось подтвердить выполнение массовой разблокировки."
        )

    await query.edit_message_text(
        message,
        reply_markup=keyboard
    )


async def ask_unban_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрашивает ввод IP-адреса для ручного разбана.
    Устанавливает флаг ожидания ввода в context.user_data.
    """
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_unban_ip'] = True
    
    await query.edit_message_text(
        "🔍 *Введите IP адрес для разбана*\n\n"
        "Поддерживаются IPv4 и IPv6.\n"
        "Пример IPv4: `192.0.2.10`\n"
        "Пример IPv6: `2001:db8::1`\n"
        "Или отправьте /cancel для отмены.",
        parse_mode='Markdown'
    )


# ============================================
# FAIL2BAN DASHBOARD
# Полная статистика Fail2ban через внешний скрипт
# ============================================

async def f2b_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает полный дашборд Fail2ban.
    Вызывает внешний скрипт f2b-status.sh
    и показывает его вывод в Telegram.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['f2b-status.sh'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            output = result.stdout
        else:
            output = f"❌ Ошибка выполнения скрипта:\n{result.stderr}"
        
        # Ограничиваем длину (Telegram лимит ~4096 символов)
        if len(output) > 3500:
            output = output[:3500] + "\n\n... (вывод обрезан)"
        
        # Экранируем спецсимволы Markdown
        output = output.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
        
        message = f"📊 *FAIL2BAN DASHBOARD*\n\n```\n{output}\n```"
        
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут при выполнении скрипта"
    except FileNotFoundError:
        message = "❌ Скрипт f2b-status.sh не найден"
    except Exception as e:
        logger.error(f"Ошибка F2B dashboard: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

# ============================================
# DOCKER КОНТЕЙНЕРЫ
# Просмотр и управление Docker контейнерами
# ============================================

def is_valid_docker_container_name(name: str) -> bool:
    """Проверяет допустимый формат имени контейнера."""
    return (
        isinstance(name, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name)
        is not None
    )


async def show_docker_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает список всех Docker контейнеров.
    Показывает имя, статус и образ каждого контейнера.
    Предоставляет кнопки для управления каждым контейнером.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}|{{.Image}}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            logger.error(
                "docker ps failed: %s",
                result.stderr.strip()
            )
            await query.edit_message_text(
                "❌ Не удалось получить список Docker-контейнеров"
            )
            return

        if not result.stdout.strip():
            await query.edit_message_text(
                "❌ Нет Docker контейнеров",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]])
            )
            return
        
        message = "🐳 *DOCKER КОНТЕЙНЕРЫ*\n\n"
        keyboard = []
        
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|')
                name = parts[0]
                status = parts[1]
                image = parts[2] if len(parts) > 2 else "unknown"
                
                status_emoji = "✅" if "Up" in status else "⏹"
                message += f"{status_emoji} `{escape_markdown(name)}` ({escape_markdown(image)})\n"
                keyboard.append([InlineKeyboardButton(f"{status_emoji} {name}", callback_data=f'docker_{name}')])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        
    except subprocess.TimeoutExpired:
        await query.edit_message_text("❌ Таймаут при получении списка контейнеров")
    except FileNotFoundError:
        await query.edit_message_text(
            "ℹ️ Docker не установлен на этом сервере",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]])
        )
    except Exception as e:
        logger.error(f"Ошибка получения списка Docker: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")


async def docker_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает меню управления конкретным контейнером.
    Отображает текущий статус и кнопки: запуск, остановка, перезапуск, логи.
    """
    query = update.callback_query
    
    # Получаем имя контейнера из callback_data
    container = query.data.removeprefix('docker_')
    
    # Проверяем, что это не служебное слово
    if container in ['list', 'start', 'stop', 'restart', 'logs']:
        await show_docker_list(update, context)
        return

    await query.answer()

    if not is_valid_docker_container_name(container):
        await query.edit_message_text(
            "❌ Некорректное имя Docker-контейнера"
        )
        return
    
    try:
        # Получаем статус контейнера
        result = subprocess.run(
            ['docker', 'inspect', '--format', '{{.State.Status}}', container],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            logger.warning(
                "docker inspect failed for %s (exit=%s)",
                container,
                result.returncode
            )
            await query.edit_message_text(
                "❌ Не удалось получить состояние Docker-контейнера"
            )
            return

        status = result.stdout.strip()
        
        keyboard = [
            [
                InlineKeyboardButton("▶️ Запустить", callback_data=f'docker_start_{container}'),
                InlineKeyboardButton("⏹ Остановить", callback_data=f'docker_stop_{container}')
            ],
            [InlineKeyboardButton("🔄 Перезапустить", callback_data=f'docker_restart_{container}')],
            [InlineKeyboardButton("📊 Логи", callback_data=f'docker_logs_{container}')],
            [InlineKeyboardButton("🔙 Назад", callback_data='docker_list')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        status_emoji = "✅" if status == "running" else "⏹" if status == "exited" else "❓"
        
        await query.edit_message_text(
            f"🐳 *Управление контейнером:* `{escape_markdown(container)}`\n\n"
            f"Статус: {status_emoji} {status}\n\n"
            f"Выберите действие:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except FileNotFoundError:
        await query.edit_message_text(
            "ℹ️ Docker не установлен на этом сервере",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]])
        )
    except Exception as e:
        logger.error(f"Ошибка управления контейнером {container}: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")


async def docker_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выполняет действие над Docker контейнером.
    Поддерживаемые действия: start, stop, restart, logs.
    Формат callback_data: docker_{action}_{container}
    """
    query = update.callback_query
    await query.answer()
    
    # Парсим действие и имя контейнера
    parts = query.data.split('_', 2)
    if len(parts) < 3:
        await query.edit_message_text("❌ Ошибка: неверный формат данных")
        return
    
    action = parts[1]
    container = parts[2]

    if not is_valid_docker_container_name(container):
        await query.edit_message_text(
            "❌ Некорректное имя Docker-контейнера"
        )
        return
    
    try:
        if action == 'start':
            result = subprocess.run(
                ['docker', 'start', container],
                capture_output=True,
                text=True,
                timeout=30
            )
            message = f"✅ Контейнер `{escape_markdown(container)}` запущен" if result.returncode == 0 else f"❌ Ошибка: {result.stderr}"
            
        elif action == 'stop':
            result = subprocess.run(
                ['docker', 'stop', container],
                capture_output=True,
                text=True,
                timeout=30
            )
            message = f"✅ Контейнер `{escape_markdown(container)}` остановлен" if result.returncode == 0 else f"❌ Ошибка: {result.stderr}"
            
        elif action == 'restart':
            result = subprocess.run(
                ['docker', 'restart', container],
                capture_output=True,
                text=True,
                timeout=60
            )
            message = f"✅ Контейнер `{escape_markdown(container)}` перезапущен" if result.returncode == 0 else f"❌ Ошибка: {result.stderr}"
            
        elif action == 'logs':
            result = subprocess.run(
                ['docker', 'logs', '--tail', '30', container],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.warning(
                    "Docker logs failed for %s (exit=%s)",
                    container,
                    result.returncode
                )
                keyboard = [[InlineKeyboardButton(
                    "🔙 Назад",
                    callback_data=f"docker_{container}"
                )]]
                await query.edit_message_text(
                    "❌ Не удалось получить журнал Docker-контейнера",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

            logs = result.stdout if result.stdout else result.stderr

            if not logs.strip():
                keyboard = [[InlineKeyboardButton(
                    "🔙 Назад",
                    callback_data=f"docker_{container}"
                )]]
                await query.edit_message_text(
                    "ℹ️ Журнал Docker-контейнера пуст",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            # Ограничиваем длину и экранируем
            logs = logs[-2000:] if len(logs) > 2000 else logs
            logs = html.escape(logs)
            
            message = f"📊 <b>Логи контейнера</b> <code>{html.escape(container)}</code>:\n\n<pre>{logs}</pre>"
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=f'docker_{container}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            return
        else:
            await query.edit_message_text(
                "❌ Неизвестное действие Docker"
            )
            return
        
        if result.returncode == 0:
            logger.info(
                "Docker %s на %s: успешно",
                action,
                container
            )
        else:
            logger.warning(
                "Docker %s на %s: ошибка, exit=%s",
                action,
                container,
                result.returncode
            )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='docker_list')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        
    except subprocess.TimeoutExpired:
        await query.edit_message_text(f"❌ Таймаут при выполнении {action}")
    except FileNotFoundError:
        await query.edit_message_text(
            "ℹ️ Docker не установлен на этом сервере",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]])
        )
    except Exception as e:
        logger.error(f"Ошибка Docker {action} для {container}: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ============================================
# СИСТЕМНАЯ ИНФОРМАЦИЯ
# Детальная информация о сервере: ОС, сеть, версии ПО
# ============================================

async def show_sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает детальную системную информацию.
    Включает: hostname, ОС, ядро, версии Python/Docker,
    сетевые настройки (IP, шлюз, DNS, MAC-адреса).
    """
    query = update.callback_query
    await query.answer()
    
    try:
        # Базовая информация о системе
        uname = os.uname()
        hostname = uname.nodename
        kernel = uname.release
        
        # Информация об ОС
        os_name = "Unknown"
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        os_name = line.split('=')[1].strip().strip('"')
                        break
        
        # Версии ПО
        python_version = subprocess.run(
            ['python3', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        ).stdout.strip()
        
        try:
            docker_version = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            ).stdout.strip()
            if not docker_version:
                docker_version = "не установлен"
        except FileNotFoundError:
            docker_version = "не установлен"
        
        # Сетевые настройки
        net_info = "\n🌐 *Сетевые настройки:*\n"
        
        # Основной IP
        ip_result = subprocess.run(
            ['hostname', '-I'],
            capture_output=True,
            text=True,
            timeout=5
        )
        main_ip = ip_result.stdout.strip().split()[0] if ip_result.stdout.strip() else "N/A"
        net_info += f"  └ IP адрес: `{main_ip}`\n"
        
        # Шлюз по умолчанию
        gateway_result = subprocess.run(
            ['ip', 'route', 'show', 'default'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if gateway_result.stdout:
            parts = gateway_result.stdout.split()
            if len(parts) >= 5:
                gw_ip = parts[2]
                gw_iface = parts[4]
                net_info += f"  └ Шлюз: `{gw_ip}` ({gw_iface})\n"
        
        # DNS серверы
        dns_servers = []
        if os.path.exists('/etc/resolv.conf'):
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.startswith('nameserver'):
                        dns_servers.append(line.split()[1])
        if dns_servers:
            net_info += f"  └ DNS: `{', '.join(dns_servers[:3])}`\n"
        
        # MAC адреса основных интерфейсов
        net_info += f"  └ MAC адреса:\n"
        for iface_name in os.listdir('/sys/class/net/'):
            if iface_name == 'lo' or iface_name.startswith('veth') or iface_name.startswith('br-'):
                continue
            mac_path = f'/sys/class/net/{iface_name}/address'
            if os.path.exists(mac_path):
                with open(mac_path, 'r') as f:
                    mac = f.read().strip()
                    if mac and mac != '00:00:00:00:00:00':
                        net_info += f"      ├ {iface_name}: `{mac}`\n"
        
        # Статистика сетевых ошибок
        net_stats = psutil.net_io_counters(pernic=True)
        errors_found = False
        errors_info = ""
        for iface, stats in net_stats.items():
            if iface == 'lo' or iface.startswith('veth'):
                continue
            if stats.errin > 0 or stats.errout > 0 or stats.dropin > 0 or stats.dropout > 0:
                if not errors_found:
                    errors_info = "  └ Ошибки сети:\n"
                    errors_found = True
                errors_info += f"      ├ {iface}: err={stats.errin}/{stats.errout}, drop={stats.dropin}/{stats.dropout}\n"
        
        if errors_found:
            net_info += errors_info
        
        message = (
            f"📋 *СИСТЕМНАЯ ИНФОРМАЦИЯ*\n\n"
            f"🖥 *Хост:* `{hostname}`\n"
            f"💿 *ОС:* {os_name}\n"
            f"🔧 *Ядро:* `{kernel}`\n"
            f"🐍 *Python:* {python_version}\n"
            f"🐳 *Docker:* {docker_version}\n"
            f"{net_info}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения системной информации: {e}")
        message = f"❌ Ошибка получения информации: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

# ============================================
# ОБНОВЛЕНИЕ СИСТЕМЫ
# Управление пакетами через apt: проверка, обновление, исправление
# ============================================


# Общая блокировка пакетных операций внутри процесса Admin Bot.
# Не заменяет системные блокировки apt/dpkg.
import threading as _package_threading
from functools import wraps as _package_wraps

_PACKAGE_OPERATION_LOCK = _package_threading.Lock()


def _package_operation_guard(handler):
    @_package_wraps(handler)
    async def guarded(update, context):
        query = update.callback_query

        # Просмотр обновлений и запрос подтверждения не изменяют пакеты.
        if (
            handler.__name__ == "update_action"
            and query.data != "update_refresh"
        ):
            return await handler(update, context)

        if not _PACKAGE_OPERATION_LOCK.acquire(blocking=False):
            await query.answer()
            await query.edit_message_text(
                "⚠️ Другая пакетная операция уже выполняется. "
                "Повторите запрос после её завершения.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🔙 Назад", callback_data="update_system"
                    )
                ]])
            )
            return

        try:
            return await handler(update, context)
        finally:
            _PACKAGE_OPERATION_LOCK.release()

    return guarded


async def update_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главное меню управления обновлениями системы.
    Показывает дату последнего обновления и предоставляет
    кнопки для проверки, обновления и исправления пакетов.
    """
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_package_action", None)
    
    # Информация о последнем обновлении
    last_update = "Неизвестно"
    try:
        if os.path.exists('/var/log/apt/history.log'):
            with open('/var/log/apt/history.log', 'r') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if 'Start-Date:' in line:
                        last_update = line.replace('Start-Date:', '').strip()
                        break
    except Exception as e:
        logger.warning(f"Не удалось прочитать историю apt: {e}")
    
    keyboard = [
        [InlineKeyboardButton("📦 Проверить обновления", callback_data='update_check')],
        [InlineKeyboardButton("🔄 Обновить список пакетов", callback_data='update_refresh')],
        [InlineKeyboardButton("⬆️ Обновить все пакеты", callback_data='update_upgrade')],
        [InlineKeyboardButton("🔧 Исправить проблемы", callback_data='request_fix_broken')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📦 *УПРАВЛЕНИЕ ОБНОВЛЕНИЯМИ*\n\n"
        f"Последнее обновление: {last_update}\n\n"
        f"Выберите действие:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


@_package_operation_guard
async def update_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик действий с обновлениями.
    Поддерживает: refresh (apt update), check (список обновлений),
    upgrade (запрос подтверждения обновления).
    """
    query = update.callback_query
    await query.answer()
    
    action = query.data.replace('update_', '')
    
    if action == 'refresh':
        # Обновление списка пакетов
        await query.edit_message_text("🔄 *Обновление списка пакетов...*", parse_mode='Markdown')
        
        try:
            result = subprocess.run(
                ['apt', 'update'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                message = "✅ Список пакетов успешно обновлен"
            else:
                message = "❌ Не удалось обновить список пакетов. Проверьте журнал службы."
        except subprocess.TimeoutExpired:
            message = "❌ Таймаут при обновлении списка пакетов"
        except Exception as e:
            logger.error(
                "SYS-03: update_refresh exception, type=%s",
                type(e).__name__
            )
            message = "❌ Ошибка обновления списка пакетов."
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif action == 'check':
        # Проверка доступных обновлений
        try:
            result = subprocess.run(
                ['apt', 'list', '--upgradable'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(
                    "SYS-03: update_check failed, exit=%s",
                    result.returncode
                )
                await query.edit_message_text(
                    "❌ Не удалось проверить доступные обновления.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "🔙 Назад", callback_data="update_system"
                        )
                    ]])
                )
                return

            lines = result.stdout.split('\n')
            updates = [line for line in lines if '/' in line and 'Listing' not in line]
            
            if updates:
                message = f"📦 *Доступные обновления ({len(updates)}):*\n\n```\n"
                message += "\n".join(updates[:15])
                message += "\n```"
                if len(updates) > 15:
                    message += f"\n... и еще {len(updates) - 15} пакетов"
                
                keyboard = [
                    [InlineKeyboardButton("⬆️ Обновить все", callback_data='update_upgrade')],
                    [InlineKeyboardButton("🔙 Назад", callback_data='update_system')]
                ]
            else:
                message = "✅ Система полностью обновлена"
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
            
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            
        except subprocess.TimeoutExpired:
            logger.error("SYS-03: update_check timeout")
            await query.edit_message_text(
                "❌ Превышено время ожидания проверки обновлений."
            )
        except Exception as e:
            logger.error(
                "SYS-03: update_check exception, type=%s",
                type(e).__name__
            )
            await query.edit_message_text(
                "❌ Не удалось проверить доступные обновления."
            )
        
    elif action == 'upgrade':
        # Запрос подтверждения обновления
        import time
        # Новый запрос отменяет предыдущее разрешение.
        context.user_data.pop("pending_package_action", None)

        keyboard = [
            [InlineKeyboardButton("✅ Да, обновить все", callback_data='confirm_upgrade')],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data='update_system')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ *ВНИМАНИЕ!*\n\n"
            "Обновление всех пакетов может занять некоторое время.\n"
            "Некоторые сервисы могут быть перезапущены.\n\n"
            "Продолжить?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

        context.user_data["pending_package_action"] = {
            "action": "upgrade",
            "chat_id": query.message.chat.id,
            "message_id": query.message.message_id,
            "expires_at": time.monotonic() + 60,
        }


@_package_operation_guard
async def confirm_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выполняет полное обновление системы.
    Последовательно: apt update, apt upgrade, проверка доступных обновлений.
    """
    query = update.callback_query
    await query.answer()

    import time
    pending = context.user_data.pop("pending_package_action", None)
    valid = (
        isinstance(pending, dict)
        and pending.get("action") == "upgrade"
        and pending.get("chat_id") == query.message.chat.id
        and pending.get("message_id") == query.message.message_id
        and isinstance(pending.get("expires_at"), (int, float))
        and time.monotonic() <= pending["expires_at"]
    )
    if not valid:
        logger.warning("SYS-03: upgrade rejected without confirmation")
        await query.edit_message_text(
            "❌ Подтверждение обновления отсутствует, "
            "истекло или уже использовано.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🔙 Назад", callback_data="update_system"
                )
            ]])
        )
        return
    
    await query.edit_message_text(
        "🔄 *Обновление системы...*\n\n"
        "1️⃣ Обновление списка пакетов...",
        parse_mode='Markdown'
    )
    
    env = os.environ.copy()
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    
    try:
        # Шаг 1: apt update
        update_result = subprocess.run(
            ['apt', 'update'],
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )
        
        if update_result.returncode != 0:
            logger.error(
                "SYS-03: upgrade apt update failed, exit=%s",
                update_result.returncode
            )
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
            await query.edit_message_text(
                "❌ Не удалось обновить список пакетов. Дальнейшие операции остановлены.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Шаг 2: apt upgrade
        await query.edit_message_text(
            "🔄 *Обновление системы...*\n\n"
            "✅ Список пакетов обновлен\n"
            "2️⃣ Установка обновлений (upgrade)...",
            parse_mode='Markdown'
        )
        
        upgrade_result = subprocess.run(
            ['apt-get', '--no-remove', 'upgrade', '-y', '-o', 'Dpkg::Options::=--force-confdef', '-o', 'Dpkg::Options::=--force-confold'],
            capture_output=True,
            text=True,
            timeout=600,
            env=env
        )

        if upgrade_result.returncode != 0:
            logger.error(
                "SYS-03: %s failed, exit=%s",
                "upgrade", upgrade_result.returncode
            )
            await query.edit_message_text(
                '❌ Ошибка выполнения этапа upgrade. Дальнейшие операции остановлены. Проверьте состояние пакетного менеджера.',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🔙 Назад", callback_data="update_system"
                    )
                ]])
            )
            return
        
        # Проверка результата
        check_result = subprocess.run(
            ['apt', 'list', '--upgradable'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if check_result.returncode != 0:
            logger.error(
                "SYS-03: %s failed, exit=%s",
                "list", check_result.returncode
            )
            await query.edit_message_text(
                '❌ Ошибка выполнения этапа list. Дальнейшие операции остановлены. Проверьте состояние пакетного менеджера.',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🔙 Назад", callback_data="update_system"
                    )
                ]])
            )
            return
        remaining = [line for line in check_result.stdout.split('\n') if '/' in line and 'Listing' not in line]
        
        if remaining:
            message = (
                "⚠️ *Стандартное обновление завершено*\n\n"
                f"Осталось доступных обновлений: {len(remaining)}.\n"
                "Для их установки требуется отдельная проверка."
            )
        else:
            message = "✅ *Стандартное обновление пакетов завершено.*"

        logger.info("Обновление системы завершено")
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    except subprocess.TimeoutExpired:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
        await query.edit_message_text(
            "❌ Таймаут при обновлении. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(
            "SYS-03: upgrade exception, type=%s",
            type(e).__name__
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
        await query.edit_message_text(
            "❌ Ошибка обновления системы. Проверьте журнал службы.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )



async def request_fix_broken(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает подтверждение исправления пакетов."""
    import time

    query = update.callback_query
    await query.answer()

    context.user_data.pop("pending_package_action", None)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Да, исправить пакеты", callback_data="fix_broken"
        )],
        [InlineKeyboardButton(
            "❌ Нет, отмена", callback_data="update_system"
        )],
    ])

    await query.edit_message_text(
        "⚠️ *ВНИМАНИЕ!*\n\n"
        "Будет выполнена команда apt-get --no-remove -f install -y.\n"
        "Автоматический dist-upgrade не выполняется.\n"
        "Возможны установка и обновление пакетов "
        "и перезапуск служб. Удаление пакетов запрещено.\n\n"
        "Продолжить?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

    context.user_data["pending_package_action"] = {
        "action": "fix_broken",
        "chat_id": query.message.chat.id,
        "message_id": query.message.message_id,
        "expires_at": time.monotonic() + 60,
    }

@_package_operation_guard
async def fix_broken_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Исправляет проблемные пакеты.
    Выполняет: apt --fix-broken install.
    """
    query = update.callback_query
    await query.answer()

    import time
    pending = context.user_data.pop("pending_package_action", None)
    valid = (
        isinstance(pending, dict)
        and pending.get("action") == "fix_broken"
        and pending.get("chat_id") == query.message.chat.id
        and pending.get("message_id") == query.message.message_id
        and isinstance(pending.get("expires_at"), (int, float))
        and time.monotonic() <= pending["expires_at"]
    )

    if not valid:
        logger.warning("SYS-03: fix_broken rejected without confirmation")
        await query.edit_message_text(
            "❌ Подтверждение исправления пакетов отсутствует, "
            "истекло или уже использовано.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🔙 Назад", callback_data="update_system"
                )
            ]])
        )
        return

    
    await query.edit_message_text(
        "🔧 *Исправление проблемных пакетов...*",
        parse_mode='Markdown'
    )
    
    env = os.environ.copy()
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    
    try:
        # Шаг 1: --fix-broken
        fix_result = subprocess.run(
            ['apt-get', '--no-remove', '-f', 'install', '-y'],
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )

        if fix_result.returncode != 0:
            logger.error(
                "SYS-03: %s failed, exit=%s",
                "--fix-broken", fix_result.returncode
            )
            await query.edit_message_text(
                '❌ Ошибка выполнения этапа --fix-broken. Дальнейшие операции остановлены. Проверьте состояние пакетного менеджера.',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🔙 Назад", callback_data="update_system"
                    )
                ]])
            )
            return
        
        message = (
            "✅ *Команда исправления зависимостей выполнена успешно.*"
        )

        logger.info("Исправление пакетов завершено")
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    except subprocess.TimeoutExpired:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
        await query.edit_message_text("❌ Таймаут", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(
            "SYS-03: fix_broken exception, type=%s",
            type(e).__name__
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='update_system')]]
        await query.edit_message_text("❌ Ошибка исправления пакетов. Проверьте журнал службы.", reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# ПРОСМОТР ЛОГОВ
# Чтение и отображение различных системных логов
# ============================================

async def logs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Меню выбора логов для просмотра.
    Динамически проверяет наличие лог-файлов и показывает только существующие.
    """
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    
    # Системные логи
    if os.path.exists('/var/log/syslog'):
        keyboard.append([InlineKeyboardButton("📋 Системные (syslog)", callback_data='logs_syslog')])
    
    if os.path.exists('/var/log/auth.log'):
        keyboard.append([InlineKeyboardButton("🔐 SSH (auth.log)", callback_data='logs_auth')])
    
    if os.path.exists('/var/log/fail2ban.log'):
        keyboard.append([InlineKeyboardButton("🛡️ Fail2ban", callback_data='logs_fail2ban')])
    
    # Docker логи
    docker_check = subprocess.run(['which', 'docker'], capture_output=True, text=True)
    if docker_check.returncode == 0:
        keyboard.append([InlineKeyboardButton("🐳 Docker контейнеры", callback_data='logs_docker')])
    
    # Дополнительные логи
    if os.path.exists('/var/log/apt/history.log'):
        keyboard.append([InlineKeyboardButton("📦 APT история", callback_data='logs_apt')])
    
    if os.path.exists('/var/log/kern.log'):
        keyboard.append([InlineKeyboardButton("🔧 Ядро (kern.log)", callback_data='logs_kern')])
    
    # Свой путь
    keyboard.append([InlineKeyboardButton("📝 Указать путь вручную", callback_data='logs_custom')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📁 *ПРОСМОТР ЛОГОВ*\n\n"
        "Выберите лог для просмотра:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает содержимое выбранного лог-файла.
    Показывает последние 50 строк лога.
    """
    query = update.callback_query
    await query.answer()
    
    log_type = query.data.replace('logs_', '')
    
    # Маппинг типов логов на файлы
    log_paths = {
        'syslog': '/var/log/syslog',
        'auth': '/var/log/auth.log',
        'fail2ban': '/var/log/fail2ban.log',
        'apt': '/var/log/apt/history.log',
        'kern': '/var/log/kern.log'
    }
    
    if log_type == 'custom':
        # Запрос пользовательского пути
        context.user_data['awaiting_log_path'] = True
        await query.edit_message_text(
            "📝 *Введите путь к лог-файлу*\n\n"
            "Например: `/var/log/nginx/error.log`\n\n"
            "Или отправьте /cancel для отмены.",
            parse_mode='Markdown'
        )
        return
    
    elif log_type == 'docker':
        # Показываем список контейнеров для выбора
        try:
            result = subprocess.run(
                ['docker', 'ps', '-a', '--format', '{{.Names}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            containers = [c for c in result.stdout.strip().split('\n') if c]
            
            if not containers:
                await query.edit_message_text(
                    "❌ Нет Docker контейнеров",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='logs_menu')]])
                )
                return
            
            keyboard = []
            for container in containers:
                keyboard.append([InlineKeyboardButton(f"🐳 {container}", callback_data=f'docker_logs_{container}')])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='logs_menu')])
            
            await query.edit_message_text(
                "🐳 *Логи Docker контейнеров*\n\n"
                "Выберите контейнер:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
            
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {str(e)}")
            return
    
    elif log_type in log_paths:
        log_path = log_paths[log_type]
        await show_file_log(query, log_path, log_type)
    
    else:
        await query.edit_message_text("❌ Неизвестный тип лога")


def read_safe_log(value: str, max_lines: int = 50) -> str:
    """Безопасно читает последние строки обычного файла внутри /var/log."""
    import stat
    from contextlib import ExitStack

    if not isinstance(value, str) or not os.path.isabs(value):
        raise ValueError("Недопустимый путь к журналу")

    if "\x00" in value:
        raise ValueError("Недопустимый путь к журналу")

    base = "/var/log"
    path = os.path.normpath(value)

    try:
        relative = os.path.relpath(path, base)
        if relative == "." or relative == ".." or relative.startswith("../"):
            raise ValueError("Доступ к файлу запрещён")
    except ValueError:
        raise ValueError("Доступ к файлу запрещён") from None

    parts = relative.split(os.sep)

    directory_flags = (
        os.O_RDONLY | os.O_DIRECTORY |
        os.O_NOFOLLOW | os.O_CLOEXEC
    )
    file_flags = (
        os.O_RDONLY | os.O_NOFOLLOW |
        os.O_CLOEXEC | os.O_NONBLOCK
    )

    with ExitStack() as stack:
        directory_fd = os.open(base, directory_flags)
        stack.callback(os.close, directory_fd)

        for component in parts[:-1]:
            next_fd = os.open(
                component, directory_flags, dir_fd=directory_fd
            )
            stack.callback(os.close, next_fd)
            directory_fd = next_fd

        fd = os.open(parts[-1], file_flags, dir_fd=directory_fd)
        stack.callback(os.close, fd)

        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Разрешено чтение только обычных файлов")

        limit = 256 * 1024
        size = min(info.st_size, limit)
        offset = max(0, info.st_size - size)

        data = os.pread(fd, size, offset)

    content = data.decode("utf-8", errors="replace")
    return "\n".join(content.splitlines()[-max_lines:])


async def show_file_log(query, log_path: str, log_type: str = None):
    """
    Вспомогательная функция для отображения содержимого лог-файла.
    Читает последние 50 строк файла и форматирует для Telegram.
    """
    try:
        log_content = read_safe_log(log_path)

        # Ограничиваем длину сообщения Telegram
        if len(log_content) > 3000:
            log_content = log_content[-3000:]

        # Сохраняем существующее форматирование

        filename = os.path.basename(log_path)
        message = f"📁 <b>{html.escape(filename)}</b>\n\n<pre>{html.escape(log_content)}</pre>"

        # Определяем callback для кнопки обновления
        refresh_callback = f'logs_{log_type}' if log_type else 'logs_menu'
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data=refresh_callback)],
            [InlineKeyboardButton("🔙 Назад", callback_data='logs_menu')]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except (ValueError, OSError) as e:
        logger.warning("Отказ при чтении журнала: %s", type(e).__name__)
        keyboard = [[InlineKeyboardButton(
            "🔙 Назад", callback_data="logs_menu"
        )]]
        await query.edit_message_text(
            "❌ Доступ к файлу запрещён или файл недоступен",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка чтения лога {log_path}: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ============================================
# ГРАФИКИ НАГРУЗКИ
# Визуализация нагрузки CPU/RAM с использованием emoji-графиков
# ============================================

async def show_graphs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Меню выбора периода для отображения графиков нагрузки.
    """
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📊 1 час", callback_data='graph_1h')],
        [InlineKeyboardButton("📊 8 часов", callback_data='graph_8h')],
        [InlineKeyboardButton("📊 24 часа", callback_data='graph_24h')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📊 *ГРАФИКИ НАГРУЗКИ*\n\n"
        "Выберите период:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def show_graph(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает график нагрузки за выбранный период.
    Использует emoji для визуализации уровня загрузки.
    Показывает: CPU по ядрам, RAM, Load Average.
    Пытается получить историю из sar (sysstat), если доступно.
    """
    query = update.callback_query
    await query.answer()
    
    period = query.data.replace('graph_', '')
    
    periods = {
        '1h': ('последний час', 60),
        '8h': ('последние 8 часов', 480),
        '24h': ('последние 24 часа', 1440)
    }
    
    period_name, minutes = periods.get(period, ('неизвестный период', 60))
    
    # Текущая нагрузка
    cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
    cpu_avg = sum(cpu_percent) / len(cpu_percent)
    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    mem_used = mem.used / (1024**3)
    mem_total = mem.total / (1024**3)
    load_avg = psutil.getloadavg()
    
    def create_bar(percent, width=15):
        """
        Создаёт emoji-полоску для визуализации процента.
        Цвет зависит от уровня: зелёный < 25%, жёлтый < 50%, оранжевый < 75%, красный >= 75%
        """
        filled = int(percent * width / 100)
        if percent < 25:
            bar = "🟩" * filled + "⬜" * (width - filled)
        elif percent < 50:
            bar = "🟨" * filled + "⬜" * (width - filled)
        elif percent < 75:
            bar = "🟧" * filled + "⬜" * (width - filled)
        else:
            bar = "🟥" * filled + "⬜" * (width - filled)
        return bar
    
    # Пытаемся получить историю из sar
    history = ""
    sar_available = False
    
    if os.path.exists('/usr/bin/sar') and os.path.exists('/var/log/sysstat'):
        try:
            time_delta = {
                '1h': timedelta(hours=1),
                '8h': timedelta(hours=8),
                '24h': timedelta(hours=24)
            }
            start_time = (datetime.now() - time_delta[period]).strftime('%H:%M:%S')
            
            sar_result = subprocess.run(
                ['sar', '-u', '-s', start_time],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if sar_result.returncode == 0 and sar_result.stdout:
                lines = sar_result.stdout.split('\n')
                max_cpu = 0
                avg_cpu = 0
                count = 0
                
                for line in lines:
                    if 'Average:' in line:
                        parts = line.split()
                        if len(parts) >= 8:
                            try:
                                user = float(parts[2])
                                system = float(parts[4])
                                avg_cpu = user + system
                            except ValueError:
                                pass
                    elif line and line[0].isdigit():
                        parts = line.split()
                        if len(parts) >= 8:
                            try:
                                user = float(parts[2])
                                system = float(parts[4])
                                total = user + system
                                if total > max_cpu:
                                    max_cpu = total
                                count += 1
                            except ValueError:
                                pass
                
                if count > 0:
                    sar_available = True
                    history = (
                        f"\n📊 *Статистика за {period_name}:*\n"
                        f"├ Средняя нагрузка CPU: {avg_cpu:.1f}%\n"
                        f"├ Максимальная нагрузка: {max_cpu:.1f}%\n"
                        f"└ Измерений: {count}\n"
                    )
        except Exception as e:
            logger.debug(f"sar недоступен: {e}")
    
    if not sar_available:
        # Альтернативная статистика из /proc/loadavg
        try:
            with open('/proc/loadavg', 'r') as f:
                load_data = f.read().strip().split()
            history = (
                f"\n📊 *Текущая статистика:*\n"
                f"├ Load average: {load_data[0]}, {load_data[1]}, {load_data[2]}\n"
                f"├ Активных процессов: {load_data[3].split('/')[0]}\n"
                f"└ Всего процессов: {load_data[3].split('/')[1]}\n"
            )
        except Exception:
            history = "\n📊 _Историческая статистика недоступна_\n"
    
    # Формируем сообщение
    cpu_bar = create_bar(cpu_avg)
    
    message = (
        f"📈 *График нагрузки за {period_name}*\n\n"
        f"⚡ *Процессор* ({len(cpu_percent)} ядер)\n"
        f"├ Общая: {cpu_avg:.1f}% {cpu_bar}\n"
    )
    
    # Информация по ядрам (компактно)
    for i, core in enumerate(cpu_percent):
        core_bar = create_bar(core, 10)
        message += f"├ Ядро {i+1}: {core:.1f}% {core_bar}\n"
    
    # RAM
    mem_bar = create_bar(mem_percent)
    message += (
        f"\n💾 *Память*\n"
        f"├ {mem_used:.1f}GB / {mem_total:.1f}GB ({mem_percent:.1f}%)\n"
        f"└ {mem_bar}\n"
    )
    
    # Load Average
    message += (
        f"\n📊 *Load Average*\n"
        f"├ 1 мин: {load_avg[0]:.2f}\n"
        f"├ 5 мин: {load_avg[1]:.2f}\n"
        f"└ 15 мин: {load_avg[2]:.2f}\n"
    )
    
    message += history
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data=f'graph_{period}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='graphs')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    except Exception as e:
        # Если сообщение слишком длинное, отправляем сокращённую версию
        logger.warning(f"Ошибка отправки графика, пробуем сокращённую версию: {e}")
        short_message = (
            f"📊 *Нагрузка за {period_name}*\n\n"
            f"CPU: {cpu_avg:.1f}% {create_bar(cpu_avg, 10)}\n"
            f"RAM: {mem_percent:.1f}% {create_bar(mem_percent, 10)}\n"
            f"Load: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}\n"
        )
        await query.edit_message_text(short_message, parse_mode='Markdown', reply_markup=reply_markup)

# ============================================
# ТЕСТ СКОРОСТИ СЕТИ
# Измерение скорости через iperf3
# ============================================

async def iperf_speedtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запускает тест скорости сети через внешний скрипт iperf3.
    Показывает статус выполнения и результаты теста.
    """
    query = update.callback_query
    await query.answer()
    
    # Сообщаем о начале теста
    await query.edit_message_text(
        "📡 *Запуск теста скорости...*\n\n"
        "⏱️ Тест может занять до 30 секунд...",
        parse_mode='Markdown'
    )
    
    try:
        result = subprocess.run(
            ['speedtest-iperf.sh'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            output = result.stdout
            # Убираем лишние пустые строки
            output = '\n'.join([line for line in output.split('\n') if line.strip()])
        else:
            output = result.stdout + "\n" + result.stderr if result.stderr else result.stdout
        
        # Ограничиваем длину и экранируем
        if len(output) > 3500:
            output = output[:3500] + "\n\n... (вывод обрезан)"
        
        output = output.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
        
        message = f"📊 *РЕЗУЛЬТАТ ТЕСТА СКОРОСТИ*\n\n```\n{output}\n```"
        
    except subprocess.TimeoutExpired:
        message = "❌ *Таймаут*\n\nТест скорости занял слишком много времени.\nПопробуйте позже."
    except FileNotFoundError:
        message = "❌ *Ошибка*\n\nСкрипт speedtest-iperf.sh не найден."
    except Exception as e:
        logger.error(f"Ошибка теста скорости: {e}")
        message = f"❌ *Ошибка*\n\n{str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        await context.bot.send_message(
            chat_id=ALLOWED_USER_ID,
            text=message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )


# ============================================
# ПЕРЕЗАГРУЗКА И ВЫКЛЮЧЕНИЕ СЕРВЕРА
# Управление питанием сервера с подтверждением
# ============================================

async def confirm_reboot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает одноразовое подтверждение перезагрузки."""
    import time

    query = update.callback_query
    await query.answer()

    # Старое разрешение недействительно после нового запроса.
    context.user_data.pop("pending_power_action", None)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Да, перезагрузить", callback_data="execute_reboot"
        )],
        [InlineKeyboardButton(
            "❌ Нет, отмена", callback_data="execute_power_cancel"
        )]
    ])

    await query.edit_message_text(
        "⚠️ *ВНИМАНИЕ!*\n\n"
        "Вы действительно хотите перезагрузить сервер?\n\n"
        "Все активные соединения будут разорваны.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

    context.user_data["pending_power_action"] = {
        "action": "reboot",
        "chat_id": query.message.chat.id,
        "message_id": query.message.message_id,
        "expires_at": time.monotonic() + 60,
    }


async def confirm_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает одноразовое подтверждение выключения."""
    import time

    query = update.callback_query
    await query.answer()

    context.user_data.pop("pending_power_action", None)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Да, выключить", callback_data="execute_shutdown"
        )],
        [InlineKeyboardButton(
            "❌ Нет, отмена", callback_data="execute_power_cancel"
        )]
    ])

    await query.edit_message_text(
        "⚠️ *ВНИМАНИЕ!*\n\n"
        "Вы действительно хотите ВЫКЛЮЧИТЬ сервер?\n\n"
        "⛔ Для включения потребуется физический доступ!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

    context.user_data["pending_power_action"] = {
        "action": "shutdown",
        "chat_id": query.message.chat.id,
        "message_id": query.message.message_id,
        "expires_at": time.monotonic() + 60,
    }


async def execute_power_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет подтверждённую однократную операцию питания."""
    import time

    query = update.callback_query
    await query.answer()

    action = query.data.removeprefix("execute_")

    # Разрешение уничтожается при первом обращении к обработчику.
    pending = context.user_data.pop("pending_power_action", None)

    if action == "power_cancel":
        await query.edit_message_text(
            "❌ Операция отменена",
            reply_markup=main_menu_keyboard()
        )
        return

    commands = {
        "reboot": ["systemctl", "reboot"],
        "shutdown": ["systemctl", "poweroff"],
    }

    if action not in commands:
        await query.edit_message_text(
            "❌ Недопустимая операция",
            reply_markup=main_menu_keyboard()
        )
        return

    valid = (
        isinstance(pending, dict)
        and pending.get("action") == action
        and pending.get("chat_id") == query.message.chat.id
        and pending.get("message_id") == query.message.message_id
        and isinstance(pending.get("expires_at"), (int, float))
        and time.monotonic() <= pending["expires_at"]
    )

    if not valid:
        logger.warning(
            "Отклонена операция питания без действительного подтверждения: %s",
            action
        )
        await query.edit_message_text(
            "❌ Подтверждение отсутствует, уже использовано "
            "или срок его действия истёк.",
            reply_markup=main_menu_keyboard()
        )
        return

    description = (
        "перезагрузки" if action == "reboot" else "выключения"
    )

    # Если Telegram не принимает предупреждение, команда не запускается.
    await query.edit_message_text(
        f"⚠️ Подготовка {description} сервера.\n\n"
        "Отправка системной команды через 5 секунд."
    )

    logger.warning("Подтверждена операция питания: %s", action)
    await asyncio.sleep(5)

    try:
        result = subprocess.run(
            commands[action],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.error(
                "Команда питания завершилась с ошибкой: action=%s, exit=%s",
                action, result.returncode
            )
            message = (
                "❌ Ошибка отправки системной команды. "
                "Проверьте состояние сервера."
            )
        else:
            logger.warning(
                "Системная команда питания принята: %s", action
            )
            message = (
                "✅ Системная команда отправлена.\n"
                "Фактическое состояние сервера необходимо проверить."
            )

    except subprocess.TimeoutExpired:
        logger.error("Таймаут системной команды питания: %s", action)
        message = (
            "⚠️ Превышено время ожидания системной команды. "
            "Результат неизвестен."
        )

    except Exception as e:
        logger.error(
            "Ошибка системной команды питания: action=%s, type=%s",
            action, type(e).__name__
        )
        message = (
            "❌ Не удалось подтвердить выполнение системной команды."
        )

    try:
        await query.edit_message_text(message)
    except Exception as e:
        logger.warning(
            "Не удалось отправить результат операции питания: %s",
            type(e).__name__
        )
        # Повторный запуск systemctl запрещён.

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    
    context.user_data.pop("pending_power_action", None)
    context.user_data.pop("pending_package_action", None)

    # Сбрасываем все флаги ожидания
    was_unban = context.user_data.get('awaiting_unban_ip', False)

    context.user_data['awaiting_unban_ip'] = False
    context.user_data['awaiting_log_path'] = False
    context.user_data['awaiting_traceroute'] = False
    
    if was_unban:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔙 К списку заблокированных IP",
                callback_data="banned_ips"
            )]
        ])
    else:
        keyboard = main_menu_keyboard()

    await update.message.reply_text(
        "❌ Операция отменена",
        reply_markup=keyboard
    )

# ============================================
# ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ
# Обработка ввода пользователя (IP для разбана, путь к логам и т.д.)
# ============================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик текстовых сообщений от пользователя.
    Используется для:
    - Ввода IP-адреса для разбана
    - Ввода пути к лог-файлу
    - Ввода адреса для traceroute
    - Обработки команды /cancel
    """
    # Проверка авторизации
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    
    text = update.message.text.strip()
    
    # Обработка /cancel
    if text == '/cancel':
        context.user_data['awaiting_unban_ip'] = False
        context.user_data['awaiting_log_path'] = False
        context.user_data['awaiting_traceroute'] = False
        await update.message.reply_text(
            "❌ Операция отменена",
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Обработка ввода адреса для traceroute
    if context.user_data.get('awaiting_traceroute'):
        context.user_data['awaiting_traceroute'] = False
        target = text
        
        # Базовая валидация (IP или домен)
        if validate_traceroute_target(target):
            await execute_traceroute(update, context, target)
        else:
            await update.message.reply_text(
                "❌ Неверный формат адреса.\n\n"
                "Используйте IP или домен без спецсимволов.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "🔄 Повторить", callback_data="cmd_traceroute"
                    )],
                    [InlineKeyboardButton(
                        "🔙 К меню сети", callback_data="extra_network"
                    )]
                ])
            )
        return
    
    # Обработка ввода IP для разбана
    if context.user_data.get('awaiting_unban_ip'):
        # INPUT04_MANUAL_UNBAN
        import ipaddress

        try:
            ip = str(ipaddress.ip_address(text))
        except ValueError:
            await update.message.reply_text(
                "❌ Некорректный IP-адрес.\n\n"
                "Введите IPv4 или IPv6 либо отправьте /cancel."
            )
            return

        # Исключаем повторное выполнение при следующем сообщении.
        context.user_data['awaiting_unban_ip'] = False

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔙 К списку заблокированных IP",
                callback_data="banned_ips"
            )]
        ])

        try:
            result = subprocess.run(
                ['fail2ban-client', 'unban', ip],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning(
                    "Ручная разблокировка Fail2ban: exit=%s",
                    result.returncode
                )
                message = (
                    "❌ Ошибка выполнения разблокировки. "
                    "Результат необходимо проверить."
                )
            else:
                count_text = result.stdout.strip()

                if not count_text.isascii() or not count_text.isdecimal():
                    logger.warning(
                        "Неожиданный ответ ручной разблокировки Fail2ban: %r",
                        count_text[:100]
                    )
                    message = (
                        "⚠️ Команда разблокировки выполнена, "
                        "но количество снятых блокировок не подтверждено."
                    )
                else:
                    removed_count = int(count_text)

                    if removed_count == 0:
                        message = (
                            f"ℹ️ Для IP {ip} блокировок не обнаружено."
                        )
                    else:
                        logger.info(
                            "Ручная разблокировка Fail2ban: removed=%s",
                            removed_count
                        )
                        message = (
                            f"✅ IP {ip} разблокирован.\n\n"
                            f"Снято блокировок: {removed_count}"
                        )

        except subprocess.TimeoutExpired:
            logger.error("Таймаут ручной разблокировки Fail2ban")
            message = (
                "⚠️ Превышено время ожидания Fail2ban. "
                "Результат неизвестен — проверьте список блокировок."
            )

        except Exception as e:
            logger.error(
                "Ошибка ручной разблокировки Fail2ban: %s",
                type(e).__name__
            )
            message = (
                "❌ Не удалось подтвердить выполнение разблокировки."
            )

        await update.message.reply_text(
            message,
            reply_markup=keyboard
        )
        return

    # Обработка ввода пути к логу
    if context.user_data.get('awaiting_log_path'):
        log_path = text
        context.user_data['awaiting_log_path'] = False
        
        try:
            log_content = read_safe_log(log_path)

            if len(log_content) > 3000:
                log_content = log_content[-3000:]


            message = f"📁 <b>{html.escape(log_path)}</b>\n\n<pre>{html.escape(log_content)}</pre>"

            keyboard = [[InlineKeyboardButton(
                "🔙 Назад", callback_data='logs_menu'
            )]]

            await update.message.reply_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except (ValueError, OSError) as e:
            logger.warning(
                "Отказ при чтении пользовательского журнала: %s",
                type(e).__name__
            )
            await update.message.reply_text(
                "❌ Доступ к файлу запрещён или файл недоступен",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🔙 Назад", callback_data="logs_menu"
                    )
                ]])
            )

        except Exception as e:
            logger.error(
                "Ошибка обработки пользовательского журнала: %s",
                type(e).__name__
            )
            await update.message.reply_text(
                "❌ Ошибка при чтении журнала",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🔙 Назад", callback_data="logs_menu"
                    )
                ]])
            )

        return

# ============================================
# НАВИГАЦИЯ
# ============================================

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Возврат в главное меню из любого подменю.
    Используется кнопкой "🔙 Назад" во всех разделах.
    """
    query = update.callback_query
    await query.answer()

    context.user_data.pop("pending_power_action", None)
    context.user_data.pop("pending_package_action", None)
    context.user_data['awaiting_traceroute'] = False
    await query.edit_message_text("🤖 *Admin Bot v2*", reply_markup=main_menu_keyboard(), parse_mode='Markdown')

# ============================================
# ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ
# ============================================

def extra_menu_keyboard():
    """Меню дополнительных команд по категориям"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Сеть", callback_data='extra_network')],
        [InlineKeyboardButton("🛡️ Безопасность", callback_data='extra_security')],
        [InlineKeyboardButton("🔍 Диагностика", callback_data='extra_diagnostics')],
        [InlineKeyboardButton("🐳 Docker", callback_data='extra_docker')],
        [InlineKeyboardButton("📦 Система", callback_data='extra_system')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')],
    ])

def extra_network_keyboard():
    """Подменю: Сеть"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔌 Открытые порты", callback_data='cmd_open_ports')],
        [InlineKeyboardButton("🌍 Активные соединения", callback_data='cmd_active_connections')],
        [InlineKeyboardButton("🔐 SSH сессии", callback_data='cmd_ssh_sessions')],
        [InlineKeyboardButton("🔍 Trace route", callback_data='cmd_traceroute')],
        [InlineKeyboardButton("🔙 Назад", callback_data='extra_menu')],
    ])

def extra_security_keyboard():
    """Подменю: Безопасность"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Последние входы", callback_data='cmd_last_logins')],
        [InlineKeyboardButton("🔒 Sudo логи", callback_data='cmd_sudo_logs')],
        [InlineKeyboardButton("🔙 Назад", callback_data='extra_menu')],
    ])

def extra_diagnostics_keyboard():
    """Подменю: Диагностика"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔝 Top CPU процессы", callback_data='cmd_top_cpu')],
        [InlineKeyboardButton("💾 Top RAM процессы", callback_data='cmd_top_ram')],
        [InlineKeyboardButton("🔥 Zombie процессы", callback_data='cmd_zombie')],
        [InlineKeyboardButton("🧵 Thread count", callback_data='cmd_threads')],
        [InlineKeyboardButton("🗂️ Большие файлы", callback_data='cmd_big_files')],
        [InlineKeyboardButton("📉 I/O wait", callback_data='cmd_io_wait')],
        [InlineKeyboardButton("🧪 Test DNS", callback_data='cmd_test_dns')],
        [InlineKeyboardButton("🔙 Назад", callback_data='extra_menu')],
    ])

def extra_docker_keyboard():
    """Подменю: Docker"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Docker stats", callback_data='cmd_docker_stats')],
        [InlineKeyboardButton("📦 Images size", callback_data='cmd_docker_images')],
        [InlineKeyboardButton("🔙 Назад", callback_data='extra_menu')],
    ])

def extra_system_keyboard():
    """Подменю: Система"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Uptime", callback_data='cmd_uptime')],
        [InlineKeyboardButton("🔄 Systemd failed", callback_data='cmd_systemd_failed')],
        [InlineKeyboardButton("📦 Apt history", callback_data='cmd_apt_history')],
        [InlineKeyboardButton("🧹 Apt cache size", callback_data='cmd_apt_cache')],
        [InlineKeyboardButton("🔙 Назад", callback_data='extra_menu')],
    ])

# ============================================
# ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ - НАВИГАЦИЯ
# ============================================

async def show_extra_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню дополнительных команд"""
    query = update.callback_query
    await query.answer()

    context.user_data['awaiting_traceroute'] = False
    
    await query.edit_message_text(
        "➕ *ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ*\n\n"
        "Выберите категорию:",
        parse_mode='Markdown',
        reply_markup=extra_menu_keyboard()
    )

async def show_extra_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю: Сеть"""
    query = update.callback_query
    await query.answer()

    context.user_data['awaiting_traceroute'] = False
    
    await query.edit_message_text(
        "🌐 *СЕТЬ*\n\n"
        "Выберите команду:",
        parse_mode='Markdown',
        reply_markup=extra_network_keyboard()
    )

async def show_extra_security(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю: Безопасность"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🛡️ *БЕЗОПАСНОСТЬ*\n\n"
        "Выберите команду:",
        parse_mode='Markdown',
        reply_markup=extra_security_keyboard()
    )

async def show_extra_diagnostics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю: Диагностика"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔍 *ДИАГНОСТИКА*\n\n"
        "Выберите команду:",
        parse_mode='Markdown',
        reply_markup=extra_diagnostics_keyboard()
    )

async def show_extra_docker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю: Docker"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🐳 *DOCKER*\n\n"
        "Выберите команду:",
        parse_mode='Markdown',
        reply_markup=extra_docker_keyboard()
    )

async def show_extra_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подменю: Система"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📦 *СИСТЕМА И ПАКЕТЫ*\n\n"
        "Выберите команду:",
        parse_mode='Markdown',
        reply_markup=extra_system_keyboard()
    )

# ============================================
# ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ - РЕАЛИЗАЦИЯ
# ============================================

# --- СЕТЬ ---

async def cmd_open_ports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать открытые порты (ss -tlnp)"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['ss', '-tlnp'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout.strip()
        
        # Парсим вывод для красивого отображения
        lines = output.split('\n')
        if len(lines) > 1:
            message = "🔌 *ОТКРЫТЫЕ ПОРТЫ*\n\n```\n"
            # Ограничиваем вывод
            for line in lines[:20]:
                message += line[:80] + "\n"
            if len(lines) > 20:
                message += f"\n... и ещё {len(lines) - 20} строк\n"
            message += "```"
        else:
            message = "🔌 *ОТКРЫТЫЕ ПОРТЫ*\n\nНет открытых портов"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_open_ports: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_network')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_active_connections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ активных соединений по IP"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['ss', '-tn', 'state', 'established'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')[1:]  # Пропускаем заголовок
        
        ip_count = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                peer = parts[3]  # Исправлено: индекс 3, не 4
                # Обработка IPv6 [addr]:port и IPv4 addr:port
                if peer.startswith('['):
                    # IPv6: [2a0d:6c2:24:347::]:40052
                    match = re.match(r'\[([^\]]+)\]:(\d+)', peer)
                    if match:
                        ip = match.group(1)
                    else:
                        ip = peer
                else:
                    # IPv4: 185.254.158.38:22
                    ip = peer.rsplit(':', 1)[0]
                
                ip_count[ip] = ip_count.get(ip, 0) + 1
        
        if ip_count:
            sorted_ips = sorted(ip_count.items(), key=lambda x: x[1], reverse=True)[:15]
            
            message = "🌍 *АКТИВНЫЕ СОЕДИНЕНИЯ*\n\n"
            message += f"Всего соединений: {len(lines)}\n\n"
            message += "*Топ IP по количеству:*\n"
            for ip, count in sorted_ips:
                # Сокращаем длинные IPv6
                display_ip = ip if len(ip) <= 25 else ip[:22] + "..."
                message += f"`{display_ip}` — {count}\n"
        else:
            message = "🌍 *АКТИВНЫЕ СОЕДИНЕНИЯ*\n\nНет активных соединений"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_active_connections: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_network')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_ssh_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные SSH сессии"""
    query = update.callback_query
    await query.answer()
    
    try:
        # who показывает залогиненных пользователей
        result = subprocess.run(
            ['who'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')
        
        if lines and lines[0]:
            message = "🔐 *SSH СЕССИИ*\n\n"
            message += f"Активных сессий: {len(lines)}\n\n"
            message += "```\n"
            for line in lines:
                message += line + "\n"
            message += "```"
        else:
            message = "🔐 *SSH СЕССИИ*\n\n✅ Нет активных сессий"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_ssh_sessions: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_network')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_ssh_sessions_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные SSH сессии (возврат в меню безопасности)"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['who'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')
        
        if lines and lines[0]:
            message = "🔐 *SSH СЕССИИ*\n\n"
            message += f"Активных сессий: {len(lines)}\n\n"
            message += "```\n"
            for line in lines:
                message += line + "\n"
            message += "```"
        else:
            message = "🔐 *SSH СЕССИИ*\n\n✅ Нет активных сессий"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_ssh_sessions_sec: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_security')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать uptime системы"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Load average
        load_avg = psutil.getloadavg()
        
        # Количество пользователей
        users = len(psutil.users())
        
        message = "📅 *UPTIME*\n\n"
        message += f"🕐 *Время работы:* {days}д {hours}ч {minutes}м {seconds}с\n\n"
        message += f"📅 *Запущен:* {boot_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += f"📈 *Load Average:* {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}\n\n"
        message += f"👥 *Пользователей онлайн:* {users}"
            
    except Exception as e:
        logger.error(f"Ошибка cmd_uptime: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_system')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_systemd_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать упавшие systemd сервисы"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['systemctl', '--failed', '--no-pager', '--no-legend'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout.strip()
        
        if output:
            lines = output.split('\n')
            message = "🔄 *УПАВШИЕ СЕРВИСЫ*\n\n"
            message += f"❌ Найдено проблем: {len(lines)}\n\n"
            message += "```\n"
            for line in lines[:15]:
                message += line[:70] + "\n"
            if len(lines) > 15:
                message += f"\n... и ещё {len(lines) - 15}\n"
            message += "```"
        else:
            message = "🔄 *УПАВШИЕ СЕРВИСЫ*\n\n✅ Все сервисы работают нормально"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_systemd_failed: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_system')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_traceroute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос адреса для traceroute"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_traceroute'] = True
    
    await query.edit_message_text(
        "🔍 *TRACEROUTE*\n\n"
        "Введите IP-адрес или домен для трассировки:\n\n"
        "Например: `8.8.8.8` или `google.com`\n\n"
        "Для отмены отправьте /cancel",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔙 К меню сети", callback_data="extra_network"
            )]
        ])
    )

def validate_traceroute_target(value: str) -> bool:
    """Проверяет IPv4, IPv6 или допустимое DNS-имя."""
    import ipaddress

    if not isinstance(value, str) or not value:
        return False

    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        pass

    # Некорректный числовой IP нельзя принимать за DNS-имя.
    if re.fullmatch(r"[0-9.]+", value):
        return False

    if len(value) > 253 or not value.isascii():
        return False

    name = value.removesuffix(".")
    if not name:
        return False

    label_pattern = re.compile(
        r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    )

    return all(
        label_pattern.fullmatch(label)
        for label in name.split(".")
    )


async def execute_traceroute(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Выполнить traceroute к указанному адресу"""
    if not validate_traceroute_target(target):
        logger.warning("Отклонён недопустимый адрес traceroute")
        keyboard = [[InlineKeyboardButton(
            "🔙 К меню сети", callback_data="extra_network"
        )]]
        await update.message.reply_text(
            "❌ Неверный формат IP-адреса или имени хоста",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await update.message.reply_text(f"🔍 Выполняю traceroute к <code>{html.escape(target)}</code>...\nЭто может занять до 30 секунд.", parse_mode='HTML')

    try:
        result = subprocess.run(
            ['traceroute', '-m', '10', '-w', '1', '-q', '1', target],
            capture_output=True,
            text=True,
            timeout=45
        )

        output = result.stdout.strip()

        if result.returncode != 0:
            logger.warning(
                "Traceroute failed (exit=%s)",
                result.returncode
            )
            message = "❌ Ошибка выполнения traceroute"
        elif output:
            message = f"🔍 <b>TRACEROUTE → {html.escape(target)}</b>\n\n<pre>"
            lines = output.split('\n')
            for line in lines[:15]:
                message += html.escape(line[:65]) + "\n"
            if len(lines) > 15:
                message += f"\n... и ещё {len(lines) - 15} хопов\n"
            message += "</pre>"
        else:
            message = f"❌ Не удалось выполнить traceroute к {html.escape(target)}"
            if result.stderr:
                message += f"\n\n{html.escape(result.stderr)}"

    except subprocess.TimeoutExpired:
        message = "❌ Таймаут (45 сек). Хост может быть недоступен или блокирует ICMP."
    except FileNotFoundError:
        message = "❌ traceroute не установлен. Установите: <code>apt install traceroute</code>"
    except Exception as e:
        logger.error(f"Ошибка traceroute: {e}")
        message = "❌ Внутренняя ошибка выполнения traceroute"

    keyboard = [
        [InlineKeyboardButton(
            "🔄 Повторить", callback_data="cmd_traceroute"
        )],
        [InlineKeyboardButton(
            "🔙 К меню сети", callback_data="extra_network"
        )]
    ]
    await update.message.reply_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# --- БЕЗОПАСНОСТЬ ---

async def cmd_last_logins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние входы в систему"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['last', '-n', '15', '-a'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout.strip()
        
        if output:
            message = "👤 *ПОСЛЕДНИЕ ВХОДЫ*\n\n```\n"
            lines = output.split('\n')
            for line in lines[:15]:
                if line.strip():
                    message += line[:75] + "\n"
            message += "```"
        else:
            message = "👤 *ПОСЛЕДНИЕ ВХОДЫ*\n\nНет данных"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_last_logins: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_security')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_sudo_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние sudo команды"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Пробуем разные источники логов sudo
        log_files = ['/var/log/auth.log', '/var/log/secure']
        log_file = None
        
        for f in log_files:
            if os.path.exists(f):
                log_file = f
                break
        
        if log_file:
            result = subprocess.run(
                ['grep', '-a', 'sudo', log_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.strip().split('\n')
            # Берём последние 15 строк
            recent = [l for l in lines if l.strip()][-15:]
            
            if recent:
                message = "🔒 *SUDO ЛОГИ*\n\n```\n"
                for line in recent:
                    # Сокращаем длинные строки
                    message += line[:70] + "\n"
                message += "```"
            else:
                message = "🔒 *SUDO ЛОГИ*\n\n✅ Нет записей sudo"
        else:
            message = "🔒 *SUDO ЛОГИ*\n\n❌ Лог-файл не найден"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_sudo_logs: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_security')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# --- ДИАГНОСТИКА ---

async def cmd_top_cpu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ процессов по CPU"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['ps', 'aux', '--sort=-%cpu'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')
        
        message = "🔝 *TOP CPU ПРОЦЕССЫ*\n\n```\n"
        # Заголовок
        message += "CPU%  MEM%  COMMAND\n"
        message += "-" * 30 + "\n"
        
        # Топ 10 процессов (пропускаем заголовок)
        for line in lines[1:11]:
            parts = line.split()
            if len(parts) >= 11:
                cpu = parts[2]
                mem = parts[3]
                cmd = parts[10][:20]
                message += f"{cpu:>5} {mem:>5}  {cmd}\n"
        
        message += "```"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_top_cpu: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_diagnostics')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_top_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ процессов по RAM"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['ps', 'aux', '--sort=-%mem'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')
        
        message = "💾 *TOP RAM ПРОЦЕССЫ*\n\n```\n"
        message += "MEM%  CPU%  COMMAND\n"
        message += "-" * 30 + "\n"
        
        for line in lines[1:11]:
            parts = line.split()
            if len(parts) >= 11:
                cpu = parts[2]
                mem = parts[3]
                cmd = parts[10][:20]
                message += f"{mem:>5} {cpu:>5}  {cmd}\n"
        
        message += "```"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_top_ram: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_diagnostics')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_big_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать большие файлы на диске"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Ищем файлы больше 100MB
        result = subprocess.run(
            ['find', '/', '-type', 'f', '-size', '+100M', '-exec', 'ls', '-lh', '{}', ';'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        lines = result.stdout.strip().split('\n')
        # Фильтруем пустые строки
        files = [l for l in lines if l.strip()]
        
        if files:
            message = "🗂️ *БОЛЬШИЕ ФАЙЛЫ (>100MB)*\n\n```\n"
            for line in files[:15]:
                parts = line.split()
                if len(parts) >= 9:
                    size = parts[4]
                    path = ' '.join(parts[8:])
                    # Сокращаем путь
                    if len(path) > 40:
                        path = "..." + path[-37:]
                    message += f"{size:>6}  {path}\n"
            
            if len(files) > 15:
                message += f"\n... и ещё {len(files) - 15} файлов\n"
            message += "```"
        else:
            message = "🗂️ *БОЛЬШИЕ ФАЙЛЫ*\n\n✅ Нет файлов больше 100MB"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут (поиск занял более 30 сек)"
    except Exception as e:
        logger.error(f"Ошибка cmd_big_files: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_diagnostics')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_io_wait(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать I/O wait статистику"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['iostat', '-x', '1', '2'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout.strip()
        
        if output:
            # Берём последний блок вывода
            blocks = output.split('\n\n')
            last_block = blocks[-1] if blocks else output
            
            message = "📉 *I/O СТАТИСТИКА*\n\n```\n"
            lines = last_block.split('\n')
            for line in lines[:12]:
                message += line[:65] + "\n"
            message += "```"
        else:
            message = "📉 *I/O СТАТИСТИКА*\n\n❌ Нет данных"
            
    except FileNotFoundError:
        message = "📉 *I/O СТАТИСТИКА*\n\n❌ iostat не установлен\n\nУстановите: `apt install sysstat`"
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_io_wait: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_diagnostics')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_test_dns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестирование DNS"""
    query = update.callback_query
    await query.answer()
    
    try:
        dns_servers = ['8.8.8.8', '1.1.1.1', '77.88.8.8']
        test_domain = 'google.com'
        
        message = "🧪 *ТЕСТ DNS*\n\n"
        
        for dns in dns_servers:
            try:
                result = subprocess.run(
                    ['dig', f'@{dns}', test_domain, '+short', '+time=2', '+tries=1'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    ip = result.stdout.strip().split('\n')[0]
                    message += f"✅ `{dns}` → {ip}\n"
                else:
                    message += f"❌ `{dns}` — нет ответа\n"
                    
            except subprocess.TimeoutExpired:
                message += f"⏱️ `{dns}` — таймаут\n"
            except Exception as e:
                message += f"❌ `{dns}` — ошибка\n"
        
        # Проверяем системный DNS
        message += "\n*Системный DNS:*\n"
        try:
            result = subprocess.run(
                ['dig', test_domain, '+short', '+time=2'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip():
                message += f"✅ Работает → {result.stdout.strip().split()[0]}"
            else:
                message += "❌ Не отвечает"
        except:
            message += "❌ Ошибка проверки"
            
    except FileNotFoundError:
        message = "🧪 *ТЕСТ DNS*\n\n❌ dig не установлен\n\nУстановите: `apt install dnsutils`"
    except Exception as e:
        logger.error(f"Ошибка cmd_test_dns: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_diagnostics')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# --- DOCKER ---

async def cmd_docker_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику Docker контейнеров"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['docker', 'stats', '--no-stream', '--format', 
             'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}'],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                message = "📊 *DOCKER STATS*\n\n```\n"
                lines = output.split('\n')
                for line in lines[:15]:
                    message += line[:65] + "\n"
                if len(lines) > 15:
                    message += f"\n... и ещё {len(lines) - 15}\n"
                message += "```"
            else:
                message = "📊 *DOCKER STATS*\n\n✅ Нет запущенных контейнеров"
        else:
            message = f"📊 *DOCKER STATS*\n\n❌ Ошибка: {result.stderr}"
            
    except FileNotFoundError:
        message = "📊 *DOCKER STATS*\n\n❌ Docker не установлен"
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_docker_stats: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_docker')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_docker_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать размер Docker образов"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['docker', 'images', '--format', 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                message = "📦 *DOCKER IMAGES*\n\n```\n"
                lines = output.split('\n')
                for line in lines[:15]:
                    message += line[:65] + "\n"
                if len(lines) > 15:
                    message += f"\n... и ещё {len(lines) - 15}\n"
                message += "```\n"
                
                # Общий размер
                du_result = subprocess.run(
                    ['docker', 'system', 'df', '--format', '{{.Type}}\t{{.Size}}'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if du_result.returncode == 0:
                    message += "\n*Использование диска:*\n```\n"
                    message += du_result.stdout.strip()
                    message += "\n```"
            else:
                message = "📦 *DOCKER IMAGES*\n\n✅ Нет образов"
        else:
            message = f"📦 *DOCKER IMAGES*\n\n❌ Ошибка: {result.stderr}"
            
    except FileNotFoundError:
        message = "📦 *DOCKER IMAGES*\n\n❌ Docker не установлен"
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_docker_images: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_docker')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


# --- ПРОЦЕССЫ ---

async def cmd_zombie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать zombie процессы"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')
        zombies = [l for l in lines if ' Z ' in l or ' Z+ ' in l]
        
        if zombies:
            message = "🔥 *ZOMBIE ПРОЦЕССЫ*\n\n"
            message += f"Найдено: {len(zombies)}\n\n```\n"
            for line in zombies[:10]:
                parts = line.split()
                if len(parts) >= 11:
                    pid = parts[1]
                    cmd = ' '.join(parts[10:])[:30]
                    message += f"PID {pid}: {cmd}\n"
            message += "```"
        else:
            message = "🔥 *ZOMBIE ПРОЦЕССЫ*\n\n✅ Нет zombie процессов"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_zombie: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_diagnostics')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_threads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать количество потоков по процессам"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['ps', '-eo', 'nlwp,pid,comm', '--sort=-nlwp'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        lines = result.stdout.strip().split('\n')
        
        message = "🧵 *ПОТОКИ ПО ПРОЦЕССАМ*\n\n```\n"
        message += "THREADS  PID    COMMAND\n"
        message += "-" * 30 + "\n"
        
        for line in lines[1:12]:  # Топ 11, пропуская заголовок
            parts = line.split()
            if len(parts) >= 3:
                threads = parts[0]
                pid = parts[1]
                cmd = parts[2][:15]
                message += f"{threads:>7}  {pid:<6} {cmd}\n"
        
        message += "```"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_threads: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_diagnostics')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# --- СИСТЕМА ---

async def cmd_apt_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю apt"""
    query = update.callback_query
    await query.answer()

    try:
        log_file = '/var/log/apt/history.log'
        log_file_gz = '/var/log/apt/history.log.1.gz'
        output = ""

        # Сначала пробуем текущий лог
        if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
            result = subprocess.run(
                ['tail', '-50', log_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout.strip()

        # Если пусто — читаем архив
        if not output and os.path.exists(log_file_gz):
            result = subprocess.run(
                ['zcat', log_file_gz],
                capture_output=True,
                text=True,
                timeout=10
            )
            lines = result.stdout.strip().split('\n')
            output = '\n'.join(lines[-50:])

        if output:
            message = "📦 *APT ИСТОРИЯ*\n\n```\n"
            lines = output.split('\n')
            for line in lines[-20:]:
                message += line[:65] + "\n"
            message += "```"
        else:
            message = "📦 *APT ИСТОРИЯ*\n\n✅ Лог пуст"

    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_apt_history: {e}")
        message = f"❌ Ошибка: {str(e)}"

    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_system')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_apt_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать размер apt кэша"""
    query = update.callback_query
    await query.answer()
    
    try:
        result = subprocess.run(
            ['du', '-sh', '/var/cache/apt/archives'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        cache_size = result.stdout.strip().split()[0] if result.stdout else "N/A"
        
        # Количество пакетов в кэше
        count_result = subprocess.run(
            ['ls', '-1', '/var/cache/apt/archives/'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        pkg_count = len([l for l in count_result.stdout.split('\n') if l.endswith('.deb')])
        
        message = "🧹 *APT КЭША*\n\n"
        message += f"📦 Размер кэша: *{cache_size}*\n"
        message += f"📄 Пакетов в кэше: *{pkg_count}*\n\n"
        message += "_Для очистки выполните:_\n"
        message += "`apt clean`"
            
    except subprocess.TimeoutExpired:
        message = "❌ Таймаут выполнения команды"
    except Exception as e:
        logger.error(f"Ошибка cmd_apt_cache: {e}")
        message = f"❌ Ошибка: {str(e)}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='extra_system')]]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# ЗАПУСК БОТА
# ============================================


async def authorize_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Блокирует обновления от неавторизованных пользователей."""
    user = update.effective_user

    if user is None or user.id != ALLOWED_USER_ID:
        raise ApplicationHandlerStop()


async def main():
    """
    Главная функция запуска бота.
    Инициализирует Application, регистрирует все обработчики команд
    и callback-запросов, запускает polling для получения обновлений.
    """
    logger.info("Запуск admin bot v2...")
    
    app = Application.builder().token(TOKEN).build()
    
    # Централизованная авторизация до остальных обработчиков
    app.add_handler(
        TypeHandler(Update, authorize_update, block=True),
        group=-1
    )

    # ===== КОМАНДЫ =====
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_command))
    
    # ===== CALLBACK HANDLERS =====
    # Порядок важен: сначала более специфичные паттерны, потом общие
    
    # Статистика
    app.add_handler(CallbackQueryHandler(show_stats, pattern='^stats$'))
    app.add_handler(CallbackQueryHandler(network_stats_menu, pattern='^network_stats_menu$'))
    app.add_handler(CallbackQueryHandler(show_network_stats, pattern='^net_stats_'))
    app.add_handler(CallbackQueryHandler(clear_swap, pattern='^clear_swap$'))
    app.add_handler(CallbackQueryHandler(confirm_clear_swap, pattern='^confirm_clear_swap$'))
    
    # Забаненные IP / Fail2ban
    app.add_handler(CallbackQueryHandler(show_banned_ips, pattern='^banned_ips$'))
    app.add_handler(CallbackQueryHandler(unban_all, pattern='^unban_all$'))
    app.add_handler(CallbackQueryHandler(confirm_unban_all, pattern='^confirm_unban_all$'))
    app.add_handler(CallbackQueryHandler(ask_unban_ip, pattern='^unban_ip_input$'))
    app.add_handler(CallbackQueryHandler(unban_ip, pattern='^unban_'))
    app.add_handler(CallbackQueryHandler(f2b_status, pattern='^f2b_status$'))
    
    # Docker
    app.add_handler(CallbackQueryHandler(show_docker_list, pattern='^docker_list$'))
    app.add_handler(CallbackQueryHandler(docker_action, pattern='^docker_(start|stop|restart|logs)_'))
    app.add_handler(CallbackQueryHandler(docker_control, pattern='^docker_'))
    
    # Системная информация
    app.add_handler(CallbackQueryHandler(show_sysinfo, pattern='^sysinfo$'))
    
    # Обновление системы
    app.add_handler(CallbackQueryHandler(update_system, pattern='^update_system$'))
    app.add_handler(CallbackQueryHandler(update_action, pattern='^update_(refresh|check|upgrade)$'))
    app.add_handler(CallbackQueryHandler(confirm_upgrade, pattern='^confirm_upgrade$'))
    app.add_handler(CallbackQueryHandler(request_fix_broken, pattern='^request_fix_broken$'))
    app.add_handler(CallbackQueryHandler(fix_broken_packages, pattern='^fix_broken$'))
    
    # Логи
    app.add_handler(CallbackQueryHandler(logs_menu, pattern='^logs_menu$'))
    app.add_handler(CallbackQueryHandler(show_logs, pattern='^logs_'))
    
    # Графики
    app.add_handler(CallbackQueryHandler(show_graphs_menu, pattern='^graphs$'))
    app.add_handler(CallbackQueryHandler(show_graph, pattern='^graph_'))
    
    # Тест скорости
    app.add_handler(CallbackQueryHandler(iperf_speedtest, pattern='^iperf_speedtest$'))
    
    # Перезагрузка / Выключение
    app.add_handler(CallbackQueryHandler(confirm_reboot, pattern='^reboot$'))
    app.add_handler(CallbackQueryHandler(confirm_shutdown, pattern='^shutdown$'))
    app.add_handler(CallbackQueryHandler(execute_power_action, pattern='^execute_(reboot|shutdown|power_cancel)$'))
    
    # Навигация
    app.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
    
    # Дополнительные команды - навигация по меню
    app.add_handler(CallbackQueryHandler(show_extra_menu, pattern='^extra_menu$'))
    app.add_handler(CallbackQueryHandler(show_extra_network, pattern='^extra_network$'))
    app.add_handler(CallbackQueryHandler(show_extra_security, pattern='^extra_security$'))
    app.add_handler(CallbackQueryHandler(show_extra_diagnostics, pattern='^extra_diagnostics$'))
    app.add_handler(CallbackQueryHandler(show_extra_docker, pattern='^extra_docker$'))
    app.add_handler(CallbackQueryHandler(show_extra_system, pattern='^extra_system$'))

    # Дополнительные команды - реализация
    app.add_handler(CallbackQueryHandler(cmd_open_ports, pattern='^cmd_open_ports$'))
    app.add_handler(CallbackQueryHandler(cmd_active_connections, pattern='^cmd_active_connections$'))
    app.add_handler(CallbackQueryHandler(cmd_ssh_sessions, pattern='^cmd_ssh_sessions$'))
    app.add_handler(CallbackQueryHandler(cmd_uptime, pattern='^cmd_uptime$'))
    app.add_handler(CallbackQueryHandler(cmd_systemd_failed, pattern='^cmd_systemd_failed$'))
    app.add_handler(CallbackQueryHandler(cmd_traceroute, pattern='^cmd_traceroute$'))

    # Дополнительные команды - безопасность
    app.add_handler(CallbackQueryHandler(cmd_last_logins, pattern='^cmd_last_logins$'))
    app.add_handler(CallbackQueryHandler(cmd_sudo_logs, pattern='^cmd_sudo_logs$'))
    app.add_handler(CallbackQueryHandler(cmd_ssh_sessions_sec, pattern='^cmd_ssh_sessions_sec$'))

    # Дополнительные команды - диагностика
    app.add_handler(CallbackQueryHandler(cmd_top_cpu, pattern='^cmd_top_cpu$'))
    app.add_handler(CallbackQueryHandler(cmd_top_ram, pattern='^cmd_top_ram$'))
    app.add_handler(CallbackQueryHandler(cmd_big_files, pattern='^cmd_big_files$'))
    app.add_handler(CallbackQueryHandler(cmd_io_wait, pattern='^cmd_io_wait$'))
    app.add_handler(CallbackQueryHandler(cmd_test_dns, pattern='^cmd_test_dns$'))

    # Дополнительные команды - Docker
    app.add_handler(CallbackQueryHandler(cmd_docker_stats, pattern='^cmd_docker_stats$'))
    app.add_handler(CallbackQueryHandler(cmd_docker_images, pattern='^cmd_docker_images$'))
    
    # Дополнительные команды - Процессы
    app.add_handler(CallbackQueryHandler(cmd_zombie, pattern='^cmd_zombie$'))
    app.add_handler(CallbackQueryHandler(cmd_threads, pattern='^cmd_threads$'))

    # Дополнительные команды - Система
    app.add_handler(CallbackQueryHandler(cmd_apt_history, pattern='^cmd_apt_history$'))
    app.add_handler(CallbackQueryHandler(cmd_apt_cache, pattern='^cmd_apt_cache$'))
    
    # ===== ОБРАБОТЧИК ТЕКСТА =====
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("✅ Admin bot v2 запущен (все обработчики зарегистрированы)")
    
    # Запуск
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Admin bot v2 остановлен")


if __name__ == '__main__':
    asyncio.run(main())
