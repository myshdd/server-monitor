#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /opt/server-monitor/bots/monitor.py
# Мониторинг сервера с отправкой уведомлений в Telegram

import asyncio
import time
import psutil
import subprocess
import json
import os
import sys
import re
import socket
from datetime import datetime
from collections import defaultdict

# Добавляем путь к библиотеке конфигурации
sys.path.insert(0, '/usr/local/lib/server-monitor')

from config import get_config, setup_logging, ConfigError
from telegram import Bot

# ============================================
# ЗАГРУЗКА КОНФИГУРАЦИИ
# ============================================

try:
    config = get_config()
    logger = setup_logging(__name__, config.get_path("logs.monitoring"))
    
    # Загружаем настройки
    TOKEN = config.telegram_monitor_token
    CHAT_ID = config.telegram_chat_id
    
    # Пороги из конфига
    CHECK_INTERVAL = config.get_setting("monitoring.check_interval", 180)
    
    # Настройки SSH мониторинга
    SSH_MONITOR_ENABLED = config.get_setting("monitoring.ssh_monitor.enabled", True)
    SSH_ALERT_WINDOW = config.get_setting("monitoring.ssh_monitor.alert_window", 60)
    SSH_MAX_ALERTS = config.get_setting("monitoring.ssh_monitor.max_alerts_per_ip", 3)
    
    # Настройки мониторинга портов
    PORT_MONITOR_ENABLED = config.get_setting("monitoring.port_monitor.enabled", True)
    PORT_CHECK_INTERVAL = config.get_setting("monitoring.port_monitor.check_interval", 30)
    
    logger.info("Конфигурация успешно загружена")
    logger.info(f"Интервал проверки: {CHECK_INTERVAL} сек")
    
except ConfigError as e:
    print(f"❌ Ошибка загрузки конфигурации: {e}", file=sys.stderr)
    sys.exit(1)

# ============================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ
# ============================================

# Состояние алертов (чтобы не спамить)
# ============================================

async def should_alert_ssh(ip: str) -> bool:
    """
    Проверяет, нужно ли отправлять алерт для данного IP.
    Реализует rate limiting: не более SSH_MAX_ALERTS за SSH_ALERT_WINDOW секунд.
    """
    now = time.time()
    
    # Удаляем старые записи
    ssh_alerts[ip] = [t for t in ssh_alerts[ip] if now - t < SSH_ALERT_WINDOW]
    
    if len(ssh_alerts[ip]) < SSH_MAX_ALERTS:
        ssh_alerts[ip].append(now)
        return True
    
    return False

# ============================================
# ОТПРАВКА УВЕДОМЛЕНИЙ В TELEGRAM
# ============================================

async def send_ssh_alert(bot: Bot, alert_type: str, user: str, ip: str, reason: str = ""):
    """
    Отправляет уведомление о SSH-событии.
    
    Args:
        bot: Экземпляр Telegram Bot
        alert_type: Тип события (login, login_key, failed)
        user: Имя пользователя
        ip: IP-адрес
        reason: Причина (для неудачных попыток)
    """
    now = datetime.now().strftime('%b %d %H:%M:%S')
    
    if alert_type == 'login':
        emoji = "🔐"
        title = "SSH вход"
    elif alert_type == 'login_key':
        emoji = "🔑"
        title = "SSH вход (ключ)"
    else:
        emoji = "⚠️"
        title = "Неудачная попытка SSH"
    
    message = (
        f"{emoji} *{title}*\n"
        f"👤 *Пользователь:* `{user}`\n"
        f"🌐 *IP адрес:* `{ip}`\n"
        f"⏰ *Время:* {now}"
    )
    
    if reason:
        message += f"\n❗ *Причина:* {reason}"
    
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"SSH {alert_type}: {user} с {ip}")
    except Exception as e:
        logger.error(f"Ошибка отправки SSH алерта: {e}")


async def send_port_alert(bot: Bot, container: str, port: int, protocol: str, status: str):
    """
    Отправляет уведомление об изменении статуса порта Docker.
    
    Args:
        bot: Экземпляр Telegram Bot
        container: Имя контейнера
        port: Номер порта
        protocol: Протокол (tcp/udp)
        status: Статус (new, changed, removed, recovered)
    """
    if status == 'new':
        emoji = "🆕"
        title = "Новый порт Docker"
    elif status == 'changed':
        emoji = "🔄"
        title = "Порт Docker изменен"
    elif status == 'removed':
        emoji = "❌"
        title = "Порт Docker удален"
    elif status == 'recovered':
        emoji = "✅"
        title = "Порт восстановлен"
    else:
        emoji = "ℹ️"
        title = "Изменение порта Docker"
    
    message = (
        f"{emoji} *{title}*\n"
        f"🐳 *Контейнер:* `{container}`\n"
        f"🔌 *Порт:* {port}/{protocol}"
    )
    
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Порт {status}: {container}:{port}/{protocol}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о порте: {e}")

# ============================================
# МОНИТОРИНГ SSH ВХОДОВ
# Отслеживание успешных и неудачных попыток входа
# ============================================

async def monitor_ssh(bot: Bot):
    """
    Мониторинг SSH входов в реальном времени.
    Читает /var/log/auth.log через tail -f и парсит события.
    Отправляет уведомления о:
    - Успешных входах (пароль и ключ)
    - Неудачных попытках (с rate limiting)
    """
    if not SSH_MONITOR_ENABLED:
        logger.info("Мониторинг SSH отключён в конфигурации")
        return
    
    logger.info("Запуск мониторинга SSH")
    
    process = None
    
    while True:
        try:
            # Запускаем tail для отслеживания новых записей
            process = await asyncio.create_subprocess_exec(
                'tail', '-f', '-n', '0', '/var/log/auth.log',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            logger.info("SSH мониторинг: подключён к /var/log/auth.log")
            
            while True:
                try:
                    # Читаем строку с таймаутом для периодической проверки
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=300  # 5 минут таймаут для перезапуска
                    )
                    
                    if not line:
                        logger.warning("SSH мониторинг: EOF, перезапуск...")
                        break
                    
                    line = line.decode('utf-8').strip()
                    await process_ssh_line(bot, line)
                    
                except asyncio.TimeoutError:
                    # Таймаут — проверяем что процесс жив и продолжаем
                    if process.returncode is not None:
                        logger.warning("SSH мониторинг: процесс завершился, перезапуск...")
                        break
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка в мониторинге SSH: {e}")
        
        finally:
            # Закрываем процесс если он существует
            if process and process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
        
        # Пауза перед перезапуском
        logger.info("SSH мониторинг: перезапуск через 5 секунд...")
        await asyncio.sleep(5)


async def process_ssh_line(bot: Bot, line: str):
    """
    Обрабатывает одну строку из auth.log.
    Парсит различные типы SSH-событий и отправляет соответствующие алерты.
    """
    # Успешный вход по паролю
    if 'Accepted password for' in line:
        match = re.search(r'Accepted password for (\S+) from (\S+)', line)
        if match:
            user, ip = match.groups()
            await send_ssh_alert(bot, 'login', user, ip)
    
    # Успешный вход по ключу
    elif 'Accepted publickey for' in line:
        match = re.search(r'Accepted publickey for (\S+) from (\S+)', line)
        if match:
            user, ip = match.groups()
            await send_ssh_alert(bot, 'login_key', user, ip)
    
    # Неудачная попытка для root
    elif 'Failed password for root' in line:
        match = re.search(r'Failed password for root from (\S+)', line)
        if match:
            ip = match.group(1)
            if await should_alert_ssh(ip):
                await send_ssh_alert(bot, 'failed', 'root', ip, 'попытка входа под root')
    
    # Неудачная попытка для несуществующего пользователя
    elif 'Failed password for invalid user' in line:
        match = re.search(r'Failed password for invalid user (\S+) from (\S+)', line)
        if match:
            user, ip = match.groups()
            if await should_alert_ssh(ip):
                await send_ssh_alert(bot, 'failed', f'{user} (не существует)', ip, 'подбор пользователей')
    
    # Неудачная попытка для существующего пользователя (кроме root)
    elif 'Failed password for' in line and 'invalid user' not in line:
        match = re.search(r'Failed password for (\S+) from (\S+)', line)
        if match:
            user, ip = match.groups()
            if user != 'root':
                if await should_alert_ssh(ip):
                    await send_ssh_alert(bot, 'failed', user, ip, 'неверный пароль')

# ============================================
# МОНИТОРИНГ DOCKER ПОРТОВ
# Отслеживание изменений портов контейнеров и их доступности
# ============================================

def get_docker_ports() -> dict:
    """
    Получает список опубликованных портов всех Docker контейнеров.
    
    Returns:
        Словарь вида {port_id: {container, port, protocol, container_port}}
    """
    ports = {}
    
    try:
        # Получаем список контейнеров
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return ports
        
        containers = [c for c in result.stdout.strip().split('\n') if c]
        
        for container in containers:
            # Получаем информацию о портах контейнера
            inspect = subprocess.run(
                ['docker', 'inspect', container],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if inspect.returncode != 0:
                continue
            
            data = json.loads(inspect.stdout)
            
            if not data:
                continue
            
            network_settings = data[0].get('NetworkSettings', {})
            port_data = network_settings.get('Ports', {})
            
            for port_proto, mappings in port_data.items():
                if mappings:  # Если порт опубликован
                    port, proto = port_proto.split('/')
                    host_port = mappings[0].get('HostPort', port)
                    
                    port_id = f"{container}_{port_proto}"
                    ports[port_id] = {
                        'container': container,
                        'port': int(host_port),
                        'protocol': proto,
                        'container_port': port
                    }
    
    except subprocess.TimeoutExpired:
        logger.error("Таймаут при получении портов Docker")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON от docker inspect: {e}")
    except Exception as e:
        logger.error(f"Ошибка получения портов Docker: {e}")
    
    return ports


async def check_port_availability(host: str, port: int, protocol: str, timeout: int = 2) -> bool:
    """
    Проверяет доступность порта.
    
    Args:
        host: Хост для проверки
        port: Номер порта
        protocol: Протокол (tcp/udp)
        timeout: Таймаут в секундах
    
    Returns:
        True если порт доступен, False иначе
    """
    try:
        if protocol == 'tcp':
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        else:
            # Для UDP просто проверяем что можем создать соединение
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return True
    except Exception:
        return False


async def monitor_docker_ports(bot: Bot):
    """
    Мониторинг изменений портов Docker контейнеров.
    Отслеживает появление, изменение и удаление портов.
    """
    if not PORT_MONITOR_ENABLED:
        logger.info("Мониторинг портов Docker отключён в конфигурации")
        return
    
    logger.info("Запуск мониторинга портов Docker")
    
    last_ports = {}
    
    while True:
        try:
            current_ports = get_docker_ports()
            
            # Проверяем новые и изменённые порты
            for port_id, info in current_ports.items():
                if port_id not in last_ports:
                    # Новый порт
                    await send_port_alert(
                        bot,
                        info['container'],
                        info['port'],
                        info['protocol'],
                        'new'
                    )
                elif last_ports[port_id]['port'] != info['port']:
                    # Порт изменился
                    await send_port_alert(
                        bot,
                        info['container'],
                        info['port'],
                        info['protocol'],
                        'changed'
                    )
            
            # Проверяем удалённые порты
            for port_id, info in last_ports.items():
                if port_id not in current_ports:
                    await send_port_alert(
                        bot,
                        info['container'],
                        info['port'],
                        info['protocol'],
                        'removed'
                    )
            
            last_ports = current_ports
            
        except Exception as e:
            logger.error(f"Ошибка в мониторинге портов Docker: {e}")
        
        await asyncio.sleep(PORT_CHECK_INTERVAL)


async def check_port_availability_loop(bot: Bot):
    """
    Периодическая проверка доступности портов Docker контейнеров.
    Отправляет уведомления при восстановлении недоступных портов.
    """
    if not PORT_MONITOR_ENABLED:
        return
    
    logger.info("Запуск проверки доступности портов")
    
    last_ports_status = {}
    
    while True:
        try:
            current_ports = get_docker_ports()
            
            for port_id, info in current_ports.items():
                port = info['port']
                protocol = info['protocol']
                container = info['container']
                
                # Проверяем доступность
                is_available = await check_port_availability('localhost', port, protocol)
                
                # Сравниваем с предыдущим состоянием
                if port_id in last_ports_status:
                    was_available = last_ports_status[port_id]
                    
                    if not was_available and is_available:
                        # Порт восстановился
                        await send_port_alert(bot, container, port, protocol, 'recovered')
                
                last_ports_status[port_id] = is_available
            
            # Удаляем неактуальные записи
            for port_id in list(last_ports_status.keys()):
                if port_id not in current_ports:
                    del last_ports_status[port_id]
            
        except Exception as e:
            logger.error(f"Ошибка в проверке доступности портов: {e}")
        
        await asyncio.sleep(PORT_CHECK_INTERVAL)

# ============================================
# ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ============================================

async def main():
    """
    Главная функция запуска мониторинга.
    Инициализирует бота и запускает все задачи мониторинга параллельно:
    - Мониторинг ресурсов (CPU, RAM, DISK)
    - Мониторинг SSH входов
    - Мониторинг Docker портов
    - Проверка доступности портов
    """
    logger.info("=" * 50)
    logger.info("Запуск Server Monitor v2")
    logger.info("=" * 50)
    
    # Создаём экземпляр бота
    bot = Bot(token=TOKEN)
    
    # Отправляем тестовое сообщение при запуске
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "🚀 *Server Monitor v2 запущен!*\n\n"
                f"📊 Интервал проверки: {CHECK_INTERVAL} сек\n"
                f"🔐 SSH мониторинг: {'✅' if SSH_MONITOR_ENABLED else '❌'}\n"
                f"🐳 Docker мониторинг: {'✅' if PORT_MONITOR_ENABLED else '❌'}"
            ),
            parse_mode='Markdown'
        )
        logger.info("Стартовое сообщение отправлено")
    except Exception as e:
        logger.error(f"Ошибка отправки стартового сообщения: {e}")
    
    # Собираем задачи для запуска
    tasks = [
    ]
    
    if SSH_MONITOR_ENABLED:
        tasks.append(asyncio.create_task(monitor_ssh(bot)))
    
    if PORT_MONITOR_ENABLED:
        tasks.append(asyncio.create_task(monitor_docker_ports(bot)))
        tasks.append(asyncio.create_task(check_port_availability_loop(bot)))
    
    logger.info(f"Запущено {len(tasks)} задач мониторинга")
    
    # Запускаем все задачи параллельно
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        # Отправляем уведомление об остановке
        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text="⚠️ *Server Monitor остановлен*",
                parse_mode='Markdown'
            )
        except Exception:
            pass
        
        logger.info("Server Monitor v2 остановлен")


if __name__ == "__main__":
    asyncio.run(main())
