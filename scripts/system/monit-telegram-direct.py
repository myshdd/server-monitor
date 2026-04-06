#!/usr/bin/env python3
"""
Monit Telegram Direct - отправка уведомлений с логикой состояний
"""
import sys
import os
import hashlib
import time
import re

sys.path.insert(0, '/opt/server-monitor/lib')
from config import get_config

# Директория для хранения состояний
STATE_DIR = '/var/lib/server-monitor/monit-states'
# Rate limit в секундах
RATE_LIMIT_SECONDS = 300


def get_state_file(alert_type: str) -> str:
    """Получить путь к файлу состояния"""
    safe_name = hashlib.md5(alert_type.encode()).hexdigest()[:16]
    return os.path.join(STATE_DIR, f"{safe_name}.state")


def get_rate_limit_file(alert_type: str) -> str:
    """Получить путь к файлу rate limit"""
    safe_name = hashlib.md5(alert_type.encode()).hexdigest()[:16]
    return os.path.join(STATE_DIR, f"{safe_name}.ratelimit")


def is_alert(message: str) -> bool:
    """Проверить, является ли сообщение алертом"""
    alert_indicators = ['⚠️', '🚨', '❌', '🔴']
    return any(indicator in message for indicator in alert_indicators)


def is_recovery(message: str) -> bool:
    """Проверить, является ли сообщение восстановлением"""
    recovery_indicators = ['✅', '🟢']
    return any(indicator in message for indicator in recovery_indicators)


def check_state_exists(alert_type: str) -> bool:
    """Проверить, существует ли состояние"""
    return os.path.exists(get_state_file(alert_type))


def set_state(alert_type: str):
    """Установить состояние"""
    state_file = get_state_file(alert_type)
    with open(state_file, 'w') as f:
        f.write(str(time.time()))


def clear_state(alert_type: str):
    """Очистить состояние"""
    state_file = get_state_file(alert_type)
    if os.path.exists(state_file):
        os.remove(state_file)


def check_rate_limit(alert_type: str) -> bool:
    """Проверить rate limit. True = можно отправить."""
    rate_file = get_rate_limit_file(alert_type)
    current_time = time.time()
    
    if os.path.exists(rate_file):
        try:
            with open(rate_file, 'r') as f:
                last_time = float(f.read().strip())
            if current_time - last_time < RATE_LIMIT_SECONDS:
                return False
        except (ValueError, IOError):
            pass
    
    return True


def update_rate_limit(alert_type: str):
    """Обновить время последней отправки"""
    rate_file = get_rate_limit_file(alert_type)
    with open(rate_file, 'w') as f:
        f.write(str(time.time()))


def get_resource_type(message: str) -> str:
    """
    Извлечь тип ресурса из сообщения.
    Возвращает унифицированный ключ для сопоставления алерта и восстановления.
    """
    # Убираем эмодзи
    clean = message
    for emoji in ['⚠️', '✅', '🚨', '❌', '🔴', '🟢']:
        clean = clean.replace(emoji, '')
    clean = clean.strip()
    
    # Словарь паттернов: ключевые слова -> унифицированный тип
    patterns = {
        # CPU/Load
        r'(нагрузка|load).*(1.*мин|1min)': 'load_1min',
        r'(нагрузка|load).*(5.*мин|5min)': 'load_5min',
        r'(нагрузка|load).*(15.*мин|15min)': 'load_15min',
        r'(нагрузка|load).*cpu': 'load_cpu',
        
        # Memory
        r'(память|memory|mem)': 'memory',
        
        # Swap
        r'swap': 'swap',
        
        # Disk
        r'(диск|disk|место)': 'disk',
        r'inode': 'inode',
        
        # Containers
        r'awg|amnezia-awg': 'container_awg',
        r'dns.*контейнер|контейнер.*dns|amnezia-dns': 'container_dns',
        r'xray': 'container_xray',
        r'socks5|socks': 'container_socks5',
        
        # Services
        r'docker.*сервис|сервис.*docker': 'service_docker',
        r'fail2ban': 'service_fail2ban',
        r'ssh.*сервис|сервис.*ssh': 'service_ssh',
        r'cron': 'service_cron',
        r'rsyslog': 'service_rsyslog',
        r'(время|time|ntp|synch)': 'service_time',
    }
    
    clean_lower = clean.lower()
    
    for pattern, resource_type in patterns.items():
        if re.search(pattern, clean_lower):
            return resource_type
    
    # Fallback: используем хеш от очищенного сообщения
    # Убираем типичные окончания
    fallback = clean_lower
    for suffix in [' в норме', ' восстановлен', ' восстановлена', ' работает', 
                   ' не работает', ' упал', ' остановлен', ' остановлена',
                   ' заполнен', ' заполнена', '!']:
        fallback = fallback.replace(suffix, '')
    
    return f"unknown_{hashlib.md5(fallback.strip().encode()).hexdigest()[:8]}"


def send_telegram(token: str, chat_id: str, message: str) -> bool:
    """Отправить сообщение в Telegram"""
    try:
        import requests
        response = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data={'chat_id': chat_id, 'text': message},
            timeout=10
        )
        return response.ok
    except Exception:
        return False


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    
    if len(sys.argv) < 2:
        sys.exit(0)
    
    message = sys.argv[1]
    resource_type = get_resource_type(message)
    
    if is_alert(message):
        # Алерт о проблеме
        if not check_rate_limit(resource_type):
            sys.exit(0)
        set_state(resource_type)
        
    elif is_recovery(message):
        # Восстановление - только если был алерт
        if not check_state_exists(resource_type):
            sys.exit(0)
        clear_state(resource_type)
        
    else:
        # Неизвестный тип
        if not check_rate_limit(resource_type):
            sys.exit(0)
    
    # Отправляем
    try:
        config = get_config()
        token = config.get_secret('telegram.monitor_bot_token')
        chat_id = config.get_secret('telegram.chat_id')
        
        if send_telegram(token, chat_id, message):
            update_rate_limit(resource_type)
    except Exception:
        pass


if __name__ == '__main__':
    main()
